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

sanitize_outbound_subnets() {
    input="$1"
    output=""
    old_ifs=$IFS
    IFS=,
    for item in $input; do
        item=$(printf '%s' "$item" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        [ -n "$item" ] || continue
        if [ "$item" = "10.0.0.0/8" ]; then
            echo "[vpn] ignoring FIREWALL_OUTBOUND_SUBNETS entry 10.0.0.0/8 because CyberGhost uses 10.x tunnel addresses" >&2
            continue
        fi
        if [ -n "$output" ]; then
            output="$output,$item"
        else
            output="$item"
        fi
    done
    IFS=$old_ifs
    [ -n "$output" ] || output="192.168.0.0/16,172.30.0.0/24"
    printf '%s' "$output"
}

prepare_runtime_config() {
    source_file="$1"
    target_file="$2"
    # CyberGhost may push redirect-gateway/redirect-private even when the downloaded
    # profile already contains redirect-gateway. Keep one deterministic full-tunnel
    # directive locally and reject pushed duplicates to avoid OpenVPN route conflicts.
    awk '
    {
        original=$0
        line=$0
        sub(/^[ \t]+/, "", line)
        split(line, fields, /[ \t]+/)
        key=tolower(fields[1])
        if (key == "redirect-gateway" || key == "redirect-private") next
        lower=tolower(line)
        if (key == "pull-filter" && lower ~ /redirect-(gateway|private)/) next
        print original
    }
    END {
        print "pull-filter ignore \"redirect-gateway\""
        print "pull-filter ignore \"redirect-private\""
        print "redirect-gateway def1"
    }' "$source_file" > "$target_file"
    chmod 600 "$target_file"
}

start_dns_proxy() {
    port="${STREMIO_DNS_PROXY_PORT:-1053}"
    case "$port" in
        ''|*[!0-9]*)
            echo "[vpn] invalid STREMIO_DNS_PROXY_PORT=$port" >&2
            exit 64
            ;;
    esac
    if [ "$port" -lt 1 ] || [ "$port" -gt 65535 ]; then
        echo "[vpn] invalid STREMIO_DNS_PROXY_PORT=$port" >&2
        exit 64
    fi
    command -v socat >/dev/null 2>&1 || {
        echo "[vpn] socat is required for the private Pi-hole -> Gluetun DNS proxy" >&2
        exit 70
    }
    socat TCP4-LISTEN:"$port",reuseaddr,fork TCP4:127.0.0.1:53 &
    socat UDP4-LISTEN:"$port",reuseaddr,fork UDP4:127.0.0.1:53 &
    echo "[vpn] DNS proxy listening on private network port $port -> 127.0.0.1:53"
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
OPENVPN_CUSTOM_CONFIG="/tmp/stremio-openvpn.runtime.ovpn"
prepare_runtime_config "$PROFILE_DIR/openvpn.runtime.ovpn" "$OPENVPN_CUSTOM_CONFIG"
OPENVPN_USER=$(cat "$PROFILE_DIR/username")
OPENVPN_PASSWORD=$(cat "$PROFILE_DIR/password")
FIREWALL_OUTBOUND_SUBNETS="${FIREWALL_OUTBOUND_SUBNETS:-192.168.0.0/16,172.30.0.0/24}"
if [ -s "$PROFILE_DIR/firewall_outbound_subnets.txt" ]; then
    FIREWALL_OUTBOUND_SUBNETS=$(sed -n '1p' "$PROFILE_DIR/firewall_outbound_subnets.txt" | tr -d '\r')
fi
FIREWALL_OUTBOUND_SUBNETS=$(sanitize_outbound_subnets "$FIREWALL_OUTBOUND_SUBNETS")

export VPN_SERVICE_PROVIDER VPN_TYPE OPENVPN_CUSTOM_CONFIG OPENVPN_USER OPENVPN_PASSWORD
export FIREWALL_OUTBOUND_SUBNETS

# Record what the gateway actually selected. vpn-data is intentionally writable
# by this wrapper so one-shot manual activation can be consumed safely.
printf '%s\n' "$PROFILE_ID" > "$ACTIVE_FILE.tmp"
chmod 600 "$ACTIVE_FILE.tmp"
mv -f "$ACTIVE_FILE.tmp" "$ACTIVE_FILE"

start_dns_proxy

echo "[vpn] selected profile: $PROFILE_ID (custom OpenVPN bundle)"
echo "[vpn] allowed outbound LAN subnets: $FIREWALL_OUTBOUND_SUBNETS"
exec /gluetun-entrypoint "$@"
