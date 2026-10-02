from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest
from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[1]
WEBADMIN_APP = ROOT / "webadmin" / "app.py"
ENTRYPOINT = ROOT / "docker" / "webadmin_entrypoint.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_write_config_is_atomic_and_readable(tmp_path, monkeypatch):
    app = _load_module("webadmin_app_config_test", WEBADMIN_APP)
    config = tmp_path / "admin-settings.json"
    monkeypatch.setattr(app, "CONFIG", config)

    persisted = app.write_config(
        {
            "cache_size": 85_899_345_920,
            "seed_on_complete": False,
            "max_streams": 4,
        }
    )

    assert persisted["cache_size"] == 85_899_345_920
    assert persisted["seed_on_complete"] is False
    assert persisted["max_streams"] == 4
    assert json.loads(config.read_text(encoding="utf-8")) == persisted
    assert not list(tmp_path.glob(".*.tmp"))


def test_entrypoint_turns_saved_values_into_stremiosrv_environment(tmp_path, monkeypatch):
    entrypoint = _load_module("webadmin_entrypoint_test", ENTRYPOINT)
    config = tmp_path / "admin-settings.json"
    config.write_text(
        json.dumps(
            {
                "cache_size": 85_899_345_920,
                "seed_on_complete": False,
                "transcode_profile": "vaapi",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("STREMIOSRV_EXTERNAL_CONFIG", str(config))
    monkeypatch.delenv("STREMIOSRV_CACHE_SIZE", raising=False)
    monkeypatch.delenv("STREMIOSRV_SEED_ON_COMPLETE", raising=False)
    monkeypatch.delenv("STREMIOSRV_TRANSCODE_PROFILE", raising=False)

    entrypoint.apply_admin_config()

    assert os.environ["STREMIOSRV_CACHE_SIZE"] == "85899345920"
    assert os.environ["STREMIOSRV_SEED_ON_COMPLETE"] == "false"
    assert os.environ["STREMIOSRV_TRANSCODE_PROFILE"] == "vaapi"


class _ExecResult:
    def __init__(self, exit_code=0, output=b""):
        self.exit_code = exit_code
        self.output = output


class _FakeContainer:
    def __init__(self, config=None):
        self.restarts = 0
        self.config = config or {}
        self.attrs = {"State": {"StartedAt": "before", "Running": True, "Status": "running"}}

    def reload(self):
        started = "after" if self.restarts else "before"
        self.attrs = {"State": {"StartedAt": started, "Running": True, "Status": "running"}}

    def restart(self, timeout=20):
        assert timeout == 20
        self.restarts += 1

    def exec_run(self, argv):
        if argv == ["cat", "/config/admin-settings.json"]:
            return _ExecResult(0, json.dumps(self.config).encode())
        if argv == ["curl", "-fsS", "http://127.0.0.1:11470/health"]:
            return _ExecResult(0, b'{"ok":true}')
        return _ExecResult(1, b"unsupported")


class _FakeContainers:
    def __init__(self, container):
        self.container = container

    def get(self, name):
        assert name == "stremio-libtorrent-server"
        return self.container


class _FakeDocker:
    def __init__(self, container):
        self.containers = _FakeContainers(container)


def test_restart_reloads_saved_configuration_and_waits_for_health(tmp_path, monkeypatch):
    app = _load_module("webadmin_app_restart_test", WEBADMIN_APP)
    config = tmp_path / "admin-settings.json"
    config.write_text('{"cache_size": 85899345920}\n', encoding="utf-8")
    container = _FakeContainer(config={"cache_size": 85899345920})

    monkeypatch.setattr(app, "CONFIG", config)
    monkeypatch.setattr(app, "client", lambda: _FakeDocker(container))
    monkeypatch.setattr(app, "_wait_for_server", lambda container=None, timeout=60.0: (True, ""))
    monkeypatch.setattr(app, "audit", lambda *args, **kwargs: None)

    result = app.restart()

    assert result["ok"] is True
    assert result["startedAtBefore"] == "before"
    assert result["startedAtAfter"] == "after"
    assert container.restarts == 1


def test_server_sees_same_persisted_configuration(monkeypatch):
    app = _load_module("webadmin_app_shared_config_test", WEBADMIN_APP)
    expected = {"cache_size": 85_899_345_920, "max_streams": 3, "seed_on_complete": True}
    container = _FakeContainer(config=expected)
    monkeypatch.setattr(app, "client", lambda: _FakeDocker(container))
    app._verify_server_config(expected)


def test_server_config_mismatch_is_rejected(monkeypatch):
    app = _load_module("webadmin_app_shared_config_mismatch_test", WEBADMIN_APP)
    container = _FakeContainer(config={"max_streams": 1})
    monkeypatch.setattr(app, "client", lambda: _FakeDocker(container))
    with pytest.raises(OSError) as exc:
        app._verify_server_config({"max_streams": 4})
    assert "does not match" in str(exc.value)


def test_wait_for_server_uses_container_local_health():
    app = _load_module("webadmin_app_local_health_test", WEBADMIN_APP)
    container = _FakeContainer()
    ok, detail = app._wait_for_server(container=container, timeout=1)
    assert ok is True
    assert detail == ""


def test_restart_refuses_corrupt_saved_configuration(tmp_path, monkeypatch):
    app = _load_module("webadmin_app_corrupt_config_test", WEBADMIN_APP)
    config = tmp_path / "admin-settings.json"
    config.write_text("{broken", encoding="utf-8")

    monkeypatch.setattr(app, "CONFIG", config)
    monkeypatch.setattr(app, "audit", lambda *args, **kwargs: None)

    with pytest.raises(HTTPException) as exc:
        app.restart()

    assert exc.value.status_code == 500
    assert "unreadable" in str(exc.value.detail)


def test_restart_verifies_persisted_configuration_after_health(tmp_path, monkeypatch):
    app = _load_module("webadmin_app_restart_verify_test", WEBADMIN_APP)
    config = tmp_path / "admin-settings.json"
    expected = {"cache_size": 85_899_345_920, "max_streams": 3}
    config.write_text(json.dumps(expected), encoding="utf-8")
    container = _FakeContainer(config=expected)

    monkeypatch.setattr(app, "CONFIG", config)
    monkeypatch.setattr(app, "client", lambda: _FakeDocker(container))
    monkeypatch.setattr(app, "_wait_for_server", lambda container=None, timeout=60.0: (True, ""))
    monkeypatch.setattr(app, "audit", lambda *args, **kwargs: None)

    result = app.restart()

    assert result["ok"] is True
    assert result["configurationVerified"] is True
    assert container.restarts == 1
