"""CyberGhost OpenVPN connection profiles layered over the VPN control API.

Profiles are isolated in the private vpn-data volume. A new profile always
imports a CyberGhost ZIP containing openvpn.ovpn, ca.crt, client.crt and
client.key. Secret values are write-only and never returned by the API.
"""
from __future__ import annotations

import base64
import binascii
import io
import ipaddress
import json
import os
import re
import shutil
import socket
import time
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel, Field

import vpn_admin as legacy

VPN_DIR = Path(os.getenv("VPN_CONFIG_DIR", "/vpn"))
PROFILES_DIR = VPN_DIR / "profiles"
ACTIVE_FILE = VPN_DIR / "active_profile"
STARTUP_FILE = VPN_DIR / "startup_profile"
NEXT_FILE = VPN_DIR / "next_profile"
REQUIRED = ("openvpn.ovpn", "ca.crt", "client.crt", "client.key")
DEFAULT_LAN_CIDRS = "192.168.0.0/16,10.0.0.0/8,172.30.0.0/24"
MAX_ZIP_BYTES = 2 * 1024 * 1024
MAX_MEMBER_BYTES = 512 * 1024
MAX_UNPACKED_BYTES = 4 * 1024 * 1024
BLOCKED_DIRECTIVES = {
    "up", "down", "route-up", "route-pre-down", "ipchange", "tls-verify",
    "auth-user-pass-verify", "client-connect", "client-disconnect", "learn-address",
    "plugin", "management", "management-client", "management-external-key",
    "management-query-passwords", "management-hold", "script-security", "askpass",
}
UNSUPPORTED_FILE_DIRECTIVES = {
    "pkcs12", "secret", "tls-auth", "tls-crypt", "tls-crypt-v2", "crl-verify",
}


class VPNFeatures(BaseModel):
    malicious_websites: bool = False
    block_ads: bool = False
    block_tracking: bool = False
    redirect_https: bool = False


class ProfileBody(BaseModel):
    name: str = Field(min_length=1, max_length=96)
    country: str = Field(default="", max_length=128)
    server_group: str = Field(default="", max_length=255)
    transport: str = Field(default="auto", max_length=8)
    username: str | None = Field(default=None, max_length=512)
    password: str | None = Field(default=None, max_length=2048)
    pre_shared: str | None = Field(default=None, max_length=2048)
    bundle_base64: str | None = Field(default=None, max_length=4 * 1024 * 1024)
    bundle_filename: str | None = Field(default=None, max_length=255)
    firewall_outbound_subnets: str = Field(default=DEFAULT_LAN_CIDRS, max_length=512)
    features: VPNFeatures = Field(default_factory=VPNFeatures)
    startup_enabled: bool = False


class StartupBody(BaseModel):
    enabled: bool


def _ensure_dirs() -> None:
    VPN_DIR.mkdir(parents=True, exist_ok=True)
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    for path in (VPN_DIR, PROFILES_DIR):
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass


def _secure_write(path: Path, value: str | bytes, newline: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if isinstance(value, bytes):
        tmp.write_bytes(value)
    else:
        if newline and not value.endswith("\n"):
            value += "\n"
        tmp.write_text(value, encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def _write_json(path: Path, value: dict) -> None:
    _secure_write(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _profile_id(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{5,63}", value):
        raise HTTPException(400, "invalid VPN profile id")
    return value


def _profile_dir(profile_id: str) -> Path:
    profile_id = _profile_id(profile_id)
    root = PROFILES_DIR.resolve()
    path = (PROFILES_DIR / profile_id).resolve()
    if root not in path.parents:
        raise HTTPException(400, "invalid VPN profile path")
    return path


def _new_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:36] or "vpn"
    return f"{slug}-{uuid.uuid4().hex[:10]}"


def _marker(path: Path) -> str | None:
    value = _read_text(path)
    if not value:
        return None
    try:
        return _profile_id(value)
    except HTTPException:
        return None


def _set_marker(path: Path, profile_id: str) -> None:
    _secure_write(path, _profile_id(profile_id), newline=True)


def _clear_marker(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _audit(action: str, detail: str = "") -> None:
    try:
        legacy.audit(action, detail)
    except Exception:
        pass


def _validate_cidrs(value: str) -> str:
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        return DEFAULT_LAN_CIDRS
    try:
        for item in items:
            ipaddress.ip_network(item, strict=False)
    except ValueError as exc:
        raise HTTPException(400, f"invalid LAN CIDR: {exc}") from exc
    return ",".join(items)


def _decode_zip(encoded: str) -> dict[str, bytes]:
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(400, "VPN bundle is not valid base64") from exc
    if not raw or len(raw) > MAX_ZIP_BYTES:
        raise HTTPException(400, "CyberGhost ZIP is empty or too large")
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise HTTPException(400, "uploaded VPN bundle is not a ZIP file") from exc

    chosen: dict[str, zipfile.ZipInfo] = {}
    unpacked = 0
    with archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            parts = Path(info.filename).parts
            if Path(info.filename).is_absolute() or any(part in {"", ".", ".."} for part in parts):
                raise HTTPException(400, "unsafe path in VPN ZIP")
            if ((info.external_attr >> 16) & 0o170000) == 0o120000:
                raise HTTPException(400, "symbolic links are not accepted in VPN ZIP")
            if info.file_size > MAX_MEMBER_BYTES:
                raise HTTPException(400, f"VPN ZIP member is too large: {Path(info.filename).name}")
            unpacked += info.file_size
            if unpacked > MAX_UNPACKED_BYTES:
                raise HTTPException(400, "VPN ZIP expands beyond the allowed size")
            base = Path(info.filename).name.lower()
            if base in REQUIRED:
                if base in chosen:
                    raise HTTPException(400, f"duplicate {base} in VPN ZIP")
                chosen[base] = info
        missing = [name for name in REQUIRED if name not in chosen]
        if missing:
            raise HTTPException(400, "CyberGhost ZIP is missing: " + ", ".join(missing))
        return {name: archive.read(chosen[name]) for name in REQUIRED}


def _text(data: bytes, label: str) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(400, f"{label} must be UTF-8 text") from exc


def _validate_pem(value: str, label: str, private: bool = False) -> None:
    if private:
        valid = "BEGIN " in value and "PRIVATE KEY" in value and "END " in value
    else:
        valid = "BEGIN CERTIFICATE" in value and "END CERTIFICATE" in value
    if not valid:
        raise HTTPException(400, f"{label} is not valid PEM material")


def _parse_ovpn(text: str) -> tuple[str, int, str]:
    host, port, transport = "", 0, ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        parts = line.split()
        key = parts[0].lower()
        if key == "remote" and len(parts) >= 2 and not host:
            host = parts[1]
            if len(parts) >= 3:
                try:
                    port = int(parts[2])
                except ValueError as exc:
                    raise HTTPException(400, "OpenVPN remote port is invalid") from exc
        elif key == "proto" and len(parts) >= 2 and not transport:
            value = parts[1].lower()
            transport = "udp" if value.startswith("udp") else "tcp" if value.startswith("tcp") else ""
    if not host:
        raise HTTPException(400, "openvpn.ovpn has no remote server")
    if transport not in {"udp", "tcp"}:
        raise HTTPException(400, "openvpn.ovpn has no supported udp/tcp protocol")
    return host, port or 1194, transport


def _resolve(host: str) -> str:
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise HTTPException(409, f"could not resolve VPN server group {host!r}: {exc}") from exc
    values: list[str] = []
    for family, _, _, _, sockaddr in infos:
        if family in {socket.AF_INET, socket.AF_INET6} and sockaddr[0] not in values:
            values.append(str(sockaddr[0]))
    if not values:
        raise HTTPException(409, f"VPN server group {host!r} did not resolve to an IP")
    return next((value for value in values if ":" not in value), values[0])


def _runtime_config(profile_id: str, original: str, expected_transport: str) -> tuple[str, dict]:
    host, port, bundle_transport = _parse_ovpn(original)
    if expected_transport != bundle_transport:
        raise HTTPException(400, f"selected transport {expected_transport} does not match the CyberGhost bundle ({bundle_transport})")
    ip = _resolve(host)
    clean: list[str] = []
    unsupported: list[str] = []
    for raw in original.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        key = line.split()[0].lower()
        if key in BLOCKED_DIRECTIVES:
            continue
        if key in UNSUPPORTED_FILE_DIRECTIVES:
            unsupported.append(key)
            continue
        if key in {"remote", "proto", "ca", "cert", "key", "auth-user-pass"} or line.lower() == "client":
            continue
        clean.append(line)
    if unsupported:
        raise HTTPException(400, "unsupported external OpenVPN material: " + ", ".join(sorted(set(unsupported))))
    root = f"/vpn/profiles/{profile_id}"
    prefix = [
        "client", f"remote {ip} {port}", f"proto {expected_transport}", "auth-user-pass",
        f"ca {root}/ca.crt", f"cert {root}/client.crt", f"key {root}/client.key",
    ]
    return "\n".join(prefix + clean) + "\n", {
        "serverGroup": host, "serverIp": ip, "serverPort": port, "transport": bundle_transport,
    }


def _prepare_bundle(bundle: dict[str, bytes], profile_id: str, requested_transport: str) -> dict:
    original = _text(bundle["openvpn.ovpn"], "openvpn.ovpn")
    ca, cert, key = (_text(bundle[name], name) for name in ("ca.crt", "client.crt", "client.key"))
    _validate_pem(ca, "ca.crt")
    _validate_pem(cert, "client.crt")
    _validate_pem(key, "client.key", private=True)
    _, _, bundle_transport = _parse_ovpn(original)
    transport = bundle_transport if requested_transport == "auto" else requested_transport
    if transport not in {"udp", "tcp"}:
        raise HTTPException(400, "transport must be auto, udp or tcp")
    runtime, endpoint = _runtime_config(profile_id, original, transport)
    return {"original": original, "runtime": runtime, "ca": ca, "cert": cert, "key": key, "endpoint": endpoint}


def _write_bundle(path: Path, prepared: dict) -> None:
    _secure_write(path / "openvpn.ovpn", prepared["original"], newline=True)
    _secure_write(path / "openvpn.runtime.ovpn", prepared["runtime"])
    _secure_write(path / "ca.crt", prepared["ca"], newline=True)
    _secure_write(path / "client.crt", prepared["cert"], newline=True)
    _secure_write(path / "client.key", prepared["key"], newline=True)


def _meta(profile_id: str) -> dict:
    data = _read_json(_profile_dir(profile_id) / "profile.json")
    if not data:
        raise HTTPException(404, "VPN connection profile not found")
    return data


def _has(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def _public(profile_id: str, meta: dict | None = None) -> dict:
    path, meta = _profile_dir(profile_id), meta or _meta(profile_id)
    return {
        "id": profile_id, "name": meta.get("name", profile_id), "provider": "CyberGhost", "protocol": "openvpn",
        "country": meta.get("country", ""), "serverGroup": meta.get("serverGroup", ""),
        "serverPort": meta.get("serverPort"), "transport": meta.get("transport", "udp"),
        "firewallOutboundSubnets": meta.get("firewallOutboundSubnets", DEFAULT_LAN_CIDRS),
        "features": meta.get("features", VPNFeatures().model_dump()), "createdAt": meta.get("createdAt"),
        "updatedAt": meta.get("updatedAt"), "bundleFilename": meta.get("bundleFilename", ""),
        "bundleFiles": [name for name in REQUIRED if _has(path / name)],
        "credentials": {"username": _has(path / "username"), "password": _has(path / "password"),
                        "preShared": _has(path / "pre_shared"), "caCert": _has(path / "ca.crt"),
                        "clientCert": _has(path / "client.crt"), "clientKey": _has(path / "client.key")},
        "active": _marker(ACTIVE_FILE) == profile_id, "startupEnabled": _marker(STARTUP_FILE) == profile_id,
        "extraFeaturesMode": "cyberghost-profile-metadata",
    }


def list_profiles():
    _ensure_dirs()
    items = []
    for path in PROFILES_DIR.iterdir():
        if path.is_dir() and re.fullmatch(r"[a-z0-9][a-z0-9_-]{5,63}", path.name):
            meta = _read_json(path / "profile.json")
            if meta:
                items.append(_public(path.name, meta))
    items.sort(key=lambda item: (not item["active"], str(item["name"]).lower()))
    return {"profiles": items, "activeProfileId": _marker(ACTIVE_FILE), "startupProfileId": _marker(STARTUP_FILE), "requiredBundleFiles": list(REQUIRED)}


def create_profile(body: ProfileBody):
    _ensure_dirs()
    if not body.bundle_base64:
        raise HTTPException(400, "a CyberGhost ZIP bundle is required for every new VPN connection")
    if not body.username or not body.password:
        raise HTTPException(400, "generated CyberGhost OpenVPN username and password are required")
    profile_id, cidrs = _new_id(body.name), _validate_cidrs(body.firewall_outbound_subnets)
    path = _profile_dir(profile_id)
    path.mkdir(mode=0o700, parents=True, exist_ok=False)
    try:
        prepared = _prepare_bundle(_decode_zip(body.bundle_base64), profile_id, body.transport.lower())
        endpoint = prepared["endpoint"]
        if body.server_group and body.server_group.lower() != str(endpoint["serverGroup"]).lower():
            raise HTTPException(400, "server group does not match the remote server inside openvpn.ovpn")
        _write_bundle(path, prepared)
        now = datetime.now(UTC).isoformat()
        meta = {"id": profile_id, "name": body.name.strip(), "provider": "cyberghost", "protocol": "openvpn",
                "country": body.country.strip(), **endpoint, "firewallOutboundSubnets": cidrs,
                "features": body.features.model_dump(), "bundleFilename": (body.bundle_filename or "cyberghost-openvpn.zip").strip(),
                "createdAt": now, "updatedAt": now}
        _secure_write(path / "username", body.username.strip())
        _secure_write(path / "password", body.password)
        if body.pre_shared:
            _secure_write(path / "pre_shared", body.pre_shared)
        _secure_write(path / "firewall_outbound_subnets.txt", cidrs, newline=True)
        _write_json(path / "profile.json", meta)
        if body.startup_enabled:
            _set_marker(STARTUP_FILE, profile_id)
        _audit("vpn.profile.create", f"profile={profile_id}")
        return {"ok": True, "profile": _public(profile_id)}
    except Exception:
        shutil.rmtree(path, ignore_errors=True)
        raise


def update_profile(profile_id: str, body: ProfileBody):
    profile_id, path, meta = _profile_id(profile_id), _profile_dir(profile_id), _meta(profile_id)
    cidrs, prepared = _validate_cidrs(body.firewall_outbound_subnets), None
    endpoint = {key: meta.get(key) for key in ("serverGroup", "serverIp", "serverPort", "transport")}
    if body.bundle_base64:
        prepared = _prepare_bundle(_decode_zip(body.bundle_base64), profile_id, body.transport.lower())
        endpoint = prepared["endpoint"]
        if body.server_group and body.server_group.lower() != str(endpoint["serverGroup"]).lower():
            raise HTTPException(400, "server group does not match the replacement openvpn.ovpn")
    elif body.transport.lower() not in {"auto", str(meta.get("transport", "udp")).lower()}:
        raise HTTPException(400, "changing UDP/TCP requires a matching replacement CyberGhost ZIP")
    if prepared:
        _write_bundle(path, prepared)
    if body.username:
        _secure_write(path / "username", body.username.strip())
    if body.password:
        _secure_write(path / "password", body.password)
    if body.pre_shared:
        _secure_write(path / "pre_shared", body.pre_shared)
    meta.update({"name": body.name.strip(), "country": body.country.strip(), **endpoint,
                 "firewallOutboundSubnets": cidrs, "features": body.features.model_dump(),
                 "updatedAt": datetime.now(UTC).isoformat()})
    if body.bundle_filename:
        meta["bundleFilename"] = body.bundle_filename.strip()
    _secure_write(path / "firewall_outbound_subnets.txt", cidrs, newline=True)
    _write_json(path / "profile.json", meta)
    if body.startup_enabled:
        _set_marker(STARTUP_FILE, profile_id)
    elif _marker(STARTUP_FILE) == profile_id:
        _clear_marker(STARTUP_FILE)
    _audit("vpn.profile.update", f"profile={profile_id}")
    return {"ok": True, "profile": _public(profile_id)}


def set_startup(profile_id: str, body: StartupBody):
    profile_id = _profile_id(profile_id)
    _meta(profile_id)
    if body.enabled:
        _set_marker(STARTUP_FILE, profile_id)
        message = "Connection will be selected automatically when the VPN gateway starts."
    else:
        if _marker(STARTUP_FILE) == profile_id:
            _clear_marker(STARTUP_FILE)
        message = "Automatic startup selection disabled for this connection."
    _audit("vpn.profile.startup", f"profile={profile_id} enabled={body.enabled}")
    result = list_profiles()
    result.update({"ok": True, "message": message})
    return result


def delete_profile(profile_id: str):
    profile_id, path = _profile_id(profile_id), _profile_dir(profile_id)
    _meta(profile_id)
    if _marker(ACTIVE_FILE) == profile_id:
        raise HTTPException(409, "activate another VPN connection before deleting the active one")
    if _marker(STARTUP_FILE) == profile_id:
        _clear_marker(STARTUP_FILE)
    if _marker(NEXT_FILE) == profile_id:
        _clear_marker(NEXT_FILE)
    shutil.rmtree(path)
    _audit("vpn.profile.delete", f"profile={profile_id}")
    return {"ok": True, "deleted": profile_id}


def _refresh_runtime(profile_id: str) -> None:
    path, meta = _profile_dir(profile_id), _meta(profile_id)
    original = _read_text(path / "openvpn.ovpn")
    runtime, endpoint = _runtime_config(profile_id, original, str(meta.get("transport") or "udp"))
    _secure_write(path / "openvpn.runtime.ovpn", runtime)
    meta.update(endpoint | {"updatedAt": datetime.now(UTC).isoformat()})
    _write_json(path / "profile.json", meta)


def activate_profile(profile_id: str):
    profile_id, path, meta = _profile_id(profile_id), _profile_dir(profile_id), _meta(profile_id)
    missing = [name for name in ("username", "password", *REQUIRED) if not _has(path / name)]
    if missing:
        raise HTTPException(409, "VPN profile is incomplete: " + ", ".join(missing))
    _refresh_runtime(profile_id)
    _set_marker(ACTIVE_FILE, profile_id)
    gluetun = legacy._container(legacy.GLUETUN_CONTAINER)
    if gluetun is None:
        _audit("vpn.profile.activate", f"profile={profile_id} mode=prepared")
        return {"ok": True, "profile": _public(profile_id), "started": False,
                "message": "Connection prepared. Run 'sh start-vpn.sh' on the Docker host to start VPN mode."}
    if not legacy.VPN_LOCK.acquire(blocking=False):
        raise HTTPException(409, "another VPN operation is already running")
    try:
        _set_marker(NEXT_FILE, profile_id)
        gluetun.restart(timeout=15)
        deadline, last_error = time.monotonic() + 60, None
        while time.monotonic() < deadline:
            time.sleep(1)
            try:
                status = legacy._control("GET", "/v1/vpn/status", timeout=3)
                if status.get("status") == "running":
                    _audit("vpn.profile.activate", f"profile={profile_id} mode=restart")
                    return {"ok": True, "profile": _public(profile_id), "started": True,
                            "message": f"VPN connection '{meta.get('name', profile_id)}' is active."}
            except Exception as exc:
                last_error = str(exc)
        return {"ok": True, "profile": _public(profile_id), "started": True,
                "message": "VPN gateway restarted; the connection is still converging.", "detail": last_error}
    finally:
        legacy.VPN_LOCK.release()


def profile_status():
    data = legacy.vpn_status()
    active = _marker(ACTIVE_FILE)
    try:
        summary = _public(active) if active else None
    except HTTPException:
        summary = None
    data.pop("config", None)
    data["activeProfileId"] = active
    data["startupProfileId"] = _marker(STARTUP_FILE)
    data["activeProfile"] = summary
    limitations = data.setdefault("limitations", {})
    limitations["providerFeatures"] = "CyberGhost extra-feature checkboxes are profile metadata; provider-side enforcement comes from the generated CyberGhost connection."
    return data


def profile_logs(lines: int = 200):
    result = legacy.vpn_logs(lines)
    text = "\n".join(result.get("lines", []))
    _ensure_dirs()
    for profile in PROFILES_DIR.iterdir():
        if profile.is_dir():
            for filename in ("username", "password", "pre_shared"):
                secret = _read_text(profile / filename)
                if secret:
                    text = text.replace(secret, "***")
    result["lines"] = text.splitlines()
    return result


def reapply_active():
    profile_id = _marker(ACTIVE_FILE)
    if not profile_id:
        raise HTTPException(409, "no VPN connection is active")
    return activate_profile(profile_id)


def install(app) -> None:
    replace = {"/api/vpn/status", "/api/vpn/config", "/api/vpn/apply", "/api/vpn/logs"}
    app.router.routes = [route for route in app.router.routes if getattr(route, "path", None) not in replace]
    app.add_api_route("/api/vpn/status", profile_status, methods=["GET"])
    app.add_api_route("/api/vpn/logs", profile_logs, methods=["GET"])
    app.add_api_route("/api/vpn/profiles", list_profiles, methods=["GET"])
    app.add_api_route("/api/vpn/profiles", create_profile, methods=["POST"], status_code=201)
    app.add_api_route("/api/vpn/profiles/{profile_id}", update_profile, methods=["PUT"])
    app.add_api_route("/api/vpn/profiles/{profile_id}", delete_profile, methods=["DELETE"])
    app.add_api_route("/api/vpn/profiles/{profile_id}/activate", activate_profile, methods=["POST"], status_code=202)
    app.add_api_route("/api/vpn/profiles/{profile_id}/startup", set_startup, methods=["PUT"])
    app.add_api_route("/api/vpn/apply", reapply_active, methods=["POST"], status_code=202)
