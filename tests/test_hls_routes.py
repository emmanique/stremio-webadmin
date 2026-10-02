from fastapi.testclient import TestClient

from stremiosrv.app import create_app


def test_hwaccel_profiler_default_none():
    c = TestClient(create_app())
    r = c.get("/hwaccel-profiler")
    assert r.status_code == 200
    assert r.json()["profile"] is None


def test_master_503_without_converter():
    c = TestClient(create_app())
    r = c.get("/hlsv2/abc/master.m3u8", params={"mediaURL": "http://x/0"})
    assert r.status_code == 503


def test_segment_503_without_converter():
    c = TestClient(create_app())
    r = c.get("/hlsv2/abc/seg0.m4s")
    assert r.status_code == 503


def test_non_int_idx_does_not_match_serve():
    # regression: paths like /hlsv2/probe must NOT be swallowed by playback's serve route.
    # Before pinning idx to :int this returned 422 (int_parsing); now it 404s and falls through.
    c = TestClient(create_app())
    r = c.get("/somehash/notanint")
    assert r.status_code == 404


# --- HEAD parity. FastAPI does not add HEAD to a GET route (bare Starlette does), so every hlsv2
# route answered 405 while the byte-range route answered 206. A client that probes a URL with HEAD
# before playing it saw a hard failure on the transcode path only.


def _app_client(monkeypatch):
    from fastapi.testclient import TestClient

    from stremiosrv.api import hls
    from stremiosrv.app import create_app

    monkeypatch.setattr(hls, "probe_media", lambda url: {"format": {"name": "matroska"}, "streams": []})
    return TestClient(create_app())


def test_head_is_accepted_on_probe(monkeypatch):
    c = _app_client(monkeypatch)
    r = c.head("/hlsv2/probe", params={"mediaURL": "http://x/y"})
    assert r.status_code == 200
    assert r.content == b""  # HEAD carries headers only


def test_head_matches_get_headers_on_probe(monkeypatch):
    """Same headers as GET is the actual contract — a HEAD that lies about content-type is worse
    than a 405, because the client believes it."""
    c = _app_client(monkeypatch)
    g = c.get("/hlsv2/probe", params={"mediaURL": "http://x/y"})
    h = c.head("/hlsv2/probe", params={"mediaURL": "http://x/y"})
    assert g.status_code == h.status_code == 200
    assert h.headers.get("content-type") == g.headers.get("content-type")


def test_head_is_accepted_on_the_playlist_and_segment_routes(monkeypatch):
    """Both reach their handler rather than the router's 405: no transcoder is wired in this app,
    so 503 is the handler talking. What matters is that it is not 405."""
    c = _app_client(monkeypatch)
    for path in ("/hlsv2/job1/master.m3u8", "/hlsv2/job1/video0.m4s"):
        r = c.head(path, params={"mediaURL": "http://x/y"})
        assert r.status_code != 405, path


class _FakeConv:
    def __init__(self):
        self.stopped = []
        self.touched = []

    def stop(self, job_id):
        self.stopped.append(job_id)

    def touch(self, job_id):
        self.touched.append(job_id)

    def job_dir(self, job_id):
        import pathlib

        return pathlib.Path("/nonexistent")

    def job_file(self, job_id, filename):
        return self.job_dir(job_id) / filename


def test_asking_for_a_segment_marks_the_job_as_still_being_watched(tmp_path):
    """The reaper ends transcodes nothing has read, and this route is where "read" is observed. Its
    absence is not visible in any test of the reaper itself: that would keep passing while the
    server quietly killed the encoder of a player that was watching perfectly happily.

    Real files on disk, because a missing one makes the route wait 35 seconds for a segment that is
    never coming -- correct behaviour, and a minute of it does not belong in the suite."""
    from fastapi.testclient import TestClient

    from stremiosrv.app import create_app

    (tmp_path / "seg7.m4s").write_bytes(b"x")
    (tmp_path / "index.m3u8").write_text("#EXTM3U\n")

    class Served(_FakeConv):
        def job_file(self, job_id, filename):
            return tmp_path / filename

    app = create_app()
    conv = Served()
    app.state.converter = conv
    c = TestClient(app)

    assert c.get("/hlsv2/job1/seg7.m4s").status_code == 200
    assert conv.touched == ["job1"]

    assert c.get("/hlsv2/job1/index.m3u8").status_code == 200
    assert conv.touched == ["job1", "job1"]


def test_a_malformed_job_path_is_refused_before_it_counts_as_activity():
    """Otherwise anyone who can reach the route could keep a transcode alive with nonsense ids."""
    from fastapi.testclient import TestClient

    from stremiosrv.app import create_app

    class Rejecting(_FakeConv):
        def job_file(self, job_id, filename):
            raise ValueError("unsafe")

    app = create_app()
    conv = Rejecting()
    app.state.converter = conv
    c = TestClient(app)

    assert c.get("/hlsv2/job1/..%2Fescape").status_code in (400, 404)
    assert conv.touched == []


def test_head_cannot_tear_down_a_transcode_job():
    """HEAD is defined as safe, and /destroy is the one route here whose GET has a side effect. It
    is left off the HEAD list, so a HEAD falls through to the segment route and 404s instead —
    what matters is that stop() is never reached. Asserted as behaviour, not as a status code: the
    catch-all /{job_id}/{filename} also matches this path, so the code alone would not prove it."""
    from fastapi.testclient import TestClient

    from stremiosrv.app import create_app

    app = create_app()
    conv = _FakeConv()
    app.state.converter = conv
    c = TestClient(app)

    c.head("/hlsv2/job1/destroy")
    assert conv.stopped == []          # HEAD must not destroy anything

    assert c.get("/hlsv2/job1/destroy").status_code == 200
    assert conv.stopped == ["job1"]    # ...while GET still does


# --- a probe that never answers. Both routes here need it before they can do anything, so both
# answer 504 -- the gateway timeout the playlist route already uses when a transcode won't start.


def _times_out(url):
    from stremiosrv.transcode.probe import ProbeTimeoutError

    raise ProbeTimeoutError("ffprobe did not answer within 30s")


def test_probe_answers_504_when_ffprobe_times_out(monkeypatch):
    from stremiosrv.api import hls

    monkeypatch.setattr(hls, "probe_media", _times_out)
    c = TestClient(create_app())
    assert c.get("/hlsv2/probe", params={"mediaURL": "http://x/y"}).status_code == 504


def test_the_master_playlist_answers_504_when_ffprobe_times_out(monkeypatch):
    """With a converter attached, so the 503 for a missing one cannot stand in for the answer."""
    from stremiosrv.api import hls

    monkeypatch.setattr(hls, "probe_media", _times_out)
    app = create_app()
    app.state.converter = _FakeConv()
    r = TestClient(app).get("/hlsv2/job1/master.m3u8", params={"mediaURL": "http://x/y"})
    assert r.status_code == 504


def test_master_advertises_embedded_subtitles_without_ffmpeg_subtitle_muxing():
    from stremiosrv.api.hls import _master_with_subtitles

    master = (
        "#EXTM3U\n"
        "#EXT-X-VERSION:7\n"
        '#EXT-X-STREAM-INF:BANDWIDTH=422400,CODECS="avc1.640828,mp4a.40.2"\n'
        "index.m3u8\n"
    )
    probe = {
        "format": {"duration": 6621.455},
        "streams": [
            {"index": 0, "track": "video", "codec": "hevc"},
            {"index": 1, "track": "audio", "codec": "aac", "lang": "eng"},
            {"index": 31, "track": "subtitle", "codec": "subrip", "lang": "por"},
            {"index": 32, "track": "subtitle", "codec": "subrip", "lang": "por"},
        ],
    }
    media = "https://host/" + "a" * 40 + "/0?"
    out = _master_with_subtitles(master, probe, media)

    assert out.count("#EXT-X-MEDIA:TYPE=SUBTITLES") == 2
    assert 'GROUP-ID="subs"' in out
    assert 'LANGUAGE="por"' in out
    assert 'NAME="por"' in out
    assert 'NAME="por (2)"' in out
    assert "subtitles/31.m3u8?" in out
    assert "subtitles/32.m3u8?" in out
    assert 'SUBTITLES="subs"' in out
    # Regression for 2.0.13: no FFmpeg var_stream_map subtitle-only metadata such as sname appears.
    assert "sname:" not in out


def test_subtitle_media_playlist_points_to_global_track_vtt():
    from stremiosrv.api.hls import _subtitle_media_playlist

    info_hash = "b" * 40
    media = f"https://host/{info_hash}/0?"
    out = _subtitle_media_playlist(media, 31, 6621.455)

    assert out.startswith("#EXTM3U")
    assert "#EXT-X-TARGETDURATION:6622" in out
    assert "#EXTINF:6621.455," in out
    assert f"/{info_hash}/0/subtitles.vtt?" in out
    assert "track=31" in out
    assert "#EXT-X-ENDLIST" in out


def test_subtitle_media_playlist_rejects_non_server_media_url():
    import pytest
    from fastapi import HTTPException
    from stremiosrv.api.hls import _subtitle_media_playlist

    with pytest.raises(HTTPException) as exc:
        _subtitle_media_playlist("https://example.invalid/movie.mkv", 31, 10)
    assert exc.value.status_code == 400


def test_subtitle_playlist_route_marks_job_active(monkeypatch):
    from stremiosrv.api import hls
    from stremiosrv.app import create_app

    info_hash = "c" * 40
    app = create_app()
    conv = _FakeConv()
    app.state.converter = conv
    c = TestClient(app)

    r = c.get(
        "/hlsv2/job1/subtitles/31.m3u8",
        params={"mediaURL": f"https://host/{info_hash}/0?", "duration": 42},
    )
    assert r.status_code == 200
    assert "text" not in r.headers.get("content-type", "")
    assert "#EXTM3U" in r.text
    assert "track=31" in r.text
    assert conv.touched == ["job1"]
