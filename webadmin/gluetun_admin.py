"""Dedicated Gluetun management surface for WebAdmin.

This module intentionally exposes only non-secret configuration. VPN credentials,
client certificates, private keys and the Gluetun control API key are never returned
to the browser. Security-critical settings such as the firewall/kill-switch remain
read-only here; connection-specific changes continue to live in WebAdmin -> VPN.
"""
from __future__ import annotations

import json
import os
import re
import socket
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import HTTPException
from fastapi.responses import FileResponse, HTMLResponse

import vpn_admin

STATIC = Path(__file__).with_name("static")
VPN_DIR = Path(os.getenv("VPN_CONFIG_DIR", "/vpn"))
GLUETUN_CONTAINER = os.getenv("VPN_CONTAINER", "stremio-gluetun")
STREMIO_CONTAINER = os.getenv("STREMIO_CONTAINER", "stremio-libtorrent-server")
PIHOLE_CONTAINER = os.getenv("PIHOLE_CONTAINER", "stremio-pihole")
SCRIPT_TAG = '<script src="/gluetun-admin.js"></script>'
GLUETUN_LOCK = threading.Lock()


def _container(name: str):
    return vpn_admin._container(name)


def _env(container) -> dict[str, str]:
    return vpn_admin._env(container)


def _control_optional(path: str):
    return vpn_admin._control_optional(path)


def _active_profile() -> dict[str, object]:
    try:
        profile_id = (VPN_DIR / "active_profile").read_text(encoding="utf-8").strip()
    except OSError:
        return {}
    if not re.fullmatch(r"[a-z0-9_-]+", profile_id):
        return {}
    result: dict[str, object] = {"id": profile_id}
    try:
        data = json.loads((VPN_DIR / "profiles" / profile_id / "profile.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return result
    if isinstance(data, dict):
        for source, target in (
            ("name", "name"),
            ("country", "country"),
            ("server_group", "serverGroup"),
            ("transport", "transport"),
        ):
            value = data.get(source)
            if isinstance(value, str) and value:
                result[target] = value
    return result


def _effective_outbound_subnets(env: dict[str, str], profile: dict[str, object]) -> str:
    value = env.get("FIREWALL_OUTBOUND_SUBNETS", "192.168.0.0/16,172.30.0.0/24")
    profile_id = str(profile.get("id") or "")
    if profile_id:
        try:
            saved = (
                VPN_DIR / "profiles" / profile_id / "firewall_outbound_subnets.txt"
            ).read_text(encoding="utf-8").strip()
            if saved:
                value = saved
        except OSError:
            pass
    values = [item.strip() for item in value.split(",") if item.strip() and item.strip() != "10.0.0.0/8"]
    return ",".join(values) or "192.168.0.0/16,172.30.0.0/24"


def _docker_stats(container) -> dict[str, object]:
    if container is None or container.status != "running":
        return {"cpuPercent": 0.0, "memoryUsage": 0, "memoryLimit": 0, "rxBytes": 0, "txBytes": 0}
    try:
        raw = container.stats(stream=False) or {}
    except Exception:
        return {"cpuPercent": 0.0, "memoryUsage": 0, "memoryLimit": 0, "rxBytes": 0, "txBytes": 0}

    cpu = raw.get("cpu_stats", {}) or {}
    precpu = raw.get("precpu_stats", {}) or {}
    cpu_usage = cpu.get("cpu_usage", {}) or {}
    precpu_usage = precpu.get("cpu_usage", {}) or {}
    cpu_delta = int(cpu_usage.get("total_usage", 0) or 0) - int(precpu_usage.get("total_usage", 0) or 0)
    system_delta = int(cpu.get("system_cpu_usage", 0) or 0) - int(precpu.get("system_cpu_usage", 0) or 0)
    online = int(cpu.get("online_cpus", 0) or len(cpu_usage.get("percpu_usage", []) or []) or 1)
    cpu_percent = 0.0
    if cpu_delta > 0 and system_delta > 0:
        cpu_percent = (cpu_delta / system_delta) * online * 100.0

    memory = raw.get("memory_stats", {}) or {}
    networks = (raw.get("networks", {}) or {}).values()
    return {
        "cpuPercent": round(cpu_percent, 2),
        "memoryUsage": int(memory.get("usage", 0) or 0),
        "memoryLimit": int(memory.get("limit", 0) or 0),
        "rxBytes": sum(int(item.get("rx_bytes", 0) or 0) for item in networks),
        "txBytes": sum(int(item.get("tx_bytes", 0) or 0) for item in networks),
    }


def _network_addresses(container) -> list[dict[str, str]]:
    if container is None:
        return []
    result = []
    networks = container.attrs.get("NetworkSettings", {}).get("Networks", {}) or {}
    for name, data in networks.items():
        if not isinstance(data, dict):
            continue
        result.append(
            {
                "network": str(name),
                "ip": str(data.get("IPAddress") or ""),
                "gateway": str(data.get("Gateway") or ""),
            }
        )
    return result


def _safe_config(gluetun, profile: dict[str, object]) -> dict[str, object]:
    env = _env(gluetun)
    firewall = str(env.get("FIREWALL", "on")).lower() not in {"off", "false", "0", "no"}
    dns_server = str(env.get("DNS_SERVER", "on")).lower() not in {"off", "false", "0", "no"}
    dns_caching = str(env.get("DNS_CACHING", "on")).lower() not in {"off", "false", "0", "no"}
    health_restart = str(env.get("HEALTH_RESTART_VPN", "on")).lower() not in {"off", "false", "0", "no"}
    return {
        "vpnServiceProvider": env.get("VPN_SERVICE_PROVIDER", "custom"),
        "vpnType": env.get("VPN_TYPE", "openvpn"),
        "timezone": env.get("TZ", ""),
        "firewallEnabled": firewall,
        "firewallInputPorts": env.get("FIREWALL_INPUT_PORTS", ""),
        "firewallOutboundSubnets": _effective_outbound_subnets(env, profile),
        "dnsServerEnabled": dns_server,
        "dnsAddress": env.get("DNS_ADDRESS", "127.0.0.1"),
        "dnsKeepNameserver": env.get("DNS_KEEP_NAMESERVER", "off"),
        "dnsUpstreamResolverType": env.get("DNS_UPSTREAM_RESOLVER_TYPE", "dot"),
        "dnsUpstreamResolvers": env.get("DNS_UPSTREAM_RESOLVERS", "cloudflare"),
        "dnsCaching": dns_caching,
        "dnsProxyPort": int(env.get("STREMIO_DNS_PROXY_PORT", "1053") or 1053),
        "healthRestartVpn": health_restart,
        "healthTargetAddresses": env.get("HEALTH_TARGET_ADDRESSES", "cloudflare.com:443,github.com:443"),
        "healthIcmpTargetIps": env.get("HEALTH_ICMP_TARGET_IPS", "1.1.1.1,8.8.8.8"),
        "controlServer": {
            "url": "internal:8000",
            "authentication": "api-key" if os.getenv("VPN_CONTROL_API_KEY") else "not-configured",
        },
        "locked": {
            "firewall": "The kill-switch is intentionally managed by the VPN stack and cannot be disabled from this page.",
            "dnsAddress": "Gluetun resolves locally on 127.0.0.1:53; Pi-hole reaches it through the private DNS proxy.",
            "credentials": "VPN credentials, certificates, private keys and API keys are never exposed here.",
        },
    }


def _routing(gluetun, stremio, firewall_on: bool) -> dict[str, object]:
    routed, network_mode = vpn_admin._routing_state(gluetun, stremio)
    running = bool(gluetun and gluetun.status == "running")
    return {
        "stremioThroughGluetun": routed,
        "networkMode": network_mode,
        "killSwitchActive": bool(running and routed and firewall_on),
    }


def _pihole_state() -> dict[str, object]:
    pihole = _container(PIHOLE_CONTAINER)
    env = _env(pihole)
    return {
        "present": pihole is not None,
        "running": bool(pihole and pihole.status == "running"),
        "upstream": env.get("FTLCONF_dns_upstreams", ""),
    }


def gluetun_status():
    gluetun = _container(GLUETUN_CONTAINER)
    stremio = _container(STREMIO_CONTAINER)
    profile = _active_profile()
    config = _safe_config(gluetun, profile)
    control_status, control_error = _control_optional("/v1/vpn/status") if gluetun else (None, None)
    public_ip, public_error = _control_optional("/v1/publicip/ip") if gluetun else (None, None)
    dns_status, dns_error = _control_optional("/v1/dns/status") if gluetun else (None, None)
    updater_status, updater_error = _control_optional("/v1/updater/status") if gluetun else (None, None)
    stats = _docker_stats(gluetun)

    state = (gluetun.attrs.get("State", {}) if gluetun else {}) or {}
    health = state.get("Health", {}) if isinstance(state.get("Health"), dict) else {}
    attrs_config = (gluetun.attrs.get("Config", {}) if gluetun else {}) or {}
    firewall_on = bool(config["firewallEnabled"])

    return {
        "container": {
            "present": gluetun is not None,
            "running": bool(gluetun and gluetun.status == "running"),
            "status": gluetun.status if gluetun else "not-found",
            "health": health.get("Status") or ("running" if gluetun and gluetun.status == "running" else "unavailable"),
            "id": gluetun.id[:12] if gluetun else None,
            "image": attrs_config.get("Image"),
            "startedAt": state.get("StartedAt") if gluetun else None,
            "restartCount": int((gluetun.attrs.get("RestartCount", 0) if gluetun else 0) or 0),
            "networks": _network_addresses(gluetun),
            **stats,
        },
        "vpn": {
            "status": str((control_status or {}).get("status") or "unavailable"),
            "publicIp": (public_ip or {}).get("public_ip"),
            "controlAvailable": control_status is not None,
            "controlError": control_error or public_error,
        },
        "dns": {
            "status": str((dns_status or {}).get("status") or "unavailable"),
            "controlError": dns_error,
        },
        "updater": {
            "status": str((updater_status or {}).get("status") or "unavailable"),
            "controlError": updater_error,
        },
        "activeProfile": profile,
        "routing": _routing(gluetun, stremio, firewall_on),
        "pihole": _pihole_state(),
        "config": config,
        "busy": GLUETUN_LOCK.locked(),
        "capturedAt": datetime.now(UTC).isoformat(),
    }


def gluetun_config():
    gluetun = _container(GLUETUN_CONTAINER)
    return {
        "config": _safe_config(gluetun, _active_profile()),
        "editableInVpnPage": ["active connection", "startup connection", "transport", "LAN CIDRs", "CyberGhost bundle"],
        "readOnlyReason": "Security-critical gateway settings are intentionally read-only. Connection-specific changes are managed in WebAdmin -> VPN.",
    }


def _wait_for_container_running(timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        container = _container(GLUETUN_CONTAINER)
        if container is not None and container.status == "running":
            return
        time.sleep(1)


def _container_action(action: str):
    if action not in {"start", "stop", "restart"}:
        raise HTTPException(400, "unsupported Gluetun action")
    container = _container(GLUETUN_CONTAINER)
    if container is None:
        raise HTTPException(409, "Gluetun container is not deployed. Start the VPN stack with sh start-vpn.sh first.")
    if not GLUETUN_LOCK.acquire(blocking=False):
        raise HTTPException(409, "another Gluetun operation is already running")
    try:
        if action == "start":
            if container.status != "running":
                container.start()
                _wait_for_container_running()
        elif action == "stop":
            container.stop(timeout=15)
        else:
            container.restart(timeout=15)
            _wait_for_container_running()
        vpn_admin._audit(f"gluetun.{action}")
        return {"ok": True, "action": action, "status": gluetun_status()}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, f"Gluetun {action} failed: {exc}")
    finally:
        GLUETUN_LOCK.release()


def start_gluetun():
    return _container_action("start")


def stop_gluetun():
    return _container_action("stop")


def restart_gluetun():
    return _container_action("restart")


def _dns_proxy_host() -> str:
    try:
        parsed = urlsplit(vpn_admin.CONTROL_URL)
        if parsed.hostname:
            return parsed.hostname
    except Exception:
        pass
    return "gluetun"


def _tcp_reachable(host: str, port: int, timeout: float = 2.0) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"{host}:{port} reachable"
    except Exception as exc:
        return False, f"{host}:{port} unavailable: {type(exc).__name__}"


def validate_gluetun():
    status = gluetun_status()
    container = status["container"]
    vpn = status["vpn"]
    dns = status["dns"]
    routing = status["routing"]
    pihole = status["pihole"]
    config = status["config"]
    proxy_port = int(config.get("dnsProxyPort") or 1053)
    proxy_ok, proxy_detail = _tcp_reachable(_dns_proxy_host(), proxy_port)
    upstream = str(pihole.get("upstream") or "")
    expected_suffix = f"#{proxy_port}"

    checks = [
        {"id": "container", "label": "Gluetun container running", "ok": bool(container.get("running")), "detail": str(container.get("status"))},
        {"id": "health", "label": "Docker health", "ok": container.get("health") == "healthy", "detail": str(container.get("health"))},
        {"id": "control", "label": "Control API", "ok": bool(vpn.get("controlAvailable")), "detail": "available" if vpn.get("controlAvailable") else str(vpn.get("controlError") or "unavailable")},
        {"id": "vpn", "label": "VPN tunnel", "ok": vpn.get("status") == "running", "detail": str(vpn.get("status"))},
        {"id": "public-ip", "label": "VPN public IP detected", "ok": bool(vpn.get("publicIp")), "detail": str(vpn.get("publicIp") or "not available")},
        {"id": "dns", "label": "Gluetun DNS service", "ok": dns.get("status") == "running", "detail": str(dns.get("status"))},
        {"id": "dns-proxy", "label": "Private DNS proxy", "ok": proxy_ok, "detail": proxy_detail},
        {"id": "pihole", "label": "Pi-hole upstream to Gluetun", "ok": bool(pihole.get("running") and expected_suffix in upstream), "detail": upstream or "not configured"},
        {"id": "routing", "label": "Stremio routed through Gluetun", "ok": bool(routing.get("stremioThroughGluetun")), "detail": str(routing.get("networkMode") or "not routed")},
        {"id": "killswitch", "label": "Kill switch active", "ok": bool(routing.get("killSwitchActive")), "detail": "firewall on" if routing.get("killSwitchActive") else "not verified"},
    ]
    vpn_admin._audit("gluetun.validate", f"passed={sum(1 for item in checks if item['ok'])}/{len(checks)}")
    return {
        "ok": all(bool(item["ok"]) for item in checks),
        "passed": sum(1 for item in checks if item["ok"]),
        "total": len(checks),
        "checks": checks,
        "capturedAt": datetime.now(UTC).isoformat(),
    }


def gluetun_logs(lines: int = 200, level: str = "all", query: str = ""):
    lines = max(20, min(int(lines), 1000))
    level = str(level or "all").lower()
    if level not in {"all", "error", "warn", "warning", "info", "debug"}:
        raise HTTPException(400, "invalid log level filter")
    query = str(query or "")[:160].strip().lower()
    base = vpn_admin.vpn_logs(lines)
    items = list(base.get("lines", [])) if isinstance(base, dict) else []

    control_key = os.getenv("VPN_CONTROL_API_KEY", "")
    if control_key:
        items = [str(item).replace(control_key, "***") for item in items]

    if level != "all":
        tokens = [level]
        if level == "warn":
            tokens.append("warning")
        if level == "warning":
            tokens.append("warn")
        items = [item for item in items if any(token in item.lower() for token in tokens)]
    if query:
        items = [item for item in items if query in item.lower()]

    return {
        "available": bool(base.get("available")) if isinstance(base, dict) else False,
        "lines": items,
        "count": len(items),
        "capturedAt": datetime.now(UTC).isoformat(),
    }


def gluetun_script():
    return FileResponse(
        STATIC / "gluetun-admin.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


def _current_home(app):
    for route in reversed(app.router.routes):
        if getattr(route, "path", None) == "/" and "GET" in (getattr(route, "methods", set()) or set()):
            return route.endpoint
    return None


def install(app) -> None:
    original_home = _current_home(app)

    def home_with_gluetun():
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
        "/gluetun-admin.js",
        "/api/gluetun/status",
        "/api/gluetun/config",
        "/api/gluetun/start",
        "/api/gluetun/stop",
        "/api/gluetun/restart",
        "/api/gluetun/validate",
        "/api/gluetun/logs",
    }
    app.router.routes = [route for route in app.router.routes if getattr(route, "path", None) not in paths]
    app.add_api_route("/", home_with_gluetun, methods=["GET"])
    app.add_api_route("/gluetun-admin.js", gluetun_script, methods=["GET"])
    app.add_api_route("/api/gluetun/status", gluetun_status, methods=["GET"])
    app.add_api_route("/api/gluetun/config", gluetun_config, methods=["GET"])
    app.add_api_route("/api/gluetun/start", start_gluetun, methods=["POST"])
    app.add_api_route("/api/gluetun/stop", stop_gluetun, methods=["POST"])
    app.add_api_route("/api/gluetun/restart", restart_gluetun, methods=["POST"])
    app.add_api_route("/api/gluetun/validate", validate_gluetun, methods=["POST"])
    app.add_api_route("/api/gluetun/logs", gluetun_logs, methods=["GET"])
