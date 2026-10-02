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
#   sh start.sh                         # unified stack: pull + up -d
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

# Persist the detected address for every later Compose/WebAdmin operation.  A
# shell-only export disappears as soon as this launcher exits, which made a
# fresh install fall back to localhost/0.0.0.0 on subsequent restarts.
ENV_FILE="$ROOT/.env"
if [ ! -f "$ENV_FILE" ]; then
    cp "$ROOT/.env.example" "$ENV_FILE"
fi
if grep -q '^IPADDRESS=' "$ENV_FILE"; then
    sed -i "s/^IPADDRESS=.*/IPADDRESS=$IPADDRESS/" "$ENV_FILE"
else
    printf '\nIPADDRESS=%s\n' "$IPADDRESS" >> "$ENV_FILE"
fi

COMPOSE_ARGS="-f compose.yaml"
if [ -e "${VAAPI_DEVICE:-/dev/dri/renderD128}" ]; then
    COMPOSE_ARGS="$COMPOSE_ARGS -f compose.vaapi.yaml"
    echo "[start] VAAPI render node detected: ${VAAPI_DEVICE:-/dev/dri/renderD128}"
elif [ -e /dev/nvidia0 ] && command -v nvidia-smi >/dev/null 2>&1; then
    COMPOSE_ARGS="$COMPOSE_ARGS -f compose.gpu.yaml"
    echo "[start] NVIDIA GPU detected: enabling GPU overlay"
else
    echo "[start] no supported GPU render node detected: CPU fallback"
fi

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

_repair_gateway_namespace() {
    gluetun_id=$(docker inspect -f '{{.Id}}' stremio-gluetun 2>/dev/null || true)
    stremio_mode=$(docker inspect -f '{{.HostConfig.NetworkMode}}' stremio-libtorrent-server 2>/dev/null || true)

    if [ -z "$gluetun_id" ] || [ -z "$stremio_mode" ]; then
        echo "[start] gateway namespace check skipped: containers are not available yet"
        return 0
    fi

    case "$stremio_mode" in
        "container:$gluetun_id")
            echo "[start] gateway namespace: current"
            return 0
            ;;
        container:*)
            echo "[start] stale Gluetun namespace detected; recreating only Stremio..."
            # Gluetun is already healthy because the normal Compose start above
            # honors the service_healthy dependency. Recreate only the dependent
            # service so Docker resolves network_mode: service:gluetun to the
            # current gateway container ID.
            # shellcheck disable=SC2086
            docker compose $COMPOSE_ARGS up -d --no-deps --force-recreate stremio-libtorrent-server

            repaired_mode=$(docker inspect -f '{{.HostConfig.NetworkMode}}' stremio-libtorrent-server 2>/dev/null || true)
            if [ "$repaired_mode" != "container:$gluetun_id" ]; then
                echo "[start] ERROR: Stremio did not attach to the current Gluetun namespace." >&2
                return 1
            fi
            echo "[start] gateway namespace repaired"
            ;;
        *)
            echo "[start] ERROR: unexpected Stremio network mode: $stremio_mode" >&2
            return 1
            ;;
    esac
}

if [ "$#" -eq 0 ]; then
    echo "[start] pulling published images..."
    # shellcheck disable=SC2086 # COMPOSE_ARGS is an intentional argument list.
    docker compose $COMPOSE_ARGS pull
    # Do not exec here: v2.0.6 performs a post-start namespace integrity check.
    # shellcheck disable=SC2086
    docker compose $COMPOSE_ARGS up -d --remove-orphans
    _repair_gateway_namespace
    exit 0
fi

# shellcheck disable=SC2086
exec docker compose $COMPOSE_ARGS "$@"
