#!/usr/bin/env bash
set -euo pipefail
export IPADDRESS="${IPADDRESS:-192.0.2.10}"
export PIHOLE_WEB_BIND_IP="${PIHOLE_WEB_BIND_IP:-192.0.2.10}"
export PIHOLE_DNS_BIND_IP="${PIHOLE_DNS_BIND_IP:-192.0.2.10}"

docker compose -f compose.yaml config --quiet
server_json="$(docker compose -f compose.yaml config --format json)"
test "$(printf '%s' "$server_json" | jq -r '.services["stremio-libtorrent-server"].hostname // empty')" = ""
test "$(printf '%s' "$server_json" | jq -r '.services["stremio-libtorrent-server"].network_mode')" = "service:gluetun"
test "$(printf '%s' "$server_json" | jq -r '.services["stremio-libtorrent-server"].environment.TRANSCODING_HWACCEL')" = "cpu"
test "$(printf '%s' "$server_json" | jq -r '.services["stremio-libtorrent-server"].environment.TRANSCODING_VIDEO_CODEC')" = "libx264"
test "$(printf '%s' "$server_json" | jq -r '.services["stremio-libtorrent-server"].environment.TRANSCODING_HW_DECODE')" = "false"
test "$(printf '%s' "$server_json" | jq -r '.services["stremio-libtorrent-server"].environment.VAAPI_DEVICE // empty')" = ""

docker compose -f compose.yaml -f compose.dns.yaml config --quiet
VAAPI_DEVICE=/dev/dri/renderD129 docker compose -f compose.yaml -f compose.vaapi.yaml config --quiet
docker compose -f compose.yaml -f compose.gpu.yaml config --quiet
