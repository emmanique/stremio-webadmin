"""Probe a media URL with ffprobe and map to the Stremio streaming-server probe shape.

`map_probe` is pure (dict -> dict) so it's unit-testable without ffprobe; `probe_media` shells out.
Captured contract: {format:{name,duration}, streams:[{id,index,track,codec,width,height,frameRate,
isHdr,isDoVi,hasBFrames,channels}], samples:{}}.
"""
from __future__ import annotations

import json
import subprocess
from urllib.parse import urlsplit, urlunsplit

_HDR_TRANSFERS = {"smpte2084", "arib-std-b67"}  # PQ (HDR10/HDR10+) and HLG
_DOVI_TAGS = {"dvhe", "dvh1", "dav1", "dvav"}
_TRUSTED_SELF_SUFFIX = ".519b6502d940.stremio.rocks"


class ProbeTimeoutError(TimeoutError):
    """Raised when ffprobe cannot obtain enough media data before its deadline."""


def _internal_media_url(media_url: str) -> str:
    """Bypass the public HTTPS/Nginx hairpin when probing this same server."""
    try:
        parsed = urlsplit(media_url)
    except ValueError:
        return media_url
    host = (parsed.hostname or "").lower()
    if parsed.scheme == "https" and parsed.port == 12470 and host.endswith(_TRUSTED_SELF_SUFFIX):
        return urlunsplit(("http", "127.0.0.1:11470", parsed.path, parsed.query, parsed.fragment))
    return media_url


def _fps(rate: str | None) -> float | None:
    if not rate or "/" not in rate:
        return None
    num, den = rate.split("/", 1)
    try:
        d = float(den)
        return round(float(num) / d, 3) if d else None
    except ValueError:
        return None


def _is_hdr(stream: dict) -> bool:
    if stream.get("color_transfer") in _HDR_TRANSFERS:
        return True
    return stream.get("color_primaries") == "bt2020"


def _is_dovi(stream: dict) -> bool:
    if stream.get("codec_tag_string", "").lower() in _DOVI_TAGS:
        return True
    for sd in stream.get("side_data_list", []) or []:
        kind = str(sd.get("side_data_type", "")).lower()
        if "dovi" in kind or "dolby vision" in kind:
            return True
    return False


def map_probe(ffprobe_json: dict) -> dict:
    fmt = ffprobe_json.get("format", {}) or {}
    streams: list[dict] = []
    for s in ffprobe_json.get("streams", []) or []:
        ct = s.get("codec_type")
        entry: dict = {
            "id": s.get("index"),
            "index": s.get("index"),
            "track": ct,
            "codec": s.get("codec_name"),
        }
        if ct == "video":
            entry.update(
                width=s.get("width"),
                height=s.get("height"),
                frameRate=_fps(s.get("r_frame_rate")),
                isHdr=_is_hdr(s),
                isDoVi=_is_dovi(s),
                hasBFrames=bool(s.get("has_b_frames")),
            )
        elif ct == "audio":
            entry.update(channels=s.get("channels"), lang=(s.get("tags") or {}).get("language"))
        elif ct == "subtitle":
            entry["lang"] = (s.get("tags") or {}).get("language")
        streams.append(entry)
    duration = fmt.get("duration")
    return {
        "format": {"name": fmt.get("format_name"), "duration": float(duration) if duration else 0},
        "streams": streams,
        "samples": {},
    }


def probe_media(media_url: str, ffprobe: str = "ffprobe", timeout: int = 30) -> dict:
    effective_url = _internal_media_url(media_url)
    argv = [ffprobe, "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", effective_url]
    try:
        proc = subprocess.run(argv, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise ProbeTimeoutError(
            f"media probe timed out after {timeout}s waiting for stream data"
        ) from exc
    data = json.loads(proc.stdout or b"{}")
    return map_probe(data)
