from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_single_compose_owns_direct_and_vpn_runtime():
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert not (ROOT / "compose.vpn.yaml").exists()
    assert "  gluetun:" in compose
    assert 'network_mode: "service:gluetun"' in compose
    assert "STREMIO_VPN_ENABLED_FILE: /vpn/enabled" in compose
    assert "FTLCONF_dns_upstreams: \"172.30.0.10#1053\"" in compose


def test_shared_configuration_volume_remains_rw_for_webadmin_and_ro_for_server():
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "stremio-config:/config:ro" in compose
    assert "stremio-config:/config" in compose
    assert "/var/run/docker.sock:/var/run/docker.sock" in compose


def test_vpn_activation_does_not_restart_gateway_container():
    profiles = (ROOT / "webadmin" / "vpn_profiles.py").read_text(encoding="utf-8")
    vpn_admin = (ROOT / "webadmin" / "vpn_admin.py").read_text(encoding="utf-8")
    gluetun_admin = (ROOT / "webadmin" / "gluetun_admin.py").read_text(encoding="utf-8")

    assert "_set_vpn_requested(True)" in profiles
    assert "gluetun.restart(" not in profiles
    assert "gluetun.restart(" not in vpn_admin
    assert "container.stop(timeout=15)" not in gluetun_admin


def test_server_restart_path_is_still_independent_from_vpn():
    app = (ROOT / "webadmin" / "app.py").read_text(encoding="utf-8")
    assert 'client().containers.get(CONTAINER)' in app
    assert "container.restart(timeout=20)" in app
    assert '["curl", "-fsS", "http://127.0.0.1:11470/health"]' in app
    assert '["cat", "/config/admin-settings.json"]' in app


def test_shell_entrypoints_parse():
    for relative in ("start.sh", "start-vpn.sh", "vpn/entrypoint.sh"):
        result = subprocess.run(
            ["sh", "-n", str(ROOT / relative)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"{relative}: {result.stderr}"


def test_base_compose_does_not_require_vaapi_device():
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    vaapi = (ROOT / "compose.vaapi.yaml").read_text(encoding="utf-8")

    assert 'devices:' not in compose.split("  stremio-libtorrent-server:", 1)[1].split("  webadmin:", 1)[0]
    assert "${VAAPI_DEVICE:?VAAPI_DEVICE must point to a detected /dev/dri/renderD* device}" in vaapi
    assert "${VAAPI_DEVICE:-/dev/dri/renderD128}" not in vaapi



def test_blank_libva_driver_is_not_seeded_or_reinjected():
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    start = (ROOT / "start.sh").read_text(encoding="utf-8")
    vaapi = (ROOT / "compose.vaapi.yaml").read_text(encoding="utf-8")

    assert "\nLIBVA_DRIVER_NAME=\n" not in f"\n{env_example}"
    assert "# LIBVA_DRIVER_NAME=iHD" in env_example
    assert "LIBVA_DRIVER_NAME=[[:space:]]*$" in start
    assert "unset LIBVA_DRIVER_NAME" in start
    assert "- LIBVA_DRIVER_NAME" in vaapi


def test_vaapi_overlay_reports_detected_device_to_webadmin():
    vaapi = (ROOT / "compose.vaapi.yaml").read_text(encoding="utf-8")
    transcoding = (ROOT / "webadmin" / "transcoding_config.py").read_text(encoding="utf-8")

    assert "  webadmin:" in vaapi
    assert 'VAAPI_DEVICE: "' in vaapi
    assert 'os.getenv("VAAPI_DEVICE", "")' in transcoding
    assert '"transcoding_vaapi_device": "/dev/dri/renderD128"' not in transcoding


def test_vpn_status_uses_active_profile_provider():
    vpn_admin = (ROOT / "webadmin" / "vpn_admin.py").read_text(encoding="utf-8")

    assert "def _active_profile_provider()" in vpn_admin
    assert 'result["provider"] = active_provider' in vpn_admin
    assert '"provider": _active_profile_provider()' in vpn_admin



def test_vpn_admin_imports_json_for_profile_provider():
    vpn_admin = (ROOT / "webadmin" / "vpn_admin.py").read_text(encoding="utf-8")

    assert "import json" in vpn_admin
    assert "json.loads(" in vpn_admin

def test_start_repairs_stale_gluetun_namespace_after_stack_upgrade():
    start = (ROOT / "start.sh").read_text(encoding="utf-8")

    assert "_repair_gateway_namespace()" in start
    assert "stale Gluetun namespace detected" in start
    assert "--no-deps --force-recreate stremio-libtorrent-server" in start
    assert "repaired_mode" in start
    assert 'if [ "$repaired_mode" != "container:$gluetun_id" ]' in start


def test_start_does_not_recreate_server_when_gateway_namespace_is_current():
    start = (ROOT / "start.sh").read_text(encoding="utf-8")

    assert '"container:$gluetun_id")' in start
    assert 'echo "[start] gateway namespace: current"' in start
    assert "return 0" in start
