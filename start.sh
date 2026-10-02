#!/bin/sh
# Start the full Stremio/WebAdmin/Pi-hole stack using the host's current LAN IPv4 address.
#
# Docker Compose cannot execute commands inside .env. Detecting the address must therefore happen
# on the host before Compose evaluates compose.yaml. Shell environment variables take precedence
# over .env, so the detected address is injected without rewriting the tracked configuration file.
#
# The default path is package-only: pull the published images and start them. No local source build
# is required. Arbitrary Docker Compose commands can still be passed through this launcher.
#
# Usage:
#   sh start.sh                         # direct mode: pull + up -d
#   sh start.sh config                  # inspect the resolved compose configuration
#   sh start.sh ps                      # show stack status
#   sh start.sh up -d --force-recreate  # pass arbitrary compose arguments
#   IPADDRESS=192.168.1.10 sh start.sh   # explicit override
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"

_detect_ip() {
    if command -v ip >/dev/null 2>&1; then
        detected=$(ip route get "${IP_DETECT_TARGET:-1.1.1.1}" 2>/dev/null \
            | awk '{for (i = 1; i <= NF; i++) if ($i == "src") {print $(i + 1); exit}}')
        if [ -n "$detected" ]; then
            printf '%s\n' "$detected"
            return
        fi
    fi
    hostname -I 2>/dev/null \
        | awk '{for (i = 1; i <= NF; i++) if ($i !~ /^127\./ && $i !~ /:/) {print $i; exit}}'
}

_is_ipv4() {
    printf '%s\n' "$1" | awk -F. '
        NF != 4 {bad = 1}
        {
            for (i = 1; i <= 4; i++) {
                if ($i !~ /^[0-9]+$/ || $i < 0 || $i > 255) bad = 1
            }
        }
        END {exit bad ? 1 : 0}'
}

_container_exists() {
    docker container inspect "$1" >/dev/null 2>&1
}

# VPN mode gives Gluetun the internal address and published Stremio ports. Before returning to
# direct mode, remove only the two transient containers that own/share that network namespace.
# Named cache/config/VPN volumes are deliberately untouched.
_leave_vpn_mode() {
    if _container_exists stremio-gluetun; then
        echo "[start] switching VPN -> direct mode (persistent volumes are preserved)..."
        docker rm -f stremio-libtorrent-server >/dev/null 2>&1 || true
        docker rm -f stremio-gluetun >/dev/null 2>&1 || true
    fi
}

if [ -z "${IPADDRESS:-}" ]; then
    IPADDRESS=$(_detect_ip || true)
fi

if [ -z "${IPADDRESS:-}" ] || ! _is_ipv4 "$IPADDRESS"; then
    echo "[start] unable to determine a valid host IPv4 address." >&2
    echo "[start] set it explicitly, e.g. IPADDRESS=192.168.1.244 sh start.sh" >&2
    exit 1
fi

export IPADDRESS
PIHOLE_WEB_BIND_IP=${PIHOLE_WEB_BIND_IP:-$IPADDRESS}
PIHOLE_DNS_BIND_IP=${PIHOLE_DNS_BIND_IP:-$IPADDRESS}
export PIHOLE_WEB_BIND_IP PIHOLE_DNS_BIND_IP

echo "[start] detected host IPv4: $IPADDRESS"
echo "[start] Web Player : http://$IPADDRESS:8080"
echo "[start] WebAdmin   : http://$IPADDRESS:8090"
echo "[start] API        : http://$IPADDRESS:11470"
echo "[start] Library    : https://$IPADDRESS:12470/library/"
echo "[start] Pi-hole    : http://$PIHOLE_WEB_BIND_IP:8053/admin/"

if ! docker compose version >/dev/null 2>&1; then
    echo "[start] Docker Compose plugin is not available." >&2
    exit 1
fi

if [ "$#" -eq 0 ]; then
    echo "[start] pulling published images..."
    docker compose pull
    _leave_vpn_mode
    exec docker compose up -d --remove-orphans
fi

exec docker compose "$@"
