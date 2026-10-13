"""Automatic BitTorrent network policy for DIRECT and VPN modes."""
from __future__ import annotations
import json
import logging
from pathlib import Path
import time
log = logging.getLogger(__name__)

def flag_enabled(path: str) -> bool:
    if not path:
        return False
    try:
        with open(path, encoding="utf-8") as handle:
            value = handle.read().strip().lower()
    except OSError:
        return False
    return value in {"1", "true", "yes", "on", "enabled"}

def vpn_provider(enabled_file: str) -> str:
    """Read the selected profile from the shared VPN volume (fail closed)."""
    if not enabled_file or not flag_enabled(enabled_file):
        return ""
    root = Path(enabled_file).parent
    try:
        profile_id = (root / "active_profile").read_text(encoding="utf-8").strip()
        if not profile_id or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for ch in profile_id):
            return ""
        data = json.loads((root / "profiles" / profile_id / "profile.json").read_text(encoding="utf-8"))
        return str(data.get("provider", "")).strip().lower()
    except (OSError, ValueError, TypeError):
        return ""

def desired_port(default_port: int, path: str, vpn_enabled: bool = False) -> tuple[int, str]:
    if not vpn_enabled:
        return int(default_port), "direct"
    try:
        with open(path, encoding="utf-8") as handle:
            port = int(handle.read().strip())
        if 1 <= port <= 65535:
            return port, "vpn-forwarded"
    except (OSError, ValueError):
        pass
    return int(default_port), "vpn-no-forwarding"

def run_auto_port_watcher(engine, default_port: int, path: str, vpn_enabled_file: str = "", direct_upnp: bool = True, interval: float = 2.0) -> None:
    last = None
    while True:
        vpn_on = flag_enabled(vpn_enabled_file)
        port, mode = desired_port(default_port, path, vpn_on)
        provider = vpn_provider(vpn_enabled_file) if vpn_on else ""
        # Proton supplies the incoming port using its own NAT-PMP lease.
        # CyberGhost does not; attempt peer mapping only if its gateway supports it.
        # Never treat an attempted mapping as proof of inbound reachability.
        upnp = bool(direct_upnp and (not vpn_on or (provider == "cyberghost" and mode == "vpn-no-forwarding")))
        policy = (port, mode, vpn_on, provider, upnp)
        if policy != last:
            try:
                engine.set_upnp_enabled(upnp)
                engine.set_listen_port(port)
                log.info("automatic BitTorrent policy -> port=%s mode=%s provider=%s upnp=%s", port, mode, provider or "none", upnp)
                last = policy
            except Exception as exc:
                log.warning("could not apply automatic BitTorrent policy %s: %s", policy, exc)
        time.sleep(max(0.25, interval))
