"""Automatic BitTorrent network policy for DIRECT and VPN modes."""
from __future__ import annotations
import logging
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
        policy = (port, mode, vpn_on)
        if policy != last:
            try:
                engine.set_upnp_enabled(False if vpn_on else direct_upnp)
                engine.set_listen_port(port)
                log.info("automatic BitTorrent policy -> port=%s mode=%s upnp=%s", port, mode, False if vpn_on else direct_upnp)
                last = policy
            except Exception as exc:
                log.warning("could not apply automatic BitTorrent policy %s: %s", policy, exc)
        time.sleep(max(0.25, interval))
