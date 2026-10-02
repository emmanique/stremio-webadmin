from fastapi.testclient import TestClient

from stremiosrv.api.subs import parse_stream_url
from stremiosrv.app import create_app


def test_parse_stream_url():
    assert parse_stream_url("https://h:12470/" + "a" * 40 + "/6?") == ("a" * 40, 6)
    assert parse_stream_url("/tmp/movie.mkv") is None


def test_opensub_hash_null_for_unresolvable_url():
    # a stream URL with no engine -> {"error": null, "result": null}, NOT a 500
    c = TestClient(create_app())
    r = c.get("/opensubHash", params={"videoUrl": "https://h:12470/" + "a" * 40 + "/6"})
    assert r.status_code == 200
    assert r.json() == {"error": None, "result": None}


def test_opensub_hash_route(tmp_path):
    p = tmp_path / "v.bin"
    p.write_bytes(b"\x00" * (2 * 65536))  # 128 KiB zeros -> filesize hash
    c = TestClient(create_app())
    r = c.get("/opensubHash", params={"videoUrl": str(p)})
    assert r.status_code == 200
    # Stock-server envelope: result carries BOTH the hash AND the byte size. OpenSubtitles matches on
    # moviehash + moviebytesize, so a bare hash (no size) silently breaks OpenSubtitles-addon matching.
    assert r.json() == {"error": None, "result": {"size": 131072, "hash": "0000000000020000"}}


def test_opensub_hash_requires_source():
    c = TestClient(create_app())
    r = c.get("/opensubHash")
    assert r.status_code == 422


def test_casting_returns_empty_list():
    c = TestClient(create_app())
    r = c.get("/casting")
    assert r.status_code == 200
    assert r.json() == []


# --- /subtitleSignature: stremio-video >= 0.0.93 calls this at every load whose probe does not rule
# out an embedded subtitle track. We answer the envelope with a null signature on purpose — the
# reference server.js v4.21.1 has no such route (404) and nothing upstream consumes the value, so
# there is no algorithm to implement and a made-up string would be *used* the day a consumer ships.


def test_subtitle_signature_envelope():
    """The exact shape stremio-video parses: resp.error falsy, resp.result.signature present."""
    c = TestClient(create_app())
    r = c.get("/subtitleSignature", params={"videoUrl": "http://x/y"})
    assert r.status_code == 200
    b = r.json()
    assert b["error"] is None
    assert b["result"] == {"signature": None}


def test_subtitle_signature_maps_to_null_in_the_client():
    """Mirror of fetchEmbeddedSubtitleSignature's own expression, so the contract is asserted the
    way the client evaluates it rather than the way we happen to serialise it."""
    c = TestClient(create_app())
    b = c.get("/subtitleSignature", params={"videoUrl": "http://x/y"}).json()
    signature = b["result"]["signature"] if b.get("result") and isinstance(
        b["result"].get("signature"), str) else None
    assert signature is None


def test_subtitle_signature_accepts_the_container_hint():
    c = TestClient(create_app())
    r = c.get("/subtitleSignature", params={"videoUrl": "http://x/y", "container": "matroska,webm"})
    assert r.status_code == 200


def test_subtitle_signature_requires_video_url():
    c = TestClient(create_app())
    assert c.get("/subtitleSignature").status_code == 422


def test_subtitle_signature_never_probes():
    """The reason it is cheap. probe_media() shells out to ffprobe uncached, and this is called at
    playback start on the box that is serving the stream."""
    import stremiosrv.api.subs as subs_api

    calls = []
    original = subs_api.probe_media
    subs_api.probe_media = lambda *a, **k: calls.append(a) or {"format": {}, "streams": []}
    try:
        TestClient(create_app()).get("/subtitleSignature", params={"videoUrl": "http://x/y"})
    finally:
        subs_api.probe_media = original
    assert calls == []


def test_subtitle_signature_is_counted():
    from stremiosrv import metrics

    metrics.reset()
    c = TestClient(create_app())
    c.get("/subtitleSignature", params={"videoUrl": "http://x/y"})
    c.get("/subtitleSignature", params={"videoUrl": "http://x/z"})
    c.get("/subtitleSignature")  # 422, not an ask we could answer
    assert metrics.playback_stats()["subtitleSignatureAsks"] == 2
    metrics.reset()


def test_subtitle_signature_does_not_shadow_other_routes():
    """One-segment literal, registered in the same router as /subtitles.{ext} and after the
    /{info_hash}/... routes. Assert the neighbours still resolve to themselves."""
    c = TestClient(create_app())
    assert c.get("/subtitleSignature", params={"videoUrl": "http://x/y"}).json()["result"] == {
        "signature": None}
    # /subtitles.srt still reaches the proxy route (422 = its own validation, not a 404/mismatch)
    assert c.get("/subtitles.srt").status_code in (422, 400)
    assert c.get("/opensubHash").status_code == 422


def test_subtitles_list_answers_its_empty_shape_when_the_probe_times_out(monkeypatch, caplog):
    """The player asks for this on every playback and it has an ordinary answer for "no tracks",
    so a slow ffprobe must not make it a 500. It is still logged: an empty list for a file that
    does have subtitles is otherwise a silent wrong answer."""
    import logging

    from stremiosrv.api import subs as subs_api
    from stremiosrv.transcode.probe import ProbeTimeoutError

    def _times_out(url):
        raise ProbeTimeoutError("ffprobe did not answer within 30s")

    monkeypatch.setattr(subs_api, "probe_media", _times_out)
    c = TestClient(create_app())
    with caplog.at_level(logging.WARNING):
        r = c.get("/" + "a" * 40 + "/0/subtitles.json", params={"mediaURL": "http://x/y"})
    assert r.status_code == 200
    assert r.json() == {"subtitles": []}
    assert "timed out" in caplog.text


def test_subtitles_vtt_uses_same_global_track_id_as_subtitles_list(monkeypatch):
    import io
    from stremiosrv.api import subs as subs_api

    monkeypatch.setattr(
        subs_api,
        "probe_media",
        lambda url: {
            "format": {"name": "matroska,webm", "duration": 10},
            "streams": [
                {"id": 0, "index": 0, "track": "video", "codec": "hevc"},
                {"id": 1, "index": 1, "track": "audio", "codec": "aac", "lang": "eng"},
                {"id": 31, "index": 31, "track": "subtitle", "codec": "subrip", "lang": "por"},
            ],
            "samples": {},
        },
    )

    calls = []

    class _Proc:
        def __init__(self, argv, **kwargs):
            calls.append((argv, kwargs))
            self.stdout = io.BytesIO(
                b"WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nOla.\n"
            )
            self._returncode = None

        def wait(self, timeout=None):
            self._returncode = 0
            return 0

        def poll(self):
            return self._returncode

        def terminate(self):
            self._returncode = 0

        def kill(self):
            self._returncode = -9

    monkeypatch.setattr(subs_api.subprocess, "Popen", _Proc)

    c = TestClient(create_app())
    listed = c.get("/" + "a" * 40 + "/0/subtitles.json", params={"mediaURL": "http://media"})
    assert listed.status_code == 200
    assert listed.json()["subtitles"] == [
        {"id": 31, "track": 31, "codec": "subrip", "lang": "por"}
    ]

    extracted = c.get(
        "/" + "a" * 40 + "/0/subtitles.vtt",
        params={"mediaURL": "http://media", "track": 31},
    )
    assert extracted.status_code == 200
    assert extracted.text.startswith("WEBVTT")
    argv, kwargs = calls[0]
    assert ["-map", "0:31"] == argv[argv.index("-map"):argv.index("-map") + 2]
    assert "0:s:31" not in argv
    assert kwargs["bufsize"] == 0


def test_subtitles_vtt_invalid_global_track_returns_controlled_404(monkeypatch):
    from stremiosrv.api import subs as subs_api

    monkeypatch.setattr(
        subs_api,
        "probe_media",
        lambda url: {
            "format": {},
            "streams": [
                {"id": 0, "index": 0, "track": "video", "codec": "h264"},
                {"id": 2, "index": 2, "track": "subtitle", "codec": "subrip", "lang": "eng"},
            ],
            "samples": {},
        },
    )

    c = TestClient(create_app())
    r = c.get(
        "/" + "a" * 40 + "/0/subtitles.vtt",
        params={"mediaURL": "http://media", "track": 31},
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "subtitle track not found"


def test_subtitles_vtt_probe_timeout_is_controlled_504(monkeypatch):
    from stremiosrv.api import subs as subs_api
    from stremiosrv.transcode.probe import ProbeTimeoutError

    def _times_out(url):
        raise ProbeTimeoutError("slow")

    monkeypatch.setattr(subs_api, "probe_media", _times_out)

    c = TestClient(create_app())
    r = c.get(
        "/" + "a" * 40 + "/0/subtitles.vtt",
        params={"mediaURL": "http://media", "track": 31},
    )
    assert r.status_code == 504
    assert r.json()["detail"] == "subtitle probe timed out"
