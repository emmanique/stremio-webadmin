#!/bin/sh
# Read-only VPN diagnostics: never prints private keys or modifies networking.
set -u
CONTAINER="${1:-stremio-gluetun}"
status=0
echo "VPN_DIAGNOSTICS_V1"
if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then echo "CONTAINER=missing"; exit 2; fi
echo "CONTAINER=present"
container_health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$CONTAINER" 2>/dev/null || true)"
echo "CONTAINER_HEALTH=$container_health"
# Container process health is not evidence of VPN connectivity.
profile="$(docker exec "$CONTAINER" cat /vpn/active_profile 2>/dev/null || true)"
case "$profile" in *[!a-zA-Z0-9_-]*|'') profile=unknown;; esac
echo "ACTIVE_PROFILE=$profile"
if docker exec "$CONTAINER" wg show all latest-handshakes >/dev/null 2>&1; then
    echo "PROTOCOL=wireguard"
    result="$(docker exec "$CONTAINER" wg show all latest-handshakes 2>/dev/null)"
    handshake="$(printf '%s\n' "$result" | awk 'NR==1 {print $3}')"
    case "$handshake" in
        ''|0|*[!0-9]*) echo "HANDSHAKE=missing"; status=1;;
        *) now="$(date +%s)"; age="$((now - handshake))"
           if [ "$age" -gt 120 ] || [ "$age" -lt 0 ]; then
               echo "HANDSHAKE=stale"; status=1
           else echo "HANDSHAKE=recent"; fi;;
    esac
    transfer="$(docker exec "$CONTAINER" wg show all transfer 2>/dev/null)"
    rx="$(printf '%s\n' "$transfer" | awk 'NR==1 {print $3}')"
    case "$rx" in ''|0|*[!0-9]*) echo "RX=zero"; status=1;; *) echo "RX=present";; esac
else
    echo "PROTOCOL=other_or_down"
    status=1
fi
if docker exec "$CONTAINER" sh -c 'nc -z -w 2 127.0.0.1 53' >/dev/null 2>&1; then
    echo "LOCAL_DNS_TCP=ready"
else
    echo "LOCAL_DNS_TCP=unavailable"
    status=1
fi
if docker exec "$CONTAINER" sh -c 'nslookup example.com 1.1.1.1' >/dev/null 2>&1; then
    echo "EXTERNAL_DNS=ready"
else
    echo "EXTERNAL_DNS=unavailable"
    status=1
fi
# Detect accumulated firewall rules without modifying live iptables.
for chain in INPUT OUTPUT; do
    rules="$(docker exec "$CONTAINER" iptables -S "$chain" 2>/dev/null || true)"
    if [ -z "$rules" ]; then
        echo "FIREWALL_${chain}=unavailable"; status=1
    else
        duplicates="$(printf '%s\n' "$rules" | grep '^-A ' | sort | uniq -d | wc -l | tr -d ' ')"
        if [ "$duplicates" -gt 0 ]; then
            echo "FIREWALL_${chain}=duplicate_rules:$duplicates"; status=1
        else
            echo "FIREWALL_${chain}=no_duplicates"
        fi
        default_policy="$(printf '%s\n' "$rules" | head -n 1)"
        if [ "$default_policy" != "-P $chain DROP" ]; then
            echo "FIREWALL_${chain}_POLICY=unexpected"; status=1
        fi
    fi
done
if [ "$status" -eq 0 ]; then echo "VPN_SERVICE=operational"; else echo "VPN_SERVICE=degraded"; fi
# Application readiness is assessed independently, even if VPN is degraded.
webadmin_url="${STREMIO_WEBADMIN_URL:-http://$(hostname -I 2>/dev/null | awk '{print $1}'):8090/}"
app_status="$(curl --max-time 4 --silent --output /dev/null --write-out '%{http_code}' "$webadmin_url" 2>/dev/null || true)"
case "$app_status" in
  2??|3??) echo "STREMIO_WEBADMIN=reachable";;
  *) echo "STREMIO_WEBADMIN=unreachable";;
esac
echo "DIAGNOSTIC_SCOPE=container_vpn_app_independent"
exit "$status"
