import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest


# vpn_admin imports docker/httpx/fastapi at module load time.
# Provide the real modules when installed; otherwise lightweight stubs are
# sufficient for testing the readiness logic in isolation.
try:
    import docker  # noqa: F401
except ImportError:
    docker = types.ModuleType("docker")
    docker.from_env = Mock()
    sys.modules["docker"] = docker

try:
    import httpx  # noqa: F401
except ImportError:
    httpx = types.ModuleType("httpx")
    sys.modules["httpx"] = httpx

try:
    import fastapi  # noqa: F401
except ImportError:
    fastapi = types.ModuleType("fastapi")

    class HTTPException(Exception):
        def __init__(self, status_code, detail):
            self.status_code = status_code
            self.detail = detail
            super().__init__(detail)

    fastapi.HTTPException = HTTPException
    sys.modules["fastapi"] = fastapi

    responses = types.ModuleType("fastapi.responses")
    responses.FileResponse = object
    responses.HTMLResponse = object
    sys.modules["fastapi.responses"] = responses

try:
    import pydantic  # noqa: F401
except ImportError:
    pydantic = types.ModuleType("pydantic")
    pydantic.BaseModel = object
    pydantic.Field = lambda *args, **kwargs: None
    sys.modules["pydantic"] = pydantic


MODULE = Path(__file__).parents[1] / "webadmin" / "vpn_admin.py"
SPEC = importlib.util.spec_from_file_location("vpn_admin_readiness_test", MODULE)
vpn_admin = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vpn_admin)


def test_wait_for_vpn_ready_waits_for_dns(monkeypatch):
    responses = iter([
        {"status": "running"},   # VPN
        {"status": "stopped"},   # DNS
        {"status": "running"},   # VPN
        {"status": "starting"},  # DNS
        {"status": "running"},   # VPN
        {"status": "running"},   # DNS
    ])

    monkeypatch.setattr(
        vpn_admin,
        "_control",
        lambda *args, **kwargs: next(responses),
    )
    monkeypatch.setattr(vpn_admin.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        vpn_admin,
        "_dns_proxy_ready",
        lambda: (True, None),
    )

    ready, detail = vpn_admin._wait_for_vpn_ready(timeout=5)

    assert ready is True
    assert detail is None


def test_wait_for_vpn_ready_requires_dns_running(monkeypatch):
    def control(method, path, **kwargs):
        if path == "/v1/vpn/status":
            return {"status": "running"}
        if path == "/v1/dns/status":
            return {"status": "stopped"}
        raise AssertionError(path)

    clock = {"value": 0.0}

    monkeypatch.setattr(vpn_admin, "_control", control)
    monkeypatch.setattr(
        vpn_admin.time,
        "monotonic",
        lambda: clock["value"],
    )
    monkeypatch.setattr(
        vpn_admin.time,
        "sleep",
        lambda seconds: clock.__setitem__(
            "value", clock["value"] + seconds
        ),
    )

    ready, detail = vpn_admin._wait_for_vpn_ready(timeout=3)

    assert ready is False
    assert "VPN status=running" in detail
    assert "DNS status=stopped" in detail


def test_connect_rejects_dns_not_ready(monkeypatch, tmp_path):
    monkeypatch.setattr(vpn_admin, "VPN_DIR", tmp_path)
    monkeypatch.setattr(vpn_admin, "ENABLED_FILE", tmp_path / "enabled")
    (tmp_path / "active_profile").write_text("cyber-test")

    monkeypatch.setattr(vpn_admin, "_container", lambda name: object())
    monkeypatch.setattr(
        vpn_admin,
        "_wait_for_vpn_ready",
        lambda timeout=60.0: (
            False,
            "VPN status=running, DNS status=stopped",
        ),
    )
    monkeypatch.setattr(vpn_admin, "_audit", lambda *args: None)

    with pytest.raises(vpn_admin.HTTPException) as exc:
        vpn_admin.connect_vpn()

    assert exc.value.status_code == 503
    assert "fully ready" in str(exc.value.detail)


def test_connect_success_requires_readiness_and_stremio(monkeypatch, tmp_path):
    monkeypatch.setattr(vpn_admin, "VPN_DIR", tmp_path)
    monkeypatch.setattr(vpn_admin, "ENABLED_FILE", tmp_path / "enabled")
    (tmp_path / "active_profile").write_text("cyber-test")

    monkeypatch.setattr(vpn_admin, "_container", lambda name: object())
    monkeypatch.setattr(
        vpn_admin,
        "_wait_for_vpn_ready",
        lambda timeout=60.0: (True, None),
    )
    monkeypatch.setattr(
        vpn_admin,
        "_wait_for_stremio_local",
        lambda timeout=30.0: (True, None),
    )
    monkeypatch.setattr(
        vpn_admin,
        "vpn_status",
        lambda: {"vpnRequested": True},
    )
    monkeypatch.setattr(vpn_admin, "_audit", lambda *args: None)

    result = vpn_admin.connect_vpn()

    assert result["ok"] is True
    assert result["detail"] is None
    assert "DNS is ready" in result["message"]


def test_reconnect_rejects_dns_not_ready(monkeypatch):
    monkeypatch.setattr(vpn_admin, "_vpn_requested", lambda: True)
    monkeypatch.setattr(vpn_admin, "_control", lambda *args, **kwargs: {})
    monkeypatch.setattr(vpn_admin.time, "sleep", lambda _: None)
    monkeypatch.setattr(vpn_admin, "_audit", lambda *args: None)
    monkeypatch.setattr(
        vpn_admin,
        "_wait_for_vpn_ready",
        lambda timeout=60.0: (
            False,
            "VPN status=running, DNS status=stopped",
        ),
    )

    with pytest.raises(vpn_admin.HTTPException) as exc:
        vpn_admin.reconnect_vpn()

    assert exc.value.status_code == 503
    assert "fully ready" in str(exc.value.detail)


def test_dns_proxy_ready_accepts_real_dns_answer(monkeypatch):
    class Result:
        exit_code = 0
        output = b"142.250.184.78\n"

    class Container:
        def exec_run(self, command):
            assert command == [
                "dig",
                "@172.30.0.10",
                "-p",
                "1053",
                "google.com",
                "+time=2",
                "+tries=1",
                "+short",
            ]
            return Result()

    monkeypatch.setattr(vpn_admin, "_container", lambda name: Container())

    ready, detail = vpn_admin._dns_proxy_ready()

    assert ready is True
    assert detail is None


def test_dns_proxy_ready_rejects_unusable_proxy(monkeypatch):
    class Result:
        exit_code = 9
        output = b";; communications error: timed out\n"

    class Container:
        def exec_run(self, command):
            return Result()

    monkeypatch.setattr(vpn_admin, "_container", lambda name: Container())

    ready, detail = vpn_admin._dns_proxy_ready()

    assert ready is False
    assert "timed out" in detail


def test_wait_for_vpn_ready_waits_for_real_dns_proxy(monkeypatch):
    control_calls = []

    def fake_control(method, path, *args, **kwargs):
        control_calls.append(path)

        if path == "/v1/vpn/status":
            return {"status": "running"}

        if path == "/v1/dns/status":
            return {"status": "running"}

        raise AssertionError(path)

    proxy_results = iter([
        (False, "DNS proxy query exited with code 9"),
        (True, None),
    ])

    monkeypatch.setattr(vpn_admin, "_control", fake_control)
    monkeypatch.setattr(
        vpn_admin,
        "_dns_proxy_ready",
        lambda: next(proxy_results),
    )
    monkeypatch.setattr(vpn_admin.time, "sleep", lambda _: None)

    ready, detail = vpn_admin._wait_for_vpn_ready(timeout=5)

    assert ready is True
    assert detail is None

    assert control_calls.count("/v1/vpn/status") == 2
    assert control_calls.count("/v1/dns/status") == 2
