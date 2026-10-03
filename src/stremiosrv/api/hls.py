"""Stremio hlsv2 transcode API: probe, master/media playlists, fMP4 segments.

The master playlist references child URIs we serve, so internal naming need not match the stock
server byte-for-byte — the player follows whatever URIs we publish.
"""
from __future__ import annotations

import logging
import math
import subprocess
import time
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response

from stremiosrv.api.media_fetch import resolve_media_input
from stremiosrv.api.subs import parse_stream_url
from stremiosrv.transcode.fingerprint import decide
from stremiosrv.transcode.probe import ProbeTimeoutError, probe_media

router = APIRouter(prefix="/hlsv2")
logger = logging.getLogger("stremiosrv.hls")

_M3U8 = "application/vnd.apple.mpegurl"


def _converter(request: Request):
    return getattr(request.app.state, "converter", None)


def _playback_registry(request: Request):
    return getattr(request.app.state, "playback_registry", None)


def _torrent_input_is_incomplete(request: Request, media_url: str) -> bool:
    """True only for a local torrent stream whose currently-wanted data is incomplete."""
    parsed = parse_stream_url(media_url)
    engine = getattr(request.app.state, "engine", None)
    if parsed is None or engine is None:
        return False
    try:
        handle = engine.get(parsed[0])
        return handle is not None and not handle.is_finished()
    except Exception:  # best-effort pacing hint; never changes playback admission
        return False


def _resolve_media_for_hls(request: Request, media_url: str) -> str:
    """Resolve an HLS input, retrying once when a torrent head is not ready yet.

    The retry deliberately calls resolve_media_input() again instead of bypassing the
    guard: each attempt must re-read and validate the torrent head before ffprobe is
    allowed to open it. Only the readiness-specific 504 is retried; 403/415 and every
    other error remain final.
    """
    try:
        return resolve_media_input(request, media_url)
    except HTTPException as exc:
        if exc.status_code != 504 or exc.detail != "media source too slow":
            raise
        logger.info("media source head not ready; retrying HLS preparation once")
        time.sleep(0.35)
        return resolve_media_input(request, media_url)


def _wait_file(path: Path, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists() and path.stat().st_size > 0:
            return True
        time.sleep(0.2)
    return path.exists()


def _subtitle_streams(probe: dict) -> list[dict]:
    return [
        stream for stream in (probe.get("streams") or [])
        if stream.get("track") == "subtitle" and stream.get("index") is not None
    ]


def _hls_quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _master_with_subtitles(master_text: str, probe: dict, media_url: str) -> str:
    """Advertise embedded text subtitles in the HLS master without asking FFmpeg's HLS muxer to
    multiplex them.

    2.0.14 intentionally removed subtitle variants after FFmpeg rejected the old var_stream_map
    (notably the unsupported sname key). That made A/V reliable again, but Chromium's web player
    discovers embedded subtitles from the HLS master and never calls /subtitles.json on this path.
    We therefore keep FFmpeg responsible only for A/V and attach standards-based WebVTT rendition
    playlists at the API layer.
    """
    tracks = _subtitle_streams(probe)
    if not tracks:
        return master_text

    duration = float((probe.get("format") or {}).get("duration") or 0.0)
    media_lines: list[str] = []
    seen_names: dict[str, int] = {}
    for stream in tracks:
        track = int(stream["index"])
        lang = str(stream.get("lang") or "und")
        title = str(stream.get("title") or "").strip()
        qualifiers: list[str] = []
        if title:
            qualifiers.append(title)
        elif stream.get("forced"):
            qualifiers.append("Forced")
        elif stream.get("hearingImpaired"):
            qualifiers.append("Hearing Impaired")
        base_name = f"{lang} — {' / '.join(qualifiers)}" if qualifiers else lang
        seen_names[base_name] = seen_names.get(base_name, 0) + 1
        ordinal = seen_names[base_name]
        name = base_name if ordinal == 1 else f"{base_name} ({ordinal})"
        query = urlencode({"mediaURL": media_url, "duration": duration})
        uri = f"subtitles/{track}.m3u8?{query}"
        media_lines.append(
            '#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",'
            f'NAME="{_hls_quote(name)}",LANGUAGE="{_hls_quote(lang)}",'
            f'AUTOSELECT=YES,DEFAULT={"YES" if stream.get("default") else "NO"},'
            f'FORCED={"YES" if stream.get("forced") else "NO"},URI="{_hls_quote(uri)}"'
        )

    out: list[str] = []
    inserted = False
    for line in master_text.splitlines():
        if line.startswith("#EXT-X-STREAM-INF:") and 'SUBTITLES=' not in line:
            if not inserted:
                out.extend(media_lines)
                inserted = True
            line += ',SUBTITLES="subs"'
        out.append(line)
    if not inserted:
        out.extend(media_lines)
    return "\n".join(out) + ("\n" if master_text.endswith("\n") else "")


def _subtitle_media_playlist(media_url: str, track: int, duration: float, mpegts_start: int = 0) -> str:
    """Build a VOD WebVTT media playlist with finite extraction windows."""
    parsed = parse_stream_url(media_url)
    if parsed is None:
        raise HTTPException(status_code=400, detail="subtitle mediaURL is not a server stream URL")
    info_hash, idx = parsed
    total = max(float(duration or 0.0), 0.001)
    segment = 30.0
    count = max(1, math.ceil(total / segment))
    lines = [
        "#EXTM3U",
        "#EXT-X-VERSION:3",
        f"#EXT-X-TARGETDURATION:{math.ceil(segment)}",
        "#EXT-X-PLAYLIST-TYPE:VOD",
        "#EXT-X-MEDIA-SEQUENCE:0",
    ]
    for n in range(count):
        offset = n * segment
        length = min(segment, total - offset)
        query = urlencode({
            "mediaURL": media_url,
            "track": track,
            "start": f"{offset:.3f}",
            "duration": f"{length:.3f}",
            "mpegtsStart": int(mpegts_start),
        })
        lines += [
            f"#EXTINF:{length:.3f},",
            f"/{info_hash}/{idx}/subtitles.vtt?{query}",
        ]
    lines.append("#EXT-X-ENDLIST")
    return "\n".join(lines) + "\n"


# HEAD is accepted on the read routes below. FastAPI, unlike bare Starlette, does NOT add HEAD to a
# GET route, so `@router.get` alone answers 405 — which is what the byte-range route already avoids
# by declaring both methods explicitly. Clients that probe a URL before playing it get a hard
# failure otherwise.
#
# /destroy is deliberately NOT in that set. It is the one route here whose GET has a side effect
# (it tears a transcode job down), and HEAD is defined as safe: a crawler, proxy or link-checker
# sending HEAD must not be able to kill someone's playback. It stays GET-only until the reference
# is shown to require otherwise.

# A probe that never answers used to escape as a 500 with a traceback. Both routes here need the
# probe to do their job, so they answer 504 -- the same gateway-timeout the playlist route already
# gives when a transcode fails to start.

@router.api_route("/probe", methods=["GET", "HEAD"])
def probe(mediaURL: str, request: Request) -> dict:
    media = _resolve_media_for_hls(request, mediaURL)
    try:
        pr = probe_media(media)
    except ProbeTimeoutError as e:
        raise HTTPException(status_code=504, detail="probe timed out") from e
    if "hls" in (pr.get("format", {}).get("name") or ""):
        raise HTTPException(status_code=415, detail="playlist inputs are not accepted")
    return pr


@router.api_route("/{job_id}/master.m3u8", methods=["GET", "HEAD"])
def master(
    job_id: str,
    request: Request,
    mediaURL: str,
    videoCodecs: list[str] = Query(default=[]),
    audioCodecs: list[str] = Query(default=[]),
    maxAudioChannels: int = 2,
    maxWidth: int = 3840,
):
    conv = _converter(request)
    if conv is None:
        raise HTTPException(status_code=503, detail="transcoder unavailable")
    media = _resolve_media_for_hls(request, mediaURL)
    try:
        pr = probe_media(media)
    except ProbeTimeoutError as e:
        raise HTTPException(status_code=504, detail="probe timed out") from e
    if "hls" in (pr.get("format", {}).get("name") or ""):
        raise HTTPException(status_code=415, detail="playlist inputs are not accepted")
    dec = decide(pr, videoCodecs or ["h264"], audioCodecs or ["aac"], maxAudioChannels, maxWidth)
    source_video = next(
        (s for s in (pr.get("streams") or []) if s.get("track") == "video"),
        {},
    )
    logger.info(
        "hls decision: codec=%s profile=%s width=%s bitDepth=%s hdr=%s dovi=%s "
        "transfer=%s clientVideoCodecs=%s maxWidth=%s action=%s",
        source_video.get("codec"),
        source_video.get("profile"),
        source_video.get("width"),
        source_video.get("bitDepth"),
        bool(source_video.get("isHdr")),
        bool(source_video.get("isDoVi")),
        source_video.get("colorTransfer"),
        ",".join(videoCodecs or ["h264"]),
        maxWidth,
        (dec.get("video") or {}).get("action"),
    )
    # The fingerprint decision historically carried only the selected primary audio action. Preserve
    # the full probed stream inventory as private converter metadata so HLS can expose alternate
    # audio and text-subtitle renditions without changing the public fingerprint contract.
    dec["_streams"] = list(pr.get("streams") or [])
    # A hardware transcoder can consume an incomplete torrent much faster than playback time,
    # outrunning the swarm and repeatedly stalling on the next missing piece. Pace only that case.
    # Complete/cache-backed media keeps the normal faster-than-realtime HLS warm-up behaviour.
    dec["_realtimeInput"] = _torrent_input_is_incomplete(request, mediaURL)
    try:
        d = conv.ensure_job(job_id, media, dec)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid job id") from e
    registry = _playback_registry(request)
    parsed_source = parse_stream_url(mediaURL)
    if registry is not None and parsed_source is not None:
        registry.register_hls_job(
            job_id,
            parsed_source[0],
            parsed_source[1],
            request.headers.get("User-Agent"),
            conv.workload_for_job(job_id),
        )
    master_path = d / "master.m3u8"
    if not _wait_file(master_path, 25):
        raise HTTPException(status_code=504, detail="transcode did not start")
    try:
        master_text = master_path.read_text(encoding="utf-8")
    except OSError as e:
        raise HTTPException(status_code=500, detail="failed to read master playlist") from e
    body = _master_with_subtitles(master_text, pr, mediaURL)
    tracks = _subtitle_streams(pr)
    logger.debug(
        "subtitle trace: stage=master method=%s tracks=%s advertised=%s",
        request.method,
        len(tracks),
        body.count("#EXT-X-MEDIA:TYPE=SUBTITLES"),
    )
    return Response(content=body, media_type=_M3U8)


def _hls_mpegts_start(conv, job_id: str) -> int:
    """Return the MPEG-TS clock at HLS timeline zero (90 kHz), derived from this workload."""
    try:
        master = conv.job_file(job_id, "master.m3u8")
        if not _wait_file(master, 5):
            return 0
        variants = [line.strip() for line in master.read_text(encoding="utf-8").splitlines()
                    if line.strip() and not line.startswith("#")]
        if not variants:
            return 0
        playlist = conv.job_file(job_id, variants[0])
        if not _wait_file(playlist, 5):
            return 0
        segments = [line.strip() for line in playlist.read_text(encoding="utf-8").splitlines()
                    if line.strip() and not line.startswith("#")]
        if not segments:
            return 0
        segment = conv.job_file(job_id, segments[0])
        if not _wait_file(segment, 5):
            return 0
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=start_time",
             "-of", "default=nw=1:nk=1", str(segment)],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if proc.returncode != 0:
            return 0
        seconds = float(proc.stdout.strip())
        return max(0, round(seconds * 90000))
    except (OSError, ValueError, subprocess.SubprocessError):
        logger.debug("unable to derive HLS MPEG-TS start", exc_info=True)
        return 0


@router.api_route("/{job_id}/subtitles/{track:int}.m3u8", methods=["GET", "HEAD"])
def subtitle_playlist(job_id: str, track: int, request: Request, mediaURL: str, duration: float = 0.0):
    conv = _converter(request)
    if conv is None:
        raise HTTPException(status_code=503, detail="transcoder unavailable")
    # Mark subtitle playlist traffic as playback activity so the A/V transcode is not reaped while a
    # browser is actively consuming the subtitle rendition.
    conv.touch(job_id)
    mpegts_start = _hls_mpegts_start(conv, job_id)
    body = _subtitle_media_playlist(mediaURL, track, duration, mpegts_start)
    logger.debug(
        "subtitle trace: stage=playlist method=%s track=%s",
        request.method,
        track,
    )
    return Response(content=body, media_type=_M3U8)


@router.get("/{job_id}/destroy")
def destroy(job_id: str, request: Request) -> dict:
    conv = _converter(request)
    if conv is not None:
        try:
            conv.stop(job_id)
        except ValueError as e:
            # This route deletes a directory, so a malformed id is refused rather than ignored.
            raise HTTPException(status_code=400, detail="invalid job id") from e
    registry = _playback_registry(request)
    if registry is not None:
        registry.end_hls(job_id)
    return {"ok": True}


@router.api_route("/{job_id}/{filename}", methods=["GET", "HEAD"])
def serve_file(job_id: str, filename: str, request: Request):
    conv = _converter(request)
    if conv is None:
        raise HTTPException(status_code=503, detail="transcoder unavailable")
    try:
        path = conv.job_file(job_id, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid job path") from e
    # A request for a segment or a playlist is the only evidence this server ever gets that anyone
    # is still watching: ffmpeg keeps encoding whether or not the output is being read. Recorded
    # before the wait below, so a client blocked on a segment that has not been written yet still
    # counts as present.
    conv.touch(job_id)
    registry = _playback_registry(request)
    if registry is not None:
        registry.touch_hls(job_id, request.headers.get("User-Agent"))
    is_playlist = filename.endswith(".m3u8")
    if not _wait_file(path, 25 if is_playlist else 35):
        raise HTTPException(status_code=404, detail="segment not found")
    if is_playlist:
        return FileResponse(path, media_type=_M3U8)
    if filename.endswith(".vtt"):
        media_type = "text/vtt"
    elif filename.endswith(".ts"):
        media_type = "video/mp2t"
    elif filename.endswith(".mp4"):
        media_type = "video/mp4"
    else:
        media_type = "video/iso.segment"
    return FileResponse(path, media_type=media_type)
