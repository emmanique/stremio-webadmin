from webadmin.transcoding_policy_parser import parse_policy_log


def test_profile_transcode_decision():
    result = parse_policy_log(
        "[ffmpeg-policy] profile=vaapi-h264; video=libx264->h264_vaapi; decode=software; engine=vaapi\n"
    )
    assert result is not None
    assert result["profile"] == "vaapi-h264"
    assert result["upstreamVideoTarget"] == "libx264"
    assert result["targetVideo"] == "h264_vaapi"
    assert "video=libx264->h264_vaapi" in result["decision"]


def test_profile_copy_preserved():
    result = parse_policy_log("[ffmpeg-policy] profile=vaapi-h264; video=copy preserved\n")
    assert result is not None
    assert result["profile"] == "vaapi-h264"
    assert result["targetVideo"] == "copy"
    assert result["action"] == "direct-stream"


def test_unavailable_encoder_is_visible():
    result = parse_policy_log(
        "[ffmpeg-policy] profile=nvenc-h264; unavailable encoder h264_nvenc; core encoder libx264 preserved\n"
    )
    assert result is not None
    assert result["unavailableEncoder"] == "h264_nvenc"
    assert result["action"] == "fallback-preserve-core"


def test_legacy_mode_record_still_parses():
    result = parse_policy_log("[ffmpeg-policy] mode=auto video=h265->h264_vaapi, audio=eac3->aac\n")
    assert result is not None
    assert result["mode"] == "auto"
    assert "video=h265->h264_vaapi" in result["decision"]


def test_no_policy_record():
    assert parse_policy_log("ordinary ffmpeg output\n") is None
