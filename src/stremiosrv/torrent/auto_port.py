"""Automatic BitTorrent listen-port selection for VPN port forwarding."""
from __future__ import annotations
import logging
import time
log = logging.getLogger(__name__)

def desired_port(default_port: int, path: str) -> tuple[int, str]:
    if not path:
        return int(default_port), "direct"
    try:
        with open(path, encoding="utf-8") as handle:
            port = int(handle.read().strip())
        if 1 <= port <= 65535:
            return port, "vpn-forwarded"
    except (OSError, ValueError):
        pass
    return int(default_port), "default"

def run_auto_port_watcher(engine, default_port: int, path: str, interval: float = 2.0) -> None:
    last = None
    while True:
        port, mode = desired_port(default_port, path)
        if port != last:
            try:
                changed = engine.set_listen_port(port)
                if changed:
                    log.info("automatic BitTorrent listen port -> %s (%s)", port, mode)
                last = port
            except Exception as exc:
                log.warning("could not apply automatic BitTorrent listen port %s: %s", port, exc)
        time.sleep(max(0.25, interval))
