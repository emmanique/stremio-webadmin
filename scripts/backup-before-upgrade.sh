#!/bin/sh
# Backup deployment configuration and persistent state before an upgrade.
# Usage:
#   sh scripts/backup-before-upgrade.sh
#   sh scripts/backup-before-upgrade.sh --with-cache
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

STAMP=$(date '+%Y%m%d-%H%M%S')
DEST=${BACKUP_DIR:-"$ROOT/backups/pre-upgrade-$STAMP"}
WITH_CACHE=false
[ "${1:-}" = "--with-cache" ] && WITH_CACHE=true

mkdir -p "$DEST/files" "$DEST/volumes"

for f in .env compose.yaml compose.dns.yaml compose.gpu.yaml compose.vaapi.yaml compose.hub.yaml; do
    [ -f "$f" ] && cp -p "$f" "$DEST/files/"
done

# Store the exact resolved Compose model and current image/container state.
docker compose config > "$DEST/compose.resolved.yaml"
docker compose images > "$DEST/compose-images.txt" 2>&1 || true
docker compose ps > "$DEST/compose-ps.txt" 2>&1 || true

backup_volume() {
    logical=$1
    actual="stremio-platform_${logical}"
    if ! docker volume inspect "$actual" >/dev/null 2>&1; then
        echo "[backup] skip missing volume: $actual"
        return 0
    fi
    echo "[backup] $actual"
    docker run --rm \
        -v "$actual:/source:ro" \
        -v "$DEST/volumes:/backup" \
        alpine:3.20 \
        sh -c "cd /source && tar -czf /backup/${logical}.tar.gz ."
}

# Configuration/state required to preserve the installation behaviour.
for v in stremio-config webadmin-data vpn-data gluetun-data pihole-etc pihole-dnsmasq; do
    backup_volume "$v"
done

# Cache/library data can be large; make it opt-in.
if [ "$WITH_CACHE" = "true" ]; then
    backup_volume stremio-cache
fi

cat > "$DEST/RESTORE-NOTES.txt" <<NOTES
Backup created: $STAMP

Critical local file:
  files/.env

Critical persistent volumes:
  stremio-config
  webadmin-data
  vpn-data
  gluetun-data
  pihole-etc
  pihole-dnsmasq

Optional large volume:
  stremio-cache (included only with --with-cache)

Before restoring a volume, stop the stack and verify that the target volume name
still uses the stremio-platform_ prefix.
NOTES

echo "[backup] completed: $DEST"
