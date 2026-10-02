"""Stremio hlsv2 transcode API: probe, master/media playlists, fMP4 segments.

The master playlist references child URIs we serve, so internal naming need not match the stock
server byte-for-byte — the player follows whatever URIs we publish.
"""
from __future__ import annotations

import math
import time
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response

from stremiosrv.api.subs import parse_stream_url
from stremiosrv.transcode.fingerprint import decide
from stremiosrv.transcode.probe import ProbeTimeoutError, probe_media

router = APIRouter(prefix="/hlsv2")

_M3U8 = "application/vnd.apple.mpegurl"


def _converter(request: Request):
    return getattr(request.app.state, "converter", None)


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
        seen_names[lang] = seen_names.get(lang, 0) + 1
        name = lang if seen_names[lang] == 1 else f"{lang} ({seen_names[lang]})"
        query = urlencode({"mediaURL": media_url, "duration": duration})
        uri = f"subtitles/{track}.m3u8?{query}"
        media_lines.append(
            '#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",'
            f'NAME="{_hls_quote(name)}",LANGUAGE="{_hls_quote(lang)}",'
            f'AUTOSELECT=YES,DEFAULT=NO,FORCED=NO,URI="{_hls_quote(uri)}"'
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


def _subtitle_media_playlist(media_url: str, track: int, duration: float) -> str:
    parsed = parse_stream_url(media_url)
    if parsed is None:
        raise HTTPException(status_code=400, detail="subtitle mediaURL is not a server stream URL")
    info_hash, idx = parsed
    duration = max(float(duration or 0.0), 0.001)
    target = max(1, math.ceil(duration))
    query = urlencode({"mediaURL": media_url, "track": track})
    vtt_uri = f"/{info_hash}/{idx}/subtitles.vtt?{query}"
    return (
        "#EXTM3U\n"
        "#EXT-X-VERSION:3\n"
        f"#EXT-X-TARGETDURATION:{target}\n"
        "#EXT-X-MEDIA-SEQUENCE:0\n"
        f"#EXTINF:{duration:.3f},\n"
        f"{vtt_uri}\n"
        "#EXT-X-ENDLIST\n"
    )


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
def probe(mediaURL: str) -> dict:
    try:
        return probe_media(mediaURL)
    except ProbeTimeoutError as e:
        raise HTTPException(status_code=504, detail="probe timed out") from e


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
    try:
        pr = probe_media(mediaURL)
    except ProbeTimeoutError as e:
        raise HTTPException(status_code=504, detail="probe timed out") from e
    dec = decide(pr, videoCodecs or ["h264"], audioCodecs or ["aac"], maxAudioChannels, maxWidth)
    # The fingerprint decision historically carried only the selected primary audio action. Preserve
    # the full probed stream inventory as private converter metadata so HLS can expose alternate
    # audio and text-subtitle renditions without changing the public fingerprint contract.
    dec["_streams"] = list(pr.get("streams") or [])
    try:
        d = conv.ensure_job(job_id, mediaURL, dec)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid job id") from e
    master_path = d / "master.m3u8"
    if not _wait_file(master_path, 25):
        raise HTTPException(status_code=504, detail="transcode did not start")
    try:
        master_text = master_path.read_text(encoding="utf-8")
    except OSError as e:
        raise HTTPException(status_code=500, detail="failed to read master playlist") from e
    body = _master_with_subtitles(master_text, pr, mediaURL)
    return Response(content=body, media_type=_M3U8)


@router.api_route("/{job_id}/subtitles/{track:int}.m3u8", methods=["GET", "HEAD"])
def subtitle_playlist(job_id: str, track: int, request: Request, mediaURL: str, duration: float = 0.0):
    conv = _converter(request)
    if conv is None:
        raise HTTPException(status_code=503, detail="transcoder unavailable")
    # Mark subtitle playlist traffic as playback activity so the A/V transcode is not reaped while a
    # browser is actively consuming the subtitle rendition.
    conv.touch(job_id)
    body = _subtitle_media_playlist(mediaURL, track, duration)
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
