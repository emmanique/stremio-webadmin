"""Simple, runtime-verified transcoding profiles for WebAdmin.

Profiles are offered only after real FFmpeg tests in the running streaming
server container. Compiled encoder names are never treated as proof that a GPU
pipeline is usable.
"""
from __future__ import annotations

import shlex
import time
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

import transcoding_runtime_fix as base

app = base.app
legacy = base.base.legacy
STATIC = Path(__file__).with_name("static")
PROFILE_CACHE: dict[str, object] = {"at": 0.0, "value": None}

PROFILE_META = {
    "preserve": {
        "label": "Preserve Stremio decision",
        "encoder": None,
        "engine": "core",
        "decode": "core",
        "codec": "unchanged",
        "description": "No encoder override. Stremio keeps full control.",
    },
    "vaapi-h264": {
        "label": "H.264 VAAPI — GPU encode only",
        "encoder": "h264_vaapi",
        "engine": "vaapi",
        "decode": "software",
        "codec": "H.264",
        "description": "Software decode, Intel/DRM VAAPI H.264 encode. Direct Stream remains direct.",
    },
    "vaapi-hevc": {
        "label": "HEVC VAAPI — GPU encode only",
        "encoder": "hevc_vaapi",
        "engine": "vaapi",
        "decode": "software",
        "codec": "HEVC",
        "description": "Software decode, Intel/DRM VAAPI HEVC encode. Direct Stream remains direct.",
    },
    "vaapi-full-h264": {
        "label": "H.264 VAAPI — Full GPU",
        "encoder": "h264_vaapi",
        "engine": "vaapi",
        "decode": "vaapi",
        "codec": "H.264",
        "description": "VAAPI hardware decode and H.264 hardware encode; frames remain on the GPU.",
    },
    "vaapi-full-hevc": {
        "label": "HEVC VAAPI — Full GPU",
        "encoder": "hevc_vaapi",
        "engine": "vaapi",
        "decode": "vaapi",
        "codec": "HEVC",
        "description": "VAAPI hardware decode and HEVC hardware encode; frames remain on the GPU.",
    },
    "nvenc-h264": {
        "label": "H.264 NVIDIA NVENC",
        "encoder": "h264_nvenc",
        "engine": "nvenc",
        "decode": "software",
        "codec": "H.264",
        "description": "Software decode, NVIDIA NVENC H.264 encode. Selectable only after the real encoder test passes.",
    },
    "nvenc-hevc": {
        "label": "HEVC NVIDIA NVENC",
        "encoder": "hevc_nvenc",
        "engine": "nvenc",
        "decode": "software",
        "codec": "HEVC",
        "description": "Software decode, NVIDIA NVENC HEVC encode. Selectable only after the real encoder test passes.",
    },
    "cpu-h264": {
        "label": "H.264 CPU (libx264)",
        "encoder": "libx264",
        "engine": "cpu",
        "decode": "software",
        "codec": "H.264",
        "description": "Software decode and libx264 encode.",
    },
    "cpu-hevc": {
        "label": "HEVC CPU (libx265)",
        "encoder": "libx265",
        "engine": "cpu",
        "decode": "software",
        "codec": "HEVC",
        "description": "Software decode and libx265 encode.",
    },
}


class ProfileBody(BaseModel):
    profile: str
    quality: int = Field(default=22, ge=0, le=51)


def _exec(container, argv: list[str]):
    try:
        return container.exec_run(argv)
    except Exception:
        return None


def _selected() -> tuple[str, int]:
    config = legacy.read_config()
    profile = str(config.get("transcoding_profile") or "").strip().lower()
    if profile not in PROFILE_META:
        profile = "legacy"
    try:
        quality = max(0, min(51, int(config.get("transcoding_video_quality", 22))))
    except (TypeError, ValueError):
        quality = 22
    return profile, quality


def _result(profile_id: str, available: bool, reason: str, verified: bool = True) -> dict[str, object]:
    return {
        **PROFILE_META[profile_id],
        "id": profile_id,
        "available": available,
        "verified": verified,
        "reason": reason,
    }


def _last_error(result) -> str:
    if result is None or not result.output:
        return "runtime self-test failed"
    raw = result.output.decode("utf-8", errors="replace").strip()
    return raw.splitlines()[-1][:220] if raw else "runtime self-test failed"


def _test_full_vaapi(container, profile_id: str, device: str, binary: str) -> dict[str, object]:
    """Verify both H.264 and HEVC VAAPI decode followed by the selected VAAPI encoder."""
    encoder = str(PROFILE_META[profile_id]["encoder"])
    b = shlex.quote(binary)
    d = shlex.quote(device)
    e = shlex.quote(encoder)
    script = f"""
set -eu
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
{b} -hide_banner -loglevel error -f lavfi -i testsrc2=size=128x72:rate=24 -frames:v 3 -c:v libx264 -preset ultrafast -pix_fmt yuv420p "$work/h264.mp4"
{b} -hide_banner -loglevel error -f lavfi -i testsrc2=size=128x72:rate=24 -frames:v 3 -c:v libx265 -preset ultrafast -pix_fmt yuv420p "$work/hevc.mp4"
for input in "$work/h264.mp4" "$work/hevc.mp4"; do
  {b} -hide_banner -loglevel error -hwaccel vaapi -hwaccel_device {d} -hwaccel_output_format vaapi -i "$input" -frames:v 1 -vf scale_vaapi=format=nv12 -c:v {e} -f null -
done
"""
    result = _exec(container, ["sh", "-lc", script])
    ok = bool(result is not None and result.exit_code == 0)
    if ok:
        return _result(profile_id, True, "Full GPU test passed: H.264 decode + HEVC decode + VAAPI encode.")
    return _result(profile_id, False, _last_error(result))


def _test_profile(container, profile_id: str, device: str, binary: str | None) -> dict[str, object]:
    meta = PROFILE_META[profile_id]
    if profile_id == "preserve":
        return _result(profile_id, True, "No encoder required.")
    if not binary:
        return _result(profile_id, False, "FFmpeg binary not available.", verified=False)

    encoder = str(meta["encoder"])
    if meta["engine"] == "vaapi":
        if not base._exists(container, device):
            return _result(profile_id, False, f"{device} is not mounted.")
        if meta["decode"] == "vaapi":
            return _test_full_vaapi(container, profile_id, device, binary)
        argv = [
            binary, "-hide_banner", "-loglevel", "error",
            "-vaapi_device", device,
            "-f", "lavfi", "-i", "color=c=black:s=128x72:d=0.04",
            "-vf", "format=nv12,hwupload", "-frames:v", "1",
            "-c:v", encoder, "-f", "null", "-",
        ]
    else:
        argv = [
            binary, "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=black:s=128x72:d=0.04",
            "-frames:v", "1", "-c:v", encoder, "-f", "null", "-",
        ]

    result = _exec(container, argv)
    ok = bool(result is not None and result.exit_code == 0)
    if ok:
        reason = "One-frame encoder runtime self-test passed."
    else:
        reason = _last_error(result)
    return _result(profile_id, ok, reason)


def _recommended_profile(items: list[dict[str, object]]) -> str:
    available = {str(item.get("id")) for item in items if item.get("available")}
    for profile_id in (
        "nvenc-h264",
        "vaapi-full-h264",
        "vaapi-h264",
        "cpu-h264",
        "preserve",
    ):
        if profile_id in available:
            return profile_id
    return "preserve"


def _hardware_detection(items: list[dict[str, object]], device: str) -> dict[str, object]:
    available = {str(item.get("id")) for item in items if item.get("available")}
    if "nvenc-h264" in available or "nvenc-hevc" in available:
        accelerator = "nvenc"
        label = "NVIDIA NVENC"
        detected = True
    elif any(profile_id.startswith("vaapi-") for profile_id in available):
        accelerator = "vaapi"
        label = "VAAPI GPU (Intel/AMD DRM)"
        detected = True
    else:
        accelerator = "cpu"
        label = "CPU software encoding"
        detected = False

    return {
        "detected": detected,
        "accelerator": accelerator,
        "label": label,
        "device": device if accelerator == "vaapi" else None,
        "lxcCompatible": accelerator == "vaapi",
    }


def _profiles(force: bool = False) -> dict[str, object]:
    now = time.monotonic()
    if not force and PROFILE_CACHE["value"] is not None and now - float(PROFILE_CACHE["at"]) < 300:
        return dict(PROFILE_CACHE["value"])

    container = legacy.client().containers.get(legacy.CONTAINER)
    binary = base._ffmpeg_binary(container)
    config = legacy.read_config()
    device = str(config.get("transcoding_vaapi_device") or "/dev/dri/renderD128")
    items = [_test_profile(container, profile_id, device, binary) for profile_id in PROFILE_META]
    selected, quality = _selected()
    recommended = _recommended_profile(items)
    hardware = _hardware_detection(items, device)
    value = {
        "checkedAt": datetime.now(UTC).isoformat(),
        "selected": selected,
        "quality": quality,
        "device": device,
        "ffmpeg": binary,
        "profiles": items,
        "recommendedProfile": recommended,
        "hardwareDetection": hardware,
        "rule": (
            "Direct Stream remains Direct Stream. Hardware is detected from real runtime self-tests. "
            "The recommended profile is preselected when legacy settings are active, but it is only applied after operator confirmation. "
            "'GPU encode only' leaves decode on CPU; 'Full GPU' is offered only when both H.264 and HEVC hardware decode plus hardware encode pass the runtime test. No silent fallback."
        ),
    }
    PROFILE_CACHE["at"] = now
    PROFILE_CACHE["value"] = dict(value)
    return value


@app.get("/api/transcoding/profiles")
def profiles():
    return _profiles()


@app.post("/api/transcoding/profiles/refresh")
def refresh_profiles():
    return _profiles(force=True)


@app.put("/api/transcoding/profile")
def set_profile(body: ProfileBody):
    available = _profiles(force=True)
    candidates = {str(item["id"]): item for item in available["profiles"]}
    profile = body.profile.strip().lower()
    if profile not in candidates:
        raise HTTPException(400, "unknown transcoding profile")
    if not candidates[profile].get("available"):
        raise HTTPException(409, f"profile is not available: {candidates[profile].get('reason')}")
    legacy.write_config({
        "transcoding_profile": profile,
        "transcoding_video_quality": body.quality,
    })
    legacy.audit("transcoding.profile", f"profile={profile} quality={body.quality}")
    PROFILE_CACHE["at"] = 0.0
    PROFILE_CACHE["value"] = None
    return {"ok": True, "profile": profile, "quality": body.quality, "restartRequired": False}


_original_status = base.transcoding_status


def _profile_summary(profile: str, quality: int) -> str:
    if profile == "legacy":
        return "Legacy transcoding fields are present. Choose one explicit verified profile in All Configuration."
    meta = PROFILE_META[profile]
    if profile == "preserve":
        return "PRESERVE: Stremio controls copy and transcoding; this policy does not replace the video pipeline."
    decode = "VAAPI hardware" if meta["decode"] == "vaapi" else "software/CPU"
    return (
        f"{meta['label']}: Direct Stream stays direct. When Stremio requires video transcoding, "
        f"decode is {decode} and encode is explicitly {meta['encoder']} at quality {quality}. "
        "No silent fallback to another encoder."
    )


def transcoding_status():
    data = _original_status()
    if not isinstance(data, dict):
        return data
    selected, quality = _selected()
    data["executionProfile"] = {"id": selected, "quality": quality}
    data["policySummary"] = _profile_summary(selected, quality)

    cached_profiles = PROFILE_CACHE.get("value")
    if isinstance(cached_profiles, dict):
        data["verifiedProfiles"] = cached_profiles.get("profiles", [])
        data["profilesCheckedAt"] = cached_profiles.get("checkedAt")
    else:
        data["verifiedProfiles"] = []
        data["profilesCheckedAt"] = None

    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    if selected in PROFILE_META:
        meta = PROFILE_META[selected]
        policy["transcoding_mode"] = meta["codec"] if selected != "preserve" else "preserve"
        policy["transcoding_hwaccel"] = meta["engine"]
        policy["transcoding_video_codec"] = meta["encoder"] or "core"
        policy["transcoding_decode"] = meta["decode"]
        data["policy"] = policy
        if meta["engine"] in {"vaapi", "nvenc"}:
            active = data.get("active") if isinstance(data.get("active"), dict) else {}
            sessions = active.get("sessions") if isinstance(active.get("sessions"), list) else []
            mismatches = [s for s in sessions if s.get("action") == "transcoding" and s.get("engine") != meta["engine"]]
            if mismatches:
                warnings = data.get("warnings") if isinstance(data.get("warnings"), list) else []
                warnings.append(
                    f"{meta['label']} is selected but an existing transcoding job is using another engine. "
                    "Stop/restart playback so the new FFmpeg job uses the selected profile."
                )
                data["warnings"] = warnings
    return data


SCRIPT_TAG = '<script src="/transcoding-simple-config.js"></script>'


def profile_home():
    response = base.runtime_home()
    text = response.body.decode("utf-8", errors="replace")
    if SCRIPT_TAG not in text:
        text = text.replace("</body>", f"  {SCRIPT_TAG}\n</body>")
    return HTMLResponse(text, headers={"Cache-Control": "no-store"})


def profile_script():
    return FileResponse(STATIC / "transcoding-simple-config.js", media_type="application/javascript", headers={"Cache-Control": "no-store"})


def _replace_route(path: str) -> None:
    app.router.routes = [route for route in app.router.routes if getattr(route, "path", None) != path]


_replace_route("/api/transcoding/status")
app.add_api_route("/api/transcoding/status", transcoding_status, methods=["GET"])
_replace_route("/")
app.add_api_route("/", profile_home, methods=["GET"])
app.add_api_route("/transcoding-simple-config.js", profile_script, methods=["GET"])
