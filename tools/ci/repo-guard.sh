#!/usr/bin/env bash
set -euo pipefail
trap 'echo "repo-guard failed at line $LINENO: $BASH_COMMAND" >&2' ERR

for file in   SERVER_VERSION FORK_VERSION VERSIONING.md VPN.md compose.yaml   start.sh start-vpn.sh vpn/Dockerfile vpn/entrypoint.sh Dockerfile   webadmin/Dockerfile webadmin/WEBADMIN_VERSION webadmin/app.py   webadmin/fork_update.py webadmin/package_update.py webadmin/version_lifecycle.py   webadmin/vpn_admin.py webadmin/vpn_profiles.py webadmin/transcoding_config.py   webadmin/transcoding_runtime_fix.py webadmin/transcoding_profiles.py   webadmin/transcoding_verified_status.py webadmin/static/vpn-admin.js tools/release/prepare_version.py tools/release/build_deployment_package.py scripts/backup-before-upgrade.sh docs/BRANCHING.md docs/TESTING.md docs/DEPLOYMENT_PACKAGE.md; do
  test -f "$file" || { echo "Missing fork-owned file: $file" >&2; exit 1; }
done

SERVER="$(tr -d '[:space:]' < SERVER_VERSION)"
FORK="$(tr -d '[:space:]' < FORK_VERSION)"
WEBADMIN="$(tr -d '[:space:]' < webadmin/WEBADMIN_VERSION)"
CORE="$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1)"

test "$FORK" = "$WEBADMIN"
test "$SERVER" = "$CORE"
case "$FORK" in 2.*) ;; *) echo "Fork release line requires a 2.x version" >&2; exit 1;; esac
case "$SERVER" in 1.*) ;; *) echo "SERVER_VERSION must reflect the integrated upstream 1.x release" >&2; exit 1;; esac

grep -q '^  gluetun:' compose.yaml
grep -q 'network_mode: "service:gluetun"' compose.yaml
grep -q 'STREMIO_VPN_ENABLED_FILE: /vpn/enabled' compose.yaml
grep -q 'FTLCONF_dns_upstreams: "172.30.0.10#1053"' compose.yaml
grep -q 'HTTP_CONTROL_SERVER_AUTH_DEFAULT_ROLE' compose.yaml
grep -q 'stremio-config:/config:ro' compose.yaml
grep -q 'vpn-data:/vpn' compose.yaml
grep -q 'ghcr.io/emmanique/stremio-libtorrent-server-webadmin:latest' compose.yaml
grep -q 'ghcr.io/emmanique/stremio-libtorrent-server-webadmin-webadmin:latest' compose.yaml
grep -q 'STREMIO_PACKAGE_REPO' compose.yaml
if grep -Eq '^[[:space:]]+build:' compose.yaml; then
  echo "Default compose.yaml must consume published images." >&2
  exit 1
fi

server_block="$(awk '/^  stremio-libtorrent-server:/{flag=1;next}/^  [A-Za-z0-9_-]+:/{if(flag)exit}flag' compose.yaml)"
if printf '%s\n' "$server_block" | grep -q '^[[:space:]]*devices:'; then
  echo "Base compose must not require a GPU/VAAPI device." >&2
  exit 1
fi
grep -q '${VAAPI_DEVICE:?VAAPI_DEVICE must point to a detected /dev/dri/renderD\* device}' compose.vaapi.yaml

grep -q 'COPY vpn_profiles.py' webadmin/Dockerfile
grep -q 'vpn_profiles.install(app)' webadmin/transcoding_verified_status.py
grep -q 'OPENVPN_CUSTOM_CONFIG' vpn/entrypoint.sh
grep -q 'startup_profile' vpn/entrypoint.sh
grep -q 'next_profile' vpn/entrypoint.sh
grep -q 'gateway supervisor ready' vpn/entrypoint.sh
grep -q '_set_vpn_requested(True)' webadmin/vpn_profiles.py
! grep -q 'gluetun.restart(' webadmin/vpn_profiles.py

grep -q 'update-checkpoint.json' webadmin/fork_update.py
grep -q 'rollback' webadmin/fork_update.py
grep -q '_wait_healthy' webadmin/fork_update.py
grep -q '_restore_old_container' webadmin/fork_update.py
grep -q 'images.pull' webadmin/package_update.py
grep -q '_activate_image' webadmin/package_update.py
grep -q '/api/component-versions' webadmin/version_lifecycle.py

grep -q 'httpsCert.json' webadmin/version_lifecycle.py
grep -q 'STREMIO_ROCKS_RE' webadmin/version_lifecycle.py
grep -q '/api/transcoding/profiles' webadmin/transcoding_profiles.py
grep -q 'runtime-profile-self-test' webadmin/transcoding_verified_status.py

grep -q 'images.metahub.space/poster/medium' src/stremiosrv/library/__init__.py
grep -q 'v3-cinemeta.strem.io' src/stremiosrv/library/metadata.py
grep -q '/api/addons/library/update' webadmin/addon_links.py

if grep -R --line-number --fixed-strings   'https://github.com/andrewhack/stremio-libtorrent-server'   webadmin compose.yaml Dockerfile docker/webadmin_entrypoint.py docker/ffmpeg_wrapper.py; then
  echo "Runtime/update paths must not use the principal repository directly." >&2
  exit 1
fi

for path in start.sh start-vpn.sh vpn compose.gpu.yaml compose.hub.yaml docker/launch.sh docker/publish.sh docker/push-readme.sh; do
  grep -Fxq "$path" .github/upstream-protected-paths.txt || {
    echo "$path must remain protected from upstream sync." >&2
    exit 1
  }
done

# Deployment/release governance must remain present.
grep -q 'IPADDRESS_SOURCE=' .env.example
grep -q 'STREMIO_DIRECT_DNS_UPSTREAM=' .env.example
grep -q 'backup-before-upgrade.sh' README.md
grep -q 'development' docs/BRANCHING.md
grep -q 'Full regression' docs/TESTING.md
! git ls-files | grep -Eq '(^|/)(\.venv-test|\.pytest_cache|__pycache__)(/|$)|\.env\.backup-'
