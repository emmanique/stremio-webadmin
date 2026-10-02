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


class _FakeContainer:
    def __init__(self):
        self.restarts = 0
        self.attrs = {"State": {"StartedAt": "before"}}

    def reload(self):
        if self.restarts:
            self.attrs = {"State": {"StartedAt": "after"}}

    def restart(self, timeout=20):
        assert timeout == 20
        self.restarts += 1


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
    container = _FakeContainer()

    monkeypatch.setattr(app, "CONFIG", config)
    monkeypatch.setattr(app, "client", lambda: _FakeDocker(container))
    monkeypatch.setattr(app, "_wait_for_server", lambda timeout=60.0: (True, ""))
    monkeypatch.setattr(app, "audit", lambda *args, **kwargs: None)

    result = app.restart()

    assert result["ok"] is True
    assert result["startedAtBefore"] == "before"
    assert result["startedAtAfter"] == "after"
    assert container.restarts == 1


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
