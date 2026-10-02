"""Stremio hlsv2 transcode API: probe, master/media playlists, fMP4 segments.

The master playlist references child URIs we serve, so internal naming need not match the stock
server byte-for-byte — the player follows whatever URIs we publish.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

from stremiosrv.transcode.fingerprint import decide
from stremiosrv.transcode.probe import ProbeTimeoutError, probe_media

router = APIRouter(prefix="/hlsv2")

_M3U8 = "application/vnd.apple.mpegurl"
_ADMIN_CONFIG = os.getenv("STREMIOSRV_EXTERNAL_CONFIG", "/config/admin-settings.json")


def _admin_settings() -> dict:
    try:
        with open(_ADMIN_CONFIG, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _codec_list(value, fallback: list[str]) -> list[str]:
    if isinstance(value, str):
        codecs = [item.strip().lower() for item in value.split(",") if item.strip()]
    elif isinstance(value, (list, tuple, set)):
        codecs = [str(item).strip().lower() for item in value if str(item).strip()]
    else:
        codecs = []
    return codecs or list(fallback)


def _effective_codecs(client_codecs: list[str], server_codecs: list[str], fallback: list[str]) -> list[str]:
    client = {str(c).strip().lower() for c in (client_codecs or fallback) if str(c).strip()}
    server = {str(c).strip().lower() for c in (server_codecs or fallback) if str(c).strip()}
    return sorted(client & server)


def _converter(request: Request):
    return getattr(request.app.state, "converter", None)


def _wait_file(path: Path, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists() and path.stat().st_size > 0:
            return True
        time.sleep(0.2)
    return path.exists()


def _probe_or_504(media_url: str) -> dict:
    try:
        return probe_media(media_url)
    except ProbeTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc


@router.api_route("/probe", methods=["GET", "HEAD"])
def probe(mediaURL: str) -> dict:
    return _probe_or_504(mediaURL)


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
    pr = _probe_or_504(mediaURL)
    admin = _admin_settings()
    server_video = _codec_list(admin.get("transcoding_direct_video_codecs"), ["h264"])
    server_audio = _codec_list(admin.get("transcoding_direct_audio_codecs"), ["aac"])
    effective_video = _effective_codecs(videoCodecs, server_video, ["h264"])
    effective_audio = _effective_codecs(audioCodecs, server_audio, ["aac"])
    dec = decide(pr, effective_video, effective_audio, maxAudioChannels, maxWidth)
    try:
        d = conv.ensure_job(job_id, mediaURL, dec)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid job id") from e
    if not _wait_file(d / "master.m3u8", 25):
        raise HTTPException(status_code=504, detail="transcode did not start")
    return FileResponse(d / "master.m3u8", media_type=_M3U8)


@router.get("/{job_id}/destroy")
def destroy(job_id: str, request: Request) -> dict:
    conv = _converter(request)
    if conv is not None:
        try:
            conv.stop(job_id)
        except ValueError as e:
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
    conv.touch(job_id)
    is_playlist = filename.endswith(".m3u8")
    if not _wait_file(path, 25 if is_playlist else 35):
        raise HTTPException(status_code=404, detail="segment not found")
    if is_playlist:
        return FileResponse(path, media_type=_M3U8)
    media_type = "video/mp4" if filename.endswith(".mp4") else "video/iso.segment"
    return FileResponse(path, media_type=media_type)
