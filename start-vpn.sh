#!/bin/sh
# Start the full Stremio/WebAdmin/Pi-hole stack with Stremio routed through
# CyberGhost via the Gluetun VPN gateway.
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
        {for (i = 1; i <= 4; i++) if ($i !~ /^[0-9]+$/ || $i < 0 || $i > 255) bad = 1}
        END {exit bad ? 1 : 0}'
}

_generate_key() {
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -hex 24
    elif command -v python3 >/dev/null 2>&1; then
        python3 -c 'import secrets; print(secrets.token_urlsafe(24))'
    else
        od -An -N24 -tx1 /dev/urandom | tr -d ' \n'
    fi
}

_container_exists() {
    docker container inspect "$1" >/dev/null 2>&1
}

# Direct mode gives stremio-libtorrent-server the internal 172.30.0.10 address and host ports.
# Gluetun needs to take over those same resources in VPN mode, so remove the direct Stremio
# container only after all images and the trusted certificate are ready. Named volumes are never removed.
_enter_vpn_mode() {
    if ! _container_exists stremio-gluetun && _container_exists stremio-libtorrent-server; then
        echo "[vpn] switching direct -> VPN mode (persistent volumes are preserved)..."
        docker rm -f stremio-libtorrent-server >/dev/null 2>&1 || true
    fi
}

if [ -z "${IPADDRESS:-}" ]; then
    IPADDRESS=$(_detect_ip || true)
fi
if [ -z "${IPADDRESS:-}" ] || ! _is_ipv4 "$IPADDRESS"; then
    echo "[vpn] unable to determine a valid host IPv4 address." >&2
    echo "[vpn] set it explicitly, e.g. IPADDRESS=192.168.1.244 sh start-vpn.sh" >&2
    exit 1
fi
export IPADDRESS

PIHOLE_WEB_BIND_IP=${PIHOLE_WEB_BIND_IP:-$IPADDRESS}
PIHOLE_DNS_BIND_IP=${PIHOLE_DNS_BIND_IP:-$IPADDRESS}
export PIHOLE_WEB_BIND_IP PIHOLE_DNS_BIND_IP

IPD=$(printf '%s' "$IPADDRESS" | sed 's/[.]/-/g')
TRUSTED_DOMAIN="${IPD}.519b6502d940.stremio.rocks"

KEY_FILE=${VPN_CONTROL_KEY_FILE:-$ROOT/.vpn-control-key}
if [ -z "${VPN_CONTROL_API_KEY:-}" ]; then
    if [ -s "$KEY_FILE" ]; then
        VPN_CONTROL_API_KEY=$(tr -d '\r\n' < "$KEY_FILE")
    else
        umask 077
        VPN_CONTROL_API_KEY=$(_generate_key)
        printf '%s\n' "$VPN_CONTROL_API_KEY" > "$KEY_FILE"
        chmod 600 "$KEY_FILE"
        echo "[vpn] generated private Gluetun control key in .vpn-control-key"
    fi
fi
export VPN_CONTROL_API_KEY

if ! docker compose version >/dev/null 2>&1; then
    echo "[vpn] Docker Compose plugin is not available." >&2
    exit 1
fi
if [ ! -c /dev/net/tun ]; then
    echo "[vpn] /dev/net/tun is not available on this host." >&2
    echo "[vpn] load/enable TUN support before starting Gluetun." >&2
    exit 1
fi

# Preserve hardware transcoding in VPN mode. The VAAPI overlay is applied
# automatically when the configured render node exists on the host.
COMPOSE_FILES="-f compose.vpn.yaml"
if [ -c "${VAAPI_DEVICE:-/dev/dri/renderD128}" ] && [ -f compose.vaapi.yaml ]; then
    COMPOSE_FILES="$COMPOSE_FILES -f compose.vaapi.yaml"
    echo "[vpn] VAAPI      : enabled (${VAAPI_DEVICE:-/dev/dri/renderD128})"
else
    echo "[vpn] VAAPI      : unavailable; starting without /dev/dri overlay"
fi

echo "[vpn] host IPv4 : $IPADDRESS"
echo "[vpn] Web Player : http://$IPADDRESS:8080"
echo "[vpn] WebAdmin   : http://$IPADDRESS:8090"
echo "[vpn] API        : http://$IPADDRESS:11470"
echo "[vpn] Library    : https://${TRUSTED_DOMAIN}:12470/library/"
echo "[vpn] Pi-hole    : http://$PIHOLE_WEB_BIND_IP:8053/admin/"
echo "[vpn] Stremio Internet egress is fail-closed behind Gluetun."
echo "[vpn] Trusted LAN HTTPS certificate is bootstrapped before the VPN stack starts."
echo "[vpn] CyberGhost credentials/certificates are configured from WebAdmin -> VPN."

if [ "$#" -eq 0 ]; then
    echo "[vpn] pulling published images..."
    # shellcheck disable=SC2086
    docker compose $COMPOSE_FILES pull

    echo "[vpn] validating/refreshing trusted LAN certificate outside the VPN tunnel..."
    # shellcheck disable=SC2086
    if ! docker compose $COMPOSE_FILES --profile bootstrap run --rm cert-bootstrap; then
        echo "[vpn] ERROR: trusted stremio.rocks certificate is not available." >&2
        echo "[vpn] VPN mode was not started because LAN clients require trusted HTTPS on :12470." >&2
        exit 1
    fi

    _enter_vpn_mode
    # shellcheck disable=SC2086
    exec docker compose $COMPOSE_FILES up -d --remove-orphans
fi

# shellcheck disable=SC2086
exec docker compose $COMPOSE_FILES "$@"
