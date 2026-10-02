#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
echo "[vpn] start-vpn.sh is kept only for compatibility."
echo "[vpn] This release uses one compose.yaml. Start the platform normally and enable VPN in WebAdmin -> VPN."
exec sh "$ROOT/start.sh" "$@"
