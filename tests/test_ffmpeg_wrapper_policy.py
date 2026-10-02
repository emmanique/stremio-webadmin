from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "docker" / "ffmpeg_wrapper.py"

spec = importlib.util.spec_from_file_location("ffmpeg_wrapper", WRAPPER)
assert spec and spec.loader
wrapper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wrapper)


def test_explicit_vaapi_pipeline_is_preserved(monkeypatch):
    args = [
        "-hide_banner",
        "-init_hw_device", "vaapi=va:/dev/dri/renderD128",
        "-filter_hw_device", "va",
        "-f", "lavfi",
        "-i", "testsrc2=size=1280x720:rate=30",
        "-vf", "format=nv12,hwupload",
        "-c:v", "h264_vaapi",
        "-t", "3",
        "-f", "null", "-",
    ]
    monkeypatch.setattr(wrapper, "_available_encoders", lambda: {"h264_vaapi"})
    monkeypatch.setattr(wrapper.os.path, "exists", lambda path: True)

    transformed, decision = wrapper._apply_profile(
        args,
        "vaapi-full-h264",
        {"transcoding_vaapi_device": "/dev/dri/renderD128"},
    )

    assert transformed == args
    assert "explicit hardware pipeline preserved" in decision


def test_profile_still_rewrites_normal_transcode_command(monkeypatch):
    args = [
        "-i", "input.mkv",
        "-c:v", "libx264",
        "-f", "null", "-",
    ]
    monkeypatch.setattr(wrapper, "_available_encoders", lambda: {"h264_vaapi"})
    monkeypatch.setattr(wrapper.os.path, "exists", lambda path: True)

    transformed, decision = wrapper._apply_profile(
        args,
        "vaapi-h264",
        {"transcoding_vaapi_device": "/dev/dri/renderD128"},
    )

    assert transformed != args
    assert "h264_vaapi" in transformed
    assert "video=libx264->h264_vaapi" in decision
