"""CyberGhost/Gluetun control plane for the WebAdmin.

The Stremio runtime stays fail-closed behind Gluetun when compose.vpn.yaml is used.
Credentials are stored in a private Docker volume and are never returned by the API.
"""
from __future__ import annotations

import os
import re
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import docker
import httpx
from fastapi import HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

STATIC = Path(__file__).with_name("static")
STATE = Path(os.getenv("WEBADMIN_STATE", "/data"))
VPN_DIR = Path(os.getenv("VPN_CONFIG_DIR", "/vpn"))
GLUETUN_CONTAINER = os.getenv("VPN_CONTAINER", "stremio-gluetun")
STREMIO_CONTAINER = os.getenv("STREMIO_CONTAINER", "stremio-libtorrent-server")
CONTROL_URL = os.getenv("VPN_CONTROL_URL", "http://stremio-gluetun:8000").rstrip("/")
CONTROL_API_KEY = os.getenv("VPN_CONTROL_API_KEY", "")
ENABLED_FILE = VPN_DIR / "enabled"
SCRIPT_TAG = '<script src="/vpn-admin.js"></script>'
VPN_LOCK = threading.Lock()

PUBLIC_FILES = {
    "provider": "provider.txt",
    "protocol": "protocol.txt",
    "country": "country.txt",
    "hostname": "hostname.txt",
    "firewall_outbound_subnets": "firewall_outbound_subnets.txt",
}
SECRET_FILES = {
    "username": "openvpn_user",
    "password": "openvpn_password",
    "client_cert": "client.crt",
    "client_key": "client.key",
}


class VPNConfigBody(BaseModel):
    provider: str = Field(default="cyberghost", max_length=32)
    protocol: str = Field(default="udp", max_length=8)
    country: str = Field(default="", max_length=128)
    hostname: str = Field(default="", max_length=255)
    firewall_outbound_subnets: str = Field(
        default="192.168.0.0/16,10.0.0.0/8,172.30.0.0/24", max_length=512
    )
    username: str | None = Field(default=None, max_length=512)
    password: str | None = Field(default=None, max_length=2048)
    client_cert: str | None = Field(default=None, max_length=32768)
    client_key: str | None = Field(default=None, max_length=32768)
    clear_credentials: bool = False


def _docker():
    return docker.from_env(timeout=60)


def _container(name: str):
    try:
        container = _docker().containers.get(name)
        container.reload()
        return container
    except Exception:
        return None


def _env(container) -> dict[str, str]:
    if container is None:
        return {}
    values: dict[str, str] = {}
    for item in container.attrs.get("Config", {}).get("Env", []) or []:
        if "=" in item:
            key, value = item.split("=", 1)
            values[key] = value
    return values


def _secure_write(path: Path, value: str, trailing_newline: bool = False) -> None:
    VPN_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    text = value
    if trailing_newline and not text.endswith("\n"):
        text += "\n"
    tmp.write_text(text, encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def _read_text(filename: str) -> str:
    try:
        return (VPN_DIR / filename).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _vpn_requested() -> bool:
    try:
        value = ENABLED_FILE.read_text(encoding="utf-8").strip().lower()
    except OSError:
        return False
    return value in {"1", "true", "yes", "on", "enabled"}


def _set_vpn_requested(enabled: bool) -> None:
    VPN_DIR.mkdir(parents=True, exist_ok=True)
    if enabled:
        _secure_write(ENABLED_FILE, "on\n")
    else:
        try:
            ENABLED_FILE.unlink()
        except FileNotFoundError:
            pass


def _active_profile_provider() -> str | None:
    try:
        profile_id = (VPN_DIR / "active_profile").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not re.fullmatch(r"[a-z0-9_-]+", profile_id):
        return None
    try:
        data = json.loads(
            (VPN_DIR / "profiles" / profile_id / "profile.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    provider = str(data.get("provider") or "").strip().lower()
    return provider or None


def _read_public_config() -> dict[str, object]:
    gluetun = _container(GLUETUN_CONTAINER)
    env = _env(gluetun)
    defaults = {
        "provider": env.get("VPN_SERVICE_PROVIDER", "cyberghost"),
        "protocol": env.get("OPENVPN_PROTOCOL", "udp"),
        "country": env.get("SERVER_COUNTRIES", ""),
        "hostname": env.get("SERVER_HOSTNAMES", ""),
        "firewall_outbound_subnets": env.get(
            "FIREWALL_OUTBOUND_SUBNETS",
            "192.168.0.0/16,10.0.0.0/8,172.30.0.0/24",
        ),
    }
    result: dict[str, object] = {}
    for key, filename in PUBLIC_FILES.items():
        path = VPN_DIR / filename
        result[key] = _read_text(filename) if path.exists() else defaults[key]
    active_provider = _active_profile_provider()
    if active_provider:
        result["provider"] = active_provider
    result["credentials"] = {
        "username": bool(_read_text(SECRET_FILES["username"])),
        "password": bool(_read_text(SECRET_FILES["password"])),
        "clientCert": bool(_read_text(SECRET_FILES["client_cert"])),
        "clientKey": bool(_read_text(SECRET_FILES["client_key"])),
    }
    return result


def _audit(action: str, detail: str = "") -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / "admin.log").open("a", encoding="utf-8") as handle:
        handle.write(f"{datetime.now(UTC).isoformat()} action={action} {detail}\n")


def _control(method: str, path: str, payload: dict | None = None, timeout: float = 5.0):
    headers = {}
    if CONTROL_API_KEY:
        headers["X-API-Key"] = CONTROL_API_KEY
    with httpx.Client(timeout=timeout) as client:
        response = client.request(method, CONTROL_URL + path, headers=headers, json=payload)
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()


def _control_optional(path: str) -> tuple[dict | None, str | None]:
    try:
        data = _control("GET", path)
        return data if isinstance(data, dict) else {}, None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _network_stats(container) -> tuple[int, int]:
    if container is None:
        return 0, 0
    try:
        raw = container.stats(stream=False)
        networks = (raw or {}).get("networks", {}).values()
        return (
            sum(int(item.get("rx_bytes", 0) or 0) for item in networks),
            sum(int(item.get("tx_bytes", 0) or 0) for item in networks),
        )
    except Exception:
        return 0, 0


def _routing_state(gluetun, stremio) -> tuple[bool, str]:
    if gluetun is None or stremio is None:
        return False, ""
    mode = str(stremio.attrs.get("HostConfig", {}).get("NetworkMode", "") or "")
    routed = mode in {f"container:{gluetun.id}", f"container:{gluetun.name}"}
    if mode.startswith("container:") and gluetun.id.startswith(mode.split(":", 1)[1]):
        routed = True
    return routed, mode


def _runtime_settings(data: dict | None) -> dict[str, object]:
    if not isinstance(data, dict):
        return {}
    provider = data.get("provider") if isinstance(data.get("provider"), dict) else {}
    selection = (
        provider.get("server_selection")
        if isinstance(provider.get("server_selection"), dict)
        else {}
    )
    openvpn = selection.get("openvpn") if isinstance(selection.get("openvpn"), dict) else {}
    countries = selection.get("countries") if isinstance(selection.get("countries"), list) else []
    hostnames = selection.get("hostnames") if isinstance(selection.get("hostnames"), list) else []
    return {
        "provider": provider.get("name"),
        "countries": countries,
        "hostnames": hostnames,
        "protocol": "tcp" if openvpn.get("tcp") is True else "udp",
    }


def vpn_status():
    gluetun = _container(GLUETUN_CONTAINER)
    stremio = _container(STREMIO_CONTAINER)
    routed, network_mode = _routing_state(gluetun, stremio)
    requested = _vpn_requested()
    env = _env(gluetun)
    firewall_on = str(env.get("FIREWALL", "on")).lower() not in {"off", "false", "0", "no"}
    control_status, control_error = _control_optional("/v1/vpn/status") if gluetun and requested else (None, None)
    public_ip, public_error = _control_optional("/v1/publicip/ip") if gluetun and requested else (None, None)
    settings, _ = _control_optional("/v1/vpn/settings") if gluetun and requested else (None, None)
    rx, tx = _network_stats(gluetun)

    state = (gluetun.attrs.get("State", {}) if gluetun else {}) or {}
    health = state.get("Health", {}) if isinstance(state.get("Health"), dict) else {}
    vpn_state = str((control_status or {}).get("status") or ("starting" if requested else "stopped"))
    vpn_running = requested and vpn_state == "running"
    return {
        "deploymentMode": "vpn" if requested else "direct",
        "vpnRequested": requested,
        "gluetun": {
            "present": gluetun is not None,
            "running": bool(gluetun and gluetun.status == "running"),
            "dockerHealth": health.get("Status")
            or ("running" if gluetun and gluetun.status == "running" else "unavailable"),
            "vpnStatus": vpn_state,
            "publicIp": (public_ip or {}).get("public_ip"),
            "controlAvailable": control_status is not None,
            "controlError": control_error or public_error,
            "startedAt": state.get("StartedAt") if gluetun else None,
            "rxBytes": rx,
            "txBytes": tx,
        },
        "routing": {
            "stremioThroughGateway": routed,
            "stremioThroughVpn": bool(routed and vpn_running),
            "networkMode": network_mode,
            "killSwitchActive": bool(routed and requested and firewall_on),
            "failClosed": bool(routed and requested and firewall_on),
        },
        "runtime": {
            **_runtime_settings(settings),
            **({"provider": _active_profile_provider()} if _active_profile_provider() else {}),
        },
        "config": _read_public_config(),
        "limitations": {
            "portForwarding": False,
            "portForwardingMessage": "CyberGhost VPN does not provide VPN port forwarding; outbound P2P remains available.",
            "disconnectBehaviour": "VPN OFF is an intentional direct mode. If the VPN fails while enabled, direct fallback is not enabled.",
        },
        "busy": VPN_LOCK.locked(),
    }


def _validate_config(body: VPNConfigBody) -> None:
    if body.provider.lower() != "cyberghost":
        raise HTTPException(400, "this release supports CyberGhost through Gluetun/OpenVPN")
    if body.protocol.lower() not in {"udp", "tcp"}:
        raise HTTPException(400, "protocol must be udp or tcp")
    if body.country and not re.fullmatch(r"[A-Za-z0-9 .,_-]+", body.country):
        raise HTTPException(400, "country contains unsupported characters")
    if body.hostname and not re.fullmatch(r"[A-Za-z0-9.,_-]+", body.hostname):
        raise HTTPException(400, "hostname contains unsupported characters")
    if body.firewall_outbound_subnets and not re.fullmatch(
        r"[0-9A-Fa-f:.,/ ]+", body.firewall_outbound_subnets
    ):
        raise HTTPException(400, "LAN CIDRs contain unsupported characters")
    if body.client_cert:
        if "BEGIN CERTIFICATE" not in body.client_cert or "END CERTIFICATE" not in body.client_cert:
            raise HTTPException(400, "client certificate is not a PEM certificate")
    if body.client_key:
        if "PRIVATE KEY" not in body.client_key or "END " not in body.client_key:
            raise HTTPException(400, "client key is not a PEM private key")


def save_vpn_config(body: VPNConfigBody):
    _validate_config(body)
    _secure_write(VPN_DIR / PUBLIC_FILES["provider"], "cyberghost\n")
    _secure_write(VPN_DIR / PUBLIC_FILES["protocol"], body.protocol.lower() + "\n")
    _secure_write(VPN_DIR / PUBLIC_FILES["country"], body.country.strip() + "\n")
    _secure_write(VPN_DIR / PUBLIC_FILES["hostname"], body.hostname.strip() + "\n")
    _secure_write(
        VPN_DIR / PUBLIC_FILES["firewall_outbound_subnets"],
        body.firewall_outbound_subnets.strip() + "\n",
    )

    if body.clear_credentials:
        for filename in SECRET_FILES.values():
            try:
                (VPN_DIR / filename).unlink()
            except FileNotFoundError:
                pass
    else:
        if body.username:
            _secure_write(VPN_DIR / SECRET_FILES["username"], body.username.strip())
        if body.password:
            _secure_write(VPN_DIR / SECRET_FILES["password"], body.password)
        if body.client_cert:
            _secure_write(
                VPN_DIR / SECRET_FILES["client_cert"], body.client_cert.strip(), trailing_newline=True
            )
        if body.client_key:
            _secure_write(
                VPN_DIR / SECRET_FILES["client_key"], body.client_key.strip(), trailing_newline=True
            )

    _audit("vpn.config.update", f"protocol={body.protocol.lower()} country={body.country.strip()!r}")
    return {"ok": True, "config": _read_public_config(), "restartRequired": True}


def _missing_credentials() -> list[str]:
    config = _read_public_config().get("credentials", {})
    required = {
        "username": "OpenVPN username",
        "password": "OpenVPN password",
        "clientCert": "client certificate",
        "clientKey": "client private key",
    }
    return [label for key, label in required.items() if not config.get(key)]


def _wait_for_stremio_local(timeout: float = 30.0) -> tuple[bool, str | None]:
    """Prove the server remains reachable inside the shared gateway namespace."""
    deadline = time.monotonic() + timeout
    last_error: str | None = None
    while time.monotonic() < deadline:
        container = _container(STREMIO_CONTAINER)
        if container is not None:
            try:
                result = container.exec_run(["curl", "-fsS", "--max-time", "3", "http://127.0.0.1:11470/health"])
                if result.exit_code == 0:
                    return True, None
                last_error = result.output.decode("utf-8", errors="replace").strip()
            except Exception as exc:
                last_error = str(exc)
        time.sleep(1)
    return False, last_error


def _wait_for_vpn_running(timeout: float = 60.0) -> tuple[bool, str | None]:
    deadline = time.monotonic() + timeout
    last_error: str | None = None
    while time.monotonic() < deadline:
        time.sleep(1)
        try:
            status = _control("GET", "/v1/vpn/status", timeout=3)
            if status.get("status") == "running":
                return True, None
        except Exception as exc:
            last_error = str(exc)
    return False, last_error


def _dns_proxy_ready() -> tuple[bool, str | None]:
    """Prove Pi-hole can resolve DNS through the Gluetun :1053 proxy."""
    container = _container("stremio-pihole")
    if container is None:
        return False, "Pi-hole container is not available"

    try:
        result = container.exec_run(
            [
                "dig",
                "@172.30.0.10",
                "-p",
                "1053",
                "google.com",
                "+time=2",
                "+tries=1",
                "+short",
            ]
        )

        output = result.output.decode("utf-8", errors="replace").strip()

        if result.exit_code == 0 and output:
            return True, None

        return False, output or f"DNS proxy query exited with code {result.exit_code}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _wait_for_vpn_ready(timeout: float = 60.0) -> tuple[bool, str | None]:
    """Wait until the VPN, Gluetun DNS and Pi-hole DNS path are usable."""
    deadline = time.monotonic() + timeout
    last_error: str | None = None

    while time.monotonic() < deadline:
        try:
            vpn = _control("GET", "/v1/vpn/status", timeout=3)
            dns = _control("GET", "/v1/dns/status", timeout=3)

            vpn_status = str(vpn.get("status") or "")
            dns_status = str(dns.get("status") or "")

            if vpn_status == "running" and dns_status == "running":
                proxy_ok, proxy_detail = _dns_proxy_ready()

                if proxy_ok:
                    return True, None

                last_error = (
                    "VPN status=running, DNS status=running, "
                    f"DNS proxy not ready: {proxy_detail or 'query failed'}"
                )
            else:
                last_error = (
                    f"VPN status={vpn_status or 'unknown'}, "
                    f"DNS status={dns_status or 'unknown'}"
                )

        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"

        time.sleep(1)

    return False, last_error


def apply_vpn_config():
    if _container(GLUETUN_CONTAINER) is None:
        raise HTTPException(409, "VPN gateway container is not available")
    if not _vpn_requested():
        return {
            "ok": True,
            "message": "VPN configuration saved. VPN remains disabled until explicitly enabled.",
            "status": vpn_status(),
        }
    return reconnect_vpn()


def connect_vpn():
    if _container(GLUETUN_CONTAINER) is None:
        raise HTTPException(409, "VPN gateway container is not available")
    active = _read_text("active_profile")
    if not active:
        raise HTTPException(409, "select or activate a VPN connection before enabling VPN")
    if not VPN_LOCK.acquire(blocking=False):
        raise HTTPException(409, "another VPN operation is already running")
    try:
        _set_vpn_requested(True)
        _audit("vpn.enable", f"profile={active}")
        ready, detail = _wait_for_vpn_ready()
        if not ready:
            _audit("vpn.enable.failed", f"readiness={detail}")
            raise HTTPException(
                503,
                f"VPN tunnel did not become fully ready: {detail}",
            )

        local_ok, local_detail = _wait_for_stremio_local()
        if not local_ok:
            _audit("vpn.enable.failed", f"stremio-health={local_detail}")
            raise HTTPException(
                503,
                f"VPN is ready but Stremio local health failed: {local_detail}",
            )

        return {
            "ok": True,
            "message": "VPN is running and DNS is ready.",
            "detail": None,
            "status": vpn_status(),
        }
    finally:
        VPN_LOCK.release()


def disconnect_vpn():
    if _container(GLUETUN_CONTAINER) is None:
        raise HTTPException(409, "VPN gateway container is not available")
    if not VPN_LOCK.acquire(blocking=False):
        raise HTTPException(409, "another VPN operation is already running")
    try:
        if _vpn_requested():
            try:
                _control("PUT", "/v1/vpn/status", {"status": "stopped"}, timeout=10)
            except Exception:
                pass
        _set_vpn_requested(False)
        _audit("vpn.disable")
        time.sleep(2)
        local_ok, local_detail = _wait_for_stremio_local()
        if not local_ok:
            _audit("vpn.disable.failed", f"stremio-health={local_detail}")
            raise HTTPException(503, f"VPN disabled but Stremio local health failed: {local_detail}")
        return {
            "ok": True,
            "message": "VPN disabled. Gateway remains running in direct mode.",
            "status": vpn_status(),
        }
    finally:
        VPN_LOCK.release()


def reconnect_vpn():
    if not _vpn_requested():
        return connect_vpn()
    if not VPN_LOCK.acquire(blocking=False):
        raise HTTPException(409, "another VPN operation is already running")
    try:
        try:
            _control("PUT", "/v1/vpn/status", {"status": "stopped"}, timeout=10)
            time.sleep(1)
            _control("PUT", "/v1/vpn/status", {"status": "running"}, timeout=10)
        except Exception:
            # The supervisor may still be starting Gluetun; keep the persistent
            # enable request and let it converge without restarting the container.
            pass
        _audit("vpn.reconnect")
        ready, detail = _wait_for_vpn_ready(timeout=60)
        if not ready:
            _audit("vpn.reconnect.failed", f"readiness={detail}")
            raise HTTPException(
                503,
                f"VPN tunnel did not become fully ready: {detail}",
            )

        local_ok, local_detail = _wait_for_stremio_local()
        if not local_ok:
            _audit("vpn.reconnect.failed", f"stremio-health={local_detail}")
            raise HTTPException(
                503,
                f"VPN is ready but Stremio local health failed: {local_detail}",
            )

        return {
            "ok": True,
            "message": "VPN reconnected and DNS is ready.",
            "detail": None,
            "status": vpn_status(),
        }
    finally:
        VPN_LOCK.release()


def _host_public_ip() -> str | None:
    try:
        with httpx.Client(timeout=6) as client:
            response = client.get("https://api.ipify.org", params={"format": "json"})
            response.raise_for_status()
            return str(response.json().get("ip") or "") or None
    except Exception:
        return None


def _stremio_public_ip() -> str | None:
    container = _container(STREMIO_CONTAINER)
    if container is None:
        return None
    command = (
        "curl -fsS --max-time 8 https://api.ipify.org 2>/dev/null "
        "|| wget -qO- -T 8 https://api.ipify.org 2>/dev/null"
    )
    try:
        result = container.exec_run(["sh", "-c", command])
        if result.exit_code != 0:
            return None
        value = result.output.decode("utf-8", errors="replace").strip()
        return value if re.fullmatch(r"[0-9A-Fa-f:.]+", value) else None
    except Exception:
        return None


def test_vpn_protection():
    status = vpn_status()
    routed = bool(status["routing"].get("stremioThroughGateway"))
    requested = bool(status.get("vpnRequested"))
    running = status["gluetun"]["vpnStatus"] == "running"
    vpn_ip = status["gluetun"].get("publicIp")
    host_ip = _host_public_ip()
    stremio_ip = _stremio_public_ip()

    if not routed:
        result = "ROUTING-ERROR"
        protected = False
        reason = "Stremio is not sharing the persistent gateway network namespace."
        leak_blocked = False
    elif not requested:
        result = "DIRECT"
        protected = False
        reason = "VPN is intentionally disabled; Stremio is using direct Internet through the persistent gateway."
        leak_blocked = False
    elif running:
        matches_vpn = bool(stremio_ip and vpn_ip and stremio_ip == vpn_ip)
        differs_host = bool(stremio_ip and (not host_ip or stremio_ip != host_ip))
        protected = bool(matches_vpn and differs_host)
        result = "PROTECTED" if protected else "CHECK"
        reason = (
            "Stremio egress matches the VPN public IP."
            if protected
            else "Could not prove that Stremio egress matches the VPN tunnel."
        )
        leak_blocked = None
    else:
        leak_blocked = stremio_ip is None
        protected = bool(status["routing"]["killSwitchActive"] and leak_blocked)
        result = "SAFE-BLOCKED" if protected else "LEAK-RISK"
        reason = (
            "VPN is stopped and Stremio cannot reach the public Internet."
            if protected
            else "VPN is stopped but Stremio still appears to have public egress."
        )

    _audit("vpn.protection_test", f"result={result}")
    return {
        "result": result,
        "protected": protected,
        "reason": reason,
        "hostPublicIp": host_ip,
        "vpnPublicIp": vpn_ip,
        "stremioPublicIp": stremio_ip,
        "vpnRunning": running,
        "stremioThroughVpn": routed,
        "killSwitchActive": status["routing"]["killSwitchActive"],
        "killSwitchVerified": leak_blocked,
    }


def vpn_logs(lines: int = 200):
    lines = max(20, min(int(lines), 1000))
    gluetun = _container(GLUETUN_CONTAINER)
    if gluetun is None:
        return {"lines": [], "available": False}
    try:
        text = gluetun.logs(tail=lines).decode("utf-8", errors="replace")
    except Exception:
        text = ""

    for filename in ("openvpn_user", "openvpn_password"):
        secret = _read_text(filename)
        if secret:
            text = text.replace(secret, "***")
    return {"lines": text.splitlines(), "available": True}


def vpn_script():
    return FileResponse(
        STATIC / "vpn-admin.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


def _current_home(app):
    for route in reversed(app.router.routes):
        if getattr(route, "path", None) == "/" and "GET" in (
            getattr(route, "methods", set()) or set()
        ):
            return route.endpoint
    return None


def install(app) -> None:
    original_home = _current_home(app)

    def home_with_vpn():
        response = original_home() if original_home else FileResponse(STATIC / "index.html")
        body = getattr(response, "body", b"")
        if isinstance(body, (bytes, bytearray)) and body:
            text = body.decode("utf-8", errors="replace")
        else:
            try:
                text = (STATIC / "index.html").read_text(encoding="utf-8")
            except OSError:
                text = str(body or "")
        if SCRIPT_TAG not in text:
            text = text.replace("</body>", f"  {SCRIPT_TAG}\n</body>")
        return HTMLResponse(text, headers={"Cache-Control": "no-store"})

    paths = {
        "/",
        "/vpn-admin.js",
        "/api/vpn/status",
        "/api/vpn/config",
        "/api/vpn/apply",
        "/api/vpn/connect",
        "/api/vpn/disconnect",
        "/api/vpn/reconnect",
        "/api/vpn/test",
        "/api/vpn/logs",
    }
    app.router.routes = [
        route for route in app.router.routes if getattr(route, "path", None) not in paths
    ]
    app.add_api_route("/", home_with_vpn, methods=["GET"])
    app.add_api_route("/vpn-admin.js", vpn_script, methods=["GET"])
    app.add_api_route("/api/vpn/status", vpn_status, methods=["GET"])
    app.add_api_route("/api/vpn/config", _read_public_config, methods=["GET"])
    app.add_api_route("/api/vpn/config", save_vpn_config, methods=["PUT"])
    app.add_api_route("/api/vpn/apply", apply_vpn_config, methods=["POST"], status_code=202)
    app.add_api_route("/api/vpn/connect", connect_vpn, methods=["POST"])
    app.add_api_route("/api/vpn/disconnect", disconnect_vpn, methods=["POST"])
    app.add_api_route("/api/vpn/reconnect", reconnect_vpn, methods=["POST"])
    app.add_api_route("/api/vpn/test", test_vpn_protection, methods=["POST"])
    app.add_api_route("/api/vpn/logs", vpn_logs, methods=["GET"])
