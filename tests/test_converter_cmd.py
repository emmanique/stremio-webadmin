from stremiosrv.transcode.converter import build_hls_cmd

DEC_TRANSCODE = {"video": {"action": "transcode", "scale_width": 1920},
                 "audio": {"action": "transcode"}}
DEC_COPY = {"video": {"action": "copy"}, "audio": {"action": "copy"}}


def test_nvenc_hls():
    cmd = build_hls_cmd("http://x/0", DEC_TRANSCODE, "nvenc-linux", "/tmp/j")
    assert "h264_nvenc" in cmd
    assert "-hwaccel" in cmd and "cuda" in cmd
    assert any("scale=1920" in p for p in cmd)
    assert "aac" in cmd
    assert "hls" in cmd and "/tmp/j/index.m3u8" in cmd


def test_vaapi_hls():
    cmd = build_hls_cmd("http://x/0", DEC_TRANSCODE, "vaapi-renderD128", "/tmp/j")
    assert "h264_vaapi" in cmd
    assert "vaapi" in cmd
    # h264_vaapi is 8-bit only and the decoder hands it whatever the source was, so the filter has
    # to convert: a 10-bit source otherwise fails at init, with no fallback.
    assert "scale_vaapi=w=1920:h=-2:format=nv12" in cmd


def test_vaapi_hls_converts_the_pixel_format_with_nothing_to_scale():
    """The other branch. It emitted no -vf at all, so there was nowhere for the conversion to go."""
    cmd = build_hls_cmd("http://x/0", {"video": {"action": "transcode"}}, "vaapi-x", "/tmp/j")
    assert "-vf" in cmd
    assert "scale_vaapi=format=nv12" in cmd


def test_cpu_hls():
    cmd = build_hls_cmd("http://x/0", DEC_TRANSCODE, None, "/tmp/j")
    assert "libx264" in cmd


def test_copy_hls_has_no_decode_accel():
    cmd = build_hls_cmd("http://x/0", DEC_COPY, "nvenc-linux", "/tmp/j")
    assert "copy" in cmd
    assert "-hwaccel" not in cmd


def test_no_audio_stream():
    cmd = build_hls_cmd("http://x/0", {"video": {"action": "copy"}}, None, "/tmp/j")
    assert "0:a:0?" not in cmd


def test_multitrack_hls_exposes_audio_group_and_keeps_subtitles_native():
    decision = {
        "video": {"action": "transcode", "scale_width": 1920},
        "audio": {"action": "transcode"},
        "_streams": [
            {"track": "video", "index": 0, "codec": "hevc"},
            {"track": "audio", "index": 1, "codec": "eac3", "lang": "eng"},
            {"track": "audio", "index": 2, "codec": "aac", "lang": "por"},
            {"track": "subtitle", "index": 3, "codec": "subrip", "lang": "eng"},
        ],
    }
    cmd = build_hls_cmd("http://x/0", decision, "vaapi-renderD128", "/tmp/j")
    stream_map = cmd[cmd.index("-var_stream_map") + 1]
    assert "a:0,agroup:audio,default:yes,language:eng" in stream_map
    assert "a:1,agroup:audio,default:no,language:por" in stream_map
    assert "v:0,agroup:audio" in stream_map
    assert "sgroup:" not in stream_map
    assert "sname:" not in stream_map
    assert "-c:s" not in cmd
    assert "0:3?" not in cmd
    assert "-hls_subtitle_path" not in cmd
    assert "mpegts" in cmd
    assert "/tmp/j/stream_%v.m3u8" in cmd
    assert cmd.count("-map") == 3


def test_bitmap_subtitles_are_not_mapped_into_hls_audio_renditions():
    decision = {
        "video": {"action": "copy"},
        "audio": {"action": "copy"},
        "_streams": [
            {"track": "video", "index": 0, "codec": "h264"},
            {"track": "audio", "index": 1, "codec": "aac", "lang": "eng"},
            {"track": "audio", "index": 2, "codec": "aac", "lang": "por"},
            {"track": "subtitle", "index": 3, "codec": "hdmv_pgs_subtitle", "lang": "eng"},
        ],
    }
    cmd = build_hls_cmd("http://x/0", decision, None, "/tmp/j")
    stream_map = cmd[cmd.index("-var_stream_map") + 1]
    assert "sgroup:subs" not in stream_map
    assert "-c:s" not in cmd
    assert "0:3?" not in cmd


def test_single_track_path_keeps_existing_fmp4_layout():
    decision = {
        "video": {"action": "copy"},
        "audio": {"action": "copy"},
        "_streams": [
            {"track": "video", "index": 0, "codec": "h264"},
            {"track": "audio", "index": 1, "codec": "aac", "lang": "eng"},
        ],
    }
    cmd = build_hls_cmd("http://x/0", decision, None, "/tmp/j")
    assert "-var_stream_map" not in cmd
    assert "fmp4" in cmd
    assert "/tmp/j/index.m3u8" in cmd
