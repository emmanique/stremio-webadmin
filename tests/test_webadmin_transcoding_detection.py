from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webadmin"))

import transcoding_profiles as profiles  # noqa: E402


def _item(profile_id: str, available: bool) -> dict[str, object]:
    return {"id": profile_id, "available": available}


def test_recommends_full_vaapi_h264_before_encode_only_and_cpu():
    items = [
        _item("preserve", True),
        _item("vaapi-h264", True),
        _item("vaapi-full-h264", True),
        _item("cpu-h264", True),
    ]
    assert profiles._recommended_profile(items) == "vaapi-full-h264"


def test_recommends_encode_only_vaapi_when_full_pipeline_is_unavailable():
    items = [
        _item("preserve", True),
        _item("vaapi-h264", True),
        _item("vaapi-full-h264", False),
        _item("cpu-h264", True),
    ]
    assert profiles._recommended_profile(items) == "vaapi-h264"


def test_nvenc_has_priority_when_runtime_verified():
    items = [
        _item("nvenc-h264", True),
        _item("vaapi-full-h264", True),
        _item("cpu-h264", True),
    ]
    assert profiles._recommended_profile(items) == "nvenc-h264"


def test_vaapi_is_reported_as_gpu_acceleration_for_lxc_render_node():
    items = [
        _item("vaapi-h264", True),
        _item("vaapi-full-h264", False),
        _item("cpu-h264", True),
    ]
    detected = profiles._hardware_detection(items, "/dev/dri/renderD128")

    assert detected["detected"] is True
    assert detected["accelerator"] == "vaapi"
    assert detected["device"] == "/dev/dri/renderD128"
    assert detected["lxcCompatible"] is True


def test_cpu_is_reported_when_no_hardware_profile_passes():
    items = [
        _item("vaapi-h264", False),
        _item("nvenc-h264", False),
        _item("cpu-h264", True),
    ]
    detected = profiles._hardware_detection(items, "/dev/dri/renderD128")

    assert detected["detected"] is False
    assert detected["accelerator"] == "cpu"
    assert detected["device"] is None


def test_process_metadata_extracts_pid_cpu_memory_and_elapsed():
    command = "741 94.0 0.2 00:10 /usr/local/libexec/stremio/ffmpeg-real -i input.mkv -c:v copy out.m3u8"
    argv, process = profiles.base.base._process_metadata(command)
    assert argv.startswith("/usr/local/libexec/stremio/ffmpeg-real")
    assert process == {"pid": 741, "cpuPercent": 94.0, "memoryPercent": 0.2, "elapsed": "00:10"}


def test_source_codec_is_read_from_ffmpeg_log_when_policy_does_not_expose_it():
    log = """
Input #0, matroska,webm, from 'input.mkv':
  Stream #0:0: Video: hevc, yuv420p, 1920x800
  Stream #0:1: Audio: ac3, 48000 Hz, stereo
"""
    telemetry = profiles.base.base
    assert telemetry._source_codec_from_log(log, "video") == "hevc"
    assert telemetry._source_codec_from_log(log, "audio") == "ac3"
