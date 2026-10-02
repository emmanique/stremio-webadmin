from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from stremiosrv.transcode.converter import build_hls_cmd


pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def _run(argv: list[str]) -> None:
    subprocess.run(argv, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=30)


def test_real_ffmpeg_writes_multiaudio_master_playlist(tmp_path: Path):
    """Release gate for the failure seen in 2.0.13.

    A var_stream_map accepted by our unit tests still failed in the real HLS muxer and produced
    only ffmpeg.log. Build a tiny real source, execute the generated command, and require an actual
    master playlist with alternate audio renditions.
    """
    source = tmp_path / "input.mkv"
    subtitle = tmp_path / "subtitle.srt"
    subtitle.write_text(
        "1\n00:00:00,000 --> 00:00:00,800\nHello\n",
        encoding="utf-8",
    )

    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=160x90:r=10:d=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=880:duration=1",
            "-f",
            "srt",
            "-i",
            str(subtitle),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-map",
            "2:a:0",
            "-map",
            "3:s:0",
            "-c:v",
            "mpeg2video",
            "-c:a",
            "aac",
            "-c:s",
            "srt",
            "-shortest",
            str(source),
        ]
    )

    out_dir = tmp_path / "hls"
    out_dir.mkdir()
    decision = {
        "video": {"action": "copy"},
        "audio": {"action": "transcode"},
        "_streams": [
            {"track": "video", "index": 0, "codec": "mpeg2video"},
            {"track": "audio", "index": 1, "codec": "aac", "lang": "eng"},
            {"track": "audio", "index": 2, "codec": "aac", "lang": "por"},
            # Present in the source but intentionally delivered by Stremio's native subtitle API.
            {"track": "subtitle", "index": 3, "codec": "subrip", "lang": "eng"},
        ],
    }
    cmd = build_hls_cmd(str(source), decision, None, out_dir)
    _run(cmd)

    master = (out_dir / "master.m3u8").read_text(encoding="utf-8")
    assert master.startswith("#EXTM3U")
    assert master.count("#EXT-X-MEDIA:TYPE=AUDIO") == 2
    assert 'GROUP-ID="group_audio"' in master
    assert 'LANGUAGE="eng"' in master
    assert 'LANGUAGE="por"' in master
    assert "#EXT-X-STREAM-INF:" in master
    assert 'AUDIO="group_audio"' in master
    assert "SUBTITLES=" not in master
    assert list(out_dir.glob("seg_*_*.ts"))
