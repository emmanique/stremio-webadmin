"""On-the-fly HLS transcoder: one ffmpeg job per request id, fMP4 segments on disk."""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

from stremiosrv import metrics

logger = logging.getLogger("stremiosrv.transcode")


def build_hls_cmd(media_url: str, decision: dict, profile: str | None, out_dir: str | Path,
                  audio_codec: str = "aac", audio_bitrate: str = "192k") -> list[str]:
    out_dir = str(out_dir)
    v = decision.get("video", {})
    a = decision.get("audio")
    argv = ["ffmpeg", "-hide_banner", "-y"]

    if v.get("action") == "transcode":
        if profile == "nvenc-linux":
            argv += ["-hwaccel", "cuda"]
        elif profile and profile.startswith("vaapi"):
            argv += ["-hwaccel", "vaapi", "-hwaccel_output_format", "vaapi"]

    argv += ["-i", media_url, "-map", "0:v:0"]
    if a is not None:
        argv += ["-map", "0:a:0?"]

    if v.get("action") == "copy":
        argv += ["-c:v", "copy"]
    else:
        w = v.get("scale_width")
        if profile == "nvenc-linux":
            argv += ["-vf", f"scale={w}:-2:flags=lanczos,format=yuv420p" if w else "format=yuv420p",
                     "-c:v", "h264_nvenc", "-preset", "p4"]
        elif profile and profile.startswith("vaapi"):
            vf = f"scale_vaapi=w={w}:h=-2:format=nv12" if w else "scale_vaapi=format=nv12"
            argv += ["-vf", vf, "-c:v", "h264_vaapi"]
        else:
            if w:
                argv += ["-vf", f"scale={w}:-2:flags=lanczos"]
            argv += ["-c:v", "libx264", "-preset", "veryfast"]

    if a is not None:
        if a.get("action") == "copy":
            argv += ["-c:a", "copy"]
        else:
            argv += ["-c:a", audio_codec, "-ac", "2", "-b:a", audio_bitrate]

    argv += [
        "-f", "hls", "-hls_time", "4", "-hls_playlist_type", "event",
        "-hls_segment_type", "fmp4", "-hls_flags", "independent_segments",
        "-hls_fmp4_init_filename", "init.mp4",
        "-hls_segment_filename", f"{out_dir}/seg%d.m4s",
        "-master_pl_name", "master.m3u8", f"{out_dir}/index.m3u8",
    ]
    return argv


class Converter:
    STOP_TIMEOUT = 5.0

    def __init__(self, cache_root: str, profile: str | None):
        self.base = Path(cache_root) / "transcode"
        self.profile = profile
        self._jobs: dict[str, subprocess.Popen] = {}
        self._seen: dict[str, float] = {}
        self._lock = threading.Lock()

    def job_dir(self, job_id: str) -> Path:
        if not job_id or job_id in (".", "..") or "/" in job_id or chr(92) in job_id:
            raise ValueError(f"unsafe transcode job id: {job_id!r}")
        candidate = self.base / job_id
        try:
            if candidate.resolve().parent != self.base.resolve():
                raise ValueError(f"unsafe transcode job id: {job_id!r}")
        except OSError as e:
            raise ValueError(f"unresolvable transcode job id: {job_id!r}") from e
        return candidate

    def job_file(self, job_id: str, filename: str) -> Path:
        if not filename or filename in (".", "..") or "/" in filename or chr(92) in filename:
            raise ValueError(f"unsafe transcode file name: {filename!r}")
        d = self.job_dir(job_id)
        candidate = d / filename
        try:
            if candidate.resolve().parent != d.resolve():
                raise ValueError(f"unsafe transcode file name: {filename!r}")
        except OSError as e:
            raise ValueError(f"unresolvable transcode file name: {filename!r}") from e
        return candidate

    def _remove_job_dir(self, job_id: str) -> None:
        try:
            d = self.job_dir(job_id)
        except ValueError:
            return
        shutil.rmtree(d, ignore_errors=True)

    def _admin_settings(self) -> dict:
        path = os.getenv("STREMIOSRV_EXTERNAL_CONFIG", "/config/admin-settings.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def ensure_job(self, job_id: str, media_url: str, decision: dict) -> Path:
        with self._lock:
            existing = self._jobs.get(job_id)
            if existing is not None and existing.poll() is None:
                self._seen[job_id] = time.monotonic()
                return self.job_dir(job_id)
            d = self.job_dir(job_id)
            d.mkdir(parents=True, exist_ok=True)
            config = self._admin_settings()
            argv = build_hls_cmd(
                media_url,
                decision,
                self.profile,
                d,
                str(config.get("transcoding_audio_codec") or "aac"),
                str(config.get("transcoding_audio_bitrate") or "192k"),
            )
            log = open(d / "ffmpeg.log", "wb")
            self._jobs[job_id] = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=log)
            self._seen[job_id] = time.monotonic()
            metrics.record_hls_session(decision)
            return d

    def touch(self, job_id: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._seen[job_id] = time.monotonic()

    def reap_idle(self, idle_after: float) -> list[str]:
        now = time.monotonic()
        with self._lock:
            idle = [jid for jid, p in self._jobs.items()
                    if p.poll() is None and now - self._seen.get(jid, 0.0) >= idle_after]
        for job_id in idle:
            logger.info("transcode gc: no client for %.0fs, ending job %s", idle_after, job_id)
            self.stop(job_id)
        return idle

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for p in self._jobs.values() if p.poll() is None)

    def _end(self, p: subprocess.Popen | None) -> None:
        if p is None or p.poll() is not None:
            return
        p.terminate()
        try:
            p.wait(timeout=self.STOP_TIMEOUT)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=self.STOP_TIMEOUT)

    def stop(self, job_id: str) -> None:
        with self._lock:
            p = self._jobs.pop(job_id, None)
            self._seen.pop(job_id, None)
        self._end(p)
        self._remove_job_dir(job_id)

    def stop_all(self) -> None:
        with self._lock:
            jobs = list(self._jobs.items())
            self._jobs.clear()
            self._seen.clear()
        for job_id, p in jobs:
            self._end(p)
            self._remove_job_dir(job_id)

    def sweep(self, max_age: float = 0.0) -> int:
        try:
            names = os.listdir(self.base)
        except OSError:
            return 0
        with self._lock:
            live = {jid for jid, p in self._jobs.items() if p.poll() is None}
        now = time.time()
        removed: list[str] = []
        for name in names:
            if name in live:
                continue
            d = self.base / name
            try:
                if not d.is_dir():
                    continue
                if max(0.0, now - d.stat().st_mtime) < max_age:
                    continue
            except OSError:
                continue
            shutil.rmtree(d, ignore_errors=True)
            if not d.exists():
                removed.append(name)
        if removed:
            with self._lock:
                for name in removed:
                    self._jobs.pop(name, None)
                    self._seen.pop(name, None)
            logger.info("transcode gc: reclaimed %d orphaned job dir(s)", len(removed))
        return len(removed)


def run_transcode_gc(converter: Converter, interval: int = 60, max_age: int = 600,
                     idle_after: int = 300) -> None:
    if not logger.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(asctime)s [transcode] %(message)s"))
        logger.addHandler(h)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    while True:
        time.sleep(interval)
        try:
            converter.reap_idle(idle_after)
        except Exception:
            logger.exception("transcode reap failed")
        try:
            converter.sweep(max_age=max_age)
        except Exception:
            logger.exception("transcode gc pass failed")
