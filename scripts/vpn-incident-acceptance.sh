#!/bin/sh
# Non-destructive production VPN incident acceptance checks.
# Usage: sh scripts/vpn-incident-acceptance.sh [hostname-or-ip]
set -u
HOST="${1:-127.0.0.1}"
PASS=0; FAIL=0; WARN=0
pass(){ printf 'PASS %s\n' "$1"; PASS=$((PASS+1)); }
fail(){ printf 'FAIL %s\n' "$1"; FAIL=$((FAIL+1)); }
warn(){ printf 'WARN %s\n' "$1"; WARN=$((WARN+1)); }
echo "=== STREMIO VPN INCIDENT ACCEPTANCE ==="
for c in stremio-gluetun stremio-libtorrent-server stremio-webadmin stremio-pihole; do
    h="$(docker inspect "$c" --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' 2>/dev/null || true)"
    [ "$h" = healthy ] && pass "container:$c" || fail "container:$c:$h"
done
if docker exec stremio-gluetun wg show all latest-handshakes >/dev/null 2>&1; then
    stamp="$(docker exec stremio-gluetun wg show all latest-handshakes 2>/dev/null | awk 'NR==1 {print $3}')"
    now="$(date +%s)"
    if [ -n "$stamp" ] && [ "$stamp" -gt 0 ] 2>/dev/null && [ "$((now-stamp))" -ge 0 ] && [ "$((now-stamp))" -le 120 ]; then
        pass "wireguard:recent_handshake"
    else fail "wireguard:handshake_missing_or_stale"; fi
    rx="$(docker exec stremio-gluetun wg show all transfer 2>/dev/null | awk 'NR==1 {print $3}')"
    if [ "${rx:-0}" -gt 0 ] 2>/dev/null; then pass "wireguard:rx_nonzero"; else fail "wireguard:rx_zero"; fi
else fail "wireguard:interface"; fi
for chain in INPUT OUTPUT; do
    rules="$(docker exec stremio-gluetun iptables -S "$chain" 2>/dev/null || true)"
    printf '%s\n' "$rules" | grep -qx -- "-P $chain DROP" && pass "kill_switch:$chain-DROP" || fail "kill_switch:$chain"
    dup="$(printf '%s\n' "$rules" | grep "^-A $chain " | sort | uniq -d | wc -l)"
    [ "$dup" -eq 0 ] && pass "firewall:$chain-idempotent" || fail "firewall:$chain-duplicate-$dup"
done
docker exec stremio-pihole nslookup example.com 1.1.1.1 >/dev/null 2>&1 && pass "pihole:dns" || fail "pihole:dns"
docker exec stremio-gluetun nslookup example.com 1.1.1.1 >/dev/null 2>&1 && pass "vpn:dns" || fail "vpn:dns"
active="$(docker exec stremio-gluetun cat /vpn/active_profile 2>/dev/null || true)"
pf="$(docker exec stremio-gluetun cat "/vpn/profiles/$active/profile.json" 2>/dev/null | grep '"portForwarding"' | head -1 || true)"
if printf '%s' "$pf" | grep -q 'true'; then
    if docker exec stremio-gluetun test -s /vpn/forwarded_port >/dev/null 2>&1; then pass "proton:natpmp_lease"; else fail "proton:natpmp_lease"; fi
else
    warn "proton:natpmp_not_enabled_in_profile"
fi
code="$(curl --silent --max-time 5 --output /dev/null --write-out '%{http_code}' "http://$HOST:8090/" 2>/dev/null)"
[ "$code" = 200 ] && pass "webadmin:http" || fail "webadmin:http-$code"
code="$(curl --insecure --silent --max-time 5 --output /dev/null --write-out '%{http_code}' "https://$HOST:12470/" 2>/dev/null)"
[ "$code" = 200 ] && pass "stremio:https" || fail "stremio:https-$code"
docker exec stremio-libtorrent-server test -c /dev/dri/renderD128 >/dev/null 2>&1 && pass "vaapi:render_node" || fail "vaapi:render_node"
for enc in h264_vaapi hevc_vaapi; do
 docker exec stremio-libtorrent-server ffmpeg -hide_banner -encoders 2>/dev/null | grep -q "$enc" && pass "vaapi:$enc" || fail "vaapi:$enc"
done
warn "playback:requires_end_to_end_test_with_media"
warn "dns_leaks:requires_packet_capture_from_clients"
warn "router_wan_nat:requires_router_or_wan_observation"
printf 'SUMMARY PASS=%s FAIL=%s WARN=%s\n' "$PASS" "$FAIL" "$WARN"
[ "$FAIL" -eq 0 ]
