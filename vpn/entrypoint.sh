#!/bin/sh
set -eu

CONFIG_DIR="${STREMIO_VPN_CONFIG_DIR:-/vpn}"
PROFILES_DIR="$CONFIG_DIR/profiles"
ACTIVE_FILE="$CONFIG_DIR/active_profile"
STARTUP_FILE="$CONFIG_DIR/startup_profile"
NEXT_FILE="$CONFIG_DIR/next_profile"
ENABLED_FILE="${STREMIO_VPN_ENABLED_FILE:-$CONFIG_DIR/enabled}"
READY_FILE="/tmp/stremio-vpn-supervisor.ready"
DNS_PORT="${STREMIO_DNS_PROXY_PORT:-1053}"
DIRECT_DNS="${STREMIO_DIRECT_DNS_UPSTREAM:-1.1.1.1}"

VPN_PID=""
DNS_TCP_PID=""
DNS_UDP_PID=""
DIRECT_DEFAULT=""

read_id() {
    file="$1"
    [ -s "$file" ] || return 1
    value=$(sed -n '1p' "$file" | tr -d '\r\n')
    case "$value" in
        ''|*[!a-z0-9_-]*) return 1 ;;
    esac
    printf '%s' "$value"
}

vpn_enabled() {
    [ -s "$ENABLED_FILE" ] || return 1
    value=$(sed -n '1p' "$ENABLED_FILE" | tr '[:upper:]' '[:lower:]' | tr -d ' \t\r\n')
    case "$value" in
        1|true|yes|on|enabled) return 0 ;;
        *) return 1 ;;
    esac
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
        if [ -n "$output" ]; then output="$output,$item"; else output="$item"; fi
    done
    IFS=$old_ifs
    [ -n "$output" ] || output="192.168.0.0/16,172.30.0.0/24"
    printf '%s' "$output"
}

prepare_runtime_config() {
    source_file="$1"
    target_file="$2"
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

stop_dns_proxy() {
    for pid in "$DNS_TCP_PID" "$DNS_UDP_PID"; do
        [ -n "$pid" ] || continue
        kill "$pid" >/dev/null 2>&1 || true
        wait "$pid" 2>/dev/null || true
    done
    DNS_TCP_PID=""
    DNS_UDP_PID=""
}

start_dns_proxy() {
    target="$1"
    case "$DNS_PORT" in
        ''|*[!0-9]*) echo "[vpn] invalid STREMIO_DNS_PROXY_PORT=$DNS_PORT" >&2; exit 64 ;;
    esac
    [ "$DNS_PORT" -ge 1 ] && [ "$DNS_PORT" -le 65535 ] || {
        echo "[vpn] invalid STREMIO_DNS_PROXY_PORT=$DNS_PORT" >&2
        exit 64
    }
    command -v socat >/dev/null 2>&1 || {
        echo "[vpn] socat is required for the Pi-hole DNS proxy" >&2
        exit 70
    }
    stop_dns_proxy
    socat TCP4-LISTEN:"$DNS_PORT",reuseaddr,fork TCP4:"$target":53 &
    DNS_TCP_PID=$!
    socat UDP4-LISTEN:"$DNS_PORT",reuseaddr,fork UDP4:"$target":53 &
    DNS_UDP_PID=$!
    echo "[vpn] DNS proxy :$DNS_PORT -> $target:53"
}

restore_direct_network() {
    # The namespace belongs only to this gateway + Stremio. Clear any Gluetun
    # firewall residue only after an explicit user-requested VPN disable.
    if command -v iptables >/dev/null 2>&1; then
        iptables -P INPUT ACCEPT >/dev/null 2>&1 || true
        iptables -P OUTPUT ACCEPT >/dev/null 2>&1 || true
        iptables -P FORWARD ACCEPT >/dev/null 2>&1 || true
        iptables -F >/dev/null 2>&1 || true
        iptables -t nat -F >/dev/null 2>&1 || true
        iptables -t mangle -F >/dev/null 2>&1 || true
        iptables -X >/dev/null 2>&1 || true
    fi
    if [ -n "$DIRECT_DEFAULT" ]; then
        # shellcheck disable=SC2086
        ip route replace $DIRECT_DEFAULT >/dev/null 2>&1 || true
    fi
}

select_profile() {
    PROFILE_ID=""
    if PROFILE_ID=$(read_id "$NEXT_FILE" 2>/dev/null); then
        rm -f "$NEXT_FILE"
    elif PROFILE_ID=$(read_id "$STARTUP_FILE" 2>/dev/null); then
        :
    elif PROFILE_ID=$(read_id "$ACTIVE_FILE" 2>/dev/null); then
        :
    else
        return 1
    fi
    printf '%s' "$PROFILE_ID"
}

prepare_profile() {
    PROFILE_ID=$(select_profile) || {
        echo "[vpn] VPN enabled but no connection profile is selected." >&2
        return 1
    }
    PROFILE_DIR="$PROFILES_DIR/$PROFILE_ID"
    for file in profile.json openvpn.runtime.ovpn ca.crt client.crt client.key username password; do
        if [ ! -s "$PROFILE_DIR/$file" ]; then
            echo "[vpn] selected profile '$PROFILE_ID' is incomplete: missing $file" >&2
            return 1
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

    printf '%s\n' "$PROFILE_ID" > "$ACTIVE_FILE.tmp"
    chmod 600 "$ACTIVE_FILE.tmp"
    mv -f "$ACTIVE_FILE.tmp" "$ACTIVE_FILE"
    return 0
}

start_vpn_child() {
    prepare_profile || return 1
    stop_dns_proxy
    # Gluetun's resolver binds 127.0.0.1:53 in this same namespace.
    start_dns_proxy 127.0.0.1
    echo "[vpn] enabling VPN profile: $PROFILE_ID"
    echo "[vpn] allowed outbound LAN subnets: $FIREWALL_OUTBOUND_SUBNETS"
    /gluetun-entrypoint "$@" &
    VPN_PID=$!
    return 0
}

stop_vpn_child_for_direct() {
    if [ -n "$VPN_PID" ]; then
        echo "[vpn] disabling VPN; returning gateway to direct mode"
        kill -TERM "$VPN_PID" >/dev/null 2>&1 || true
        wait "$VPN_PID" 2>/dev/null || true
        VPN_PID=""
    fi
    restore_direct_network
    start_dns_proxy "$DIRECT_DNS"
}

cleanup() {
    rm -f "$READY_FILE"
    stop_dns_proxy
    if [ -n "$VPN_PID" ]; then
        kill -TERM "$VPN_PID" >/dev/null 2>&1 || true
        wait "$VPN_PID" 2>/dev/null || true
    fi
}

trap cleanup INT TERM EXIT

mkdir -p "$CONFIG_DIR" "$PROFILES_DIR"
chmod 700 "$CONFIG_DIR" "$PROFILES_DIR" 2>/dev/null || true
DIRECT_DEFAULT=$(ip route show default 2>/dev/null | sed -n '1p' || true)

# DIRECT is a normal supported state. The container and namespace remain alive
# so Stremio configuration saves/restarts never depend on VPN availability.
restore_direct_network
start_dns_proxy "$DIRECT_DNS"
touch "$READY_FILE"
echo "[vpn] gateway supervisor ready; initial state: $(vpn_enabled && echo VPN-enabled || echo DIRECT)"

while :; do
    if vpn_enabled; then
        if [ -n "$VPN_PID" ] && [ -s "$NEXT_FILE" ]; then
            echo "[vpn] connection change requested; recycling VPN child without restarting gateway container"
            kill -TERM "$VPN_PID" >/dev/null 2>&1 || true
            wait "$VPN_PID" 2>/dev/null || true
            VPN_PID=""
            stop_dns_proxy
            rm -f "$READY_FILE"
            sleep 1
            continue
        fi

        if [ -z "$VPN_PID" ]; then
            if ! start_vpn_child "$@"; then
                echo "[vpn] VPN remains enabled but cannot start; keeping direct transition disabled" >&2
                stop_dns_proxy
                sleep 5
                continue
            fi
        fi

        # Keep the gateway process under supervision without restarting the
        # container/network namespace. Explicit disable is the only path back
        # to direct egress.
        if ! kill -0 "$VPN_PID" >/dev/null 2>&1; then
            wait "$VPN_PID" 2>/dev/null || true
            VPN_PID=""
            echo "[vpn] Gluetun exited while VPN is enabled; retrying without enabling direct fallback" >&2
            stop_dns_proxy
            sleep 5
            continue
        fi
    else
        if [ -n "$VPN_PID" ]; then
            stop_vpn_child_for_direct
        fi
        # Recover a direct DNS proxy if it died unexpectedly.
        if [ -n "$DNS_TCP_PID" ] && ! kill -0 "$DNS_TCP_PID" >/dev/null 2>&1; then
            start_dns_proxy "$DIRECT_DNS"
        fi
    fi
    sleep 1
done
