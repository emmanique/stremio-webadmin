"""Expose only runtime-verified transcoding capabilities to the Dashboard.

The lower telemetry layer can report encoders compiled into FFmpeg. This final
WebAdmin layer replaces those optimistic flags with the real profile self-test
results so the Dashboard never calls NVENC/VAAPI usable merely because an
encoder name exists.
"""
from __future__ import annotations

import addon_links
import transcoding_profiles as base

app = base.app
_original_status = base.transcoding_status


def _available(items: dict[str, dict[str, object]], *profile_ids: str) -> bool:
    return any(bool(items.get(profile_id, {}).get("available")) for profile_id in profile_ids)


def transcoding_status():
    data = _original_status()
    if not isinstance(data, dict):
        return data

    cached = base.PROFILE_CACHE.get("value")
    if isinstance(cached, dict):
        profiles = cached.get("profiles") if isinstance(cached.get("profiles"), list) else []
        items = {str(item.get("id")): item for item in profiles if isinstance(item, dict)}
        hardware = data.get("hardware") if isinstance(data.get("hardware"), dict) else {}
        hardware["h264Vaapi"] = _available(items, "vaapi-h264", "vaapi-full-h264")
        hardware["hevcVaapi"] = _available(items, "vaapi-hevc", "vaapi-full-hevc")
        hardware["h264Nvenc"] = _available(items, "nvenc-h264")
        hardware["hevcNvenc"] = _available(items, "nvenc-hevc")
        hardware["libx264"] = _available(items, "cpu-h264")
        hardware["libx265"] = _available(items, "cpu-hevc")
        hardware["vaapiFullH264"] = _available(items, "vaapi-full-h264")
        hardware["vaapiFullHevc"] = _available(items, "vaapi-full-hevc")
        hardware["capabilitySource"] = "runtime-profile-self-test"
        data["hardware"] = hardware
    else:
        # No runtime test has been run since WebAdmin start. Never promote a
        # compiled encoder list to a verified-ready status.
        hardware = data.get("hardware") if isinstance(data.get("hardware"), dict) else {}
        for key in ("h264Vaapi", "hevcVaapi", "h264Nvenc", "hevcNvenc", "libx264", "libx265"):
            hardware[key] = False
        hardware["capabilitySource"] = "not-tested"
        data["hardware"] = hardware

    execution = data.get("executionProfile") if isinstance(data.get("executionProfile"), dict) else {}
    profile_id = str(execution.get("id") or "")
    if profile_id in {"vaapi-full-h264", "vaapi-full-hevc"}:
        policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
        policy["transcoding_hwaccel"] = "vaapi-full"
        data["policy"] = policy
    return data


def _replace_route(path: str) -> None:
    app.router.routes = [route for route in app.router.routes if getattr(route, "path", None) != path]


_replace_route("/api/transcoding/status")
app.add_api_route("/api/transcoding/status", transcoding_status, methods=["GET"])
addon_links.install(app)
