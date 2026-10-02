#!/bin/sh
set -eu

CONFIG_DIR="${STREMIO_VPN_CONFIG_DIR:-/vpn}"
PROFILES_DIR="$CONFIG_DIR/profiles"
ACTIVE_FILE="$CONFIG_DIR/active_profile"
STARTUP_FILE="$CONFIG_DIR/startup_profile"
NEXT_FILE="$CONFIG_DIR/next_profile"

read_id() {
    file="$1"
    [ -s "$file" ] || return 1
    value=$(sed -n '1p' "$file" | tr -d '\r\n')
    case "$value" in
        ''|*[!a-z0-9_-]*) return 1 ;;
    esac
    printf '%s' "$value"
}

# A manual activation writes next_profile and restarts Gluetun. It is consumed
# once. On a later host/container boot, startup_profile wins. If no startup
# profile is configured, the last active profile is reused.
PROFILE_ID=""
if PROFILE_ID=$(read_id "$NEXT_FILE" 2>/dev/null); then
    rm -f "$NEXT_FILE"
elif PROFILE_ID=$(read_id "$STARTUP_FILE" 2>/dev/null); then
    :
elif PROFILE_ID=$(read_id "$ACTIVE_FILE" 2>/dev/null); then
    :
else
    echo "[vpn] no VPN connection profile is selected." >&2
    echo "[vpn] create a CyberGhost profile in WebAdmin -> VPN, activate it, then start VPN mode." >&2
    exit 64
fi

PROFILE_DIR="$PROFILES_DIR/$PROFILE_ID"
for file in profile.json openvpn.runtime.ovpn ca.crt client.crt client.key username password; do
    if [ ! -s "$PROFILE_DIR/$file" ]; then
        echo "[vpn] selected profile '$PROFILE_ID' is incomplete: missing $file" >&2
        exit 64
    fi
done

VPN_SERVICE_PROVIDER=custom
VPN_TYPE=openvpn
OPENVPN_CUSTOM_CONFIG="$PROFILE_DIR/openvpn.runtime.ovpn"
OPENVPN_USER=$(cat "$PROFILE_DIR/username")
OPENVPN_PASSWORD=$(cat "$PROFILE_DIR/password")
FIREWALL_OUTBOUND_SUBNETS="${FIREWALL_OUTBOUND_SUBNETS:-192.168.0.0/16,10.0.0.0/8,172.30.0.0/24}"
if [ -s "$PROFILE_DIR/firewall_outbound_subnets.txt" ]; then
    FIREWALL_OUTBOUND_SUBNETS=$(sed -n '1p' "$PROFILE_DIR/firewall_outbound_subnets.txt" | tr -d '\r')
fi

export VPN_SERVICE_PROVIDER VPN_TYPE OPENVPN_CUSTOM_CONFIG OPENVPN_USER OPENVPN_PASSWORD
export FIREWALL_OUTBOUND_SUBNETS

# Record what the gateway actually selected. vpn-data is intentionally writable
# by this wrapper so one-shot manual activation can be consumed safely.
printf '%s\n' "$PROFILE_ID" > "$ACTIVE_FILE.tmp"
chmod 600 "$ACTIVE_FILE.tmp"
mv -f "$ACTIVE_FILE.tmp" "$ACTIVE_FILE"

echo "[vpn] selected profile: $PROFILE_ID (custom OpenVPN bundle)"
exec /gluetun-entrypoint "$@"
