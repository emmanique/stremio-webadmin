#!/usr/bin/env bash
set -euo pipefail

bash tools/ci/static-check.sh
bash tools/ci/compose-check.sh
python tools/ci/release-docs-check.py
bash tools/ci/run-tests.sh deterministic
bash tools/ci/run-tests.sh integration

build_retry() {
  tag="$1"; context="$2"
  for attempt in 1 2 3; do
    docker build -t "$tag" "$context" && return 0
    [ "$attempt" -eq 3 ] && return 1
    sleep $((attempt * 5))
  done
}

build_retry stremio-ci-server:test .
build_retry stremio-ci-webadmin:test ./webadmin
build_retry stremio-ci-vpn:test ./vpn

cleanup() {
  docker rm -f stremio-ci-server webadmin-ci >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

docker run -d --name stremio-ci-server -p 18099:11470 stremio-ci-server:test >/dev/null
for i in $(seq 1 120); do
  curl -fsS http://127.0.0.1:18099/health >/tmp/server-health.json 2>/dev/null && break
  sleep 1
done
test -s /tmp/server-health.json

docker run -d --name webadmin-ci -p 18090:8090 -v /var/run/docker.sock:/var/run/docker.sock stremio-ci-webadmin:test >/dev/null
for i in $(seq 1 90); do
  curl -fsS http://127.0.0.1:18090/health >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS http://127.0.0.1:18090/ | grep -q 'vpn-admin.js'
docker run --rm --entrypoint /bin/sh stremio-ci-vpn:test -c 'test -x /stremio-vpn-entrypoint && test -x /gluetun-entrypoint'

rm -rf dist
python tools/release/build_deployment_package.py
test -f dist/SHA256SUMS
(cd dist && sha256sum -c SHA256SUMS)
zipfile="$(find dist -maxdepth 1 -name '*-deployment.zip' -print -quit)"
test -n "$zipfile"
unzip -l "$zipfile" >/tmp/deployment-files.txt
! grep -Eq '(^|/)(tests|tools|\.github|src|webadmin|vpn)/' /tmp/deployment-files.txt
grep -q '/compose.yaml' /tmp/deployment-files.txt
grep -q '/\.env.example' /tmp/deployment-files.txt
grep -q '/scripts/backup-before-upgrade.sh' /tmp/deployment-files.txt

# Simulate a real first installation from the exact deployment artifact.
rm -rf /tmp/stremio-clean-install
mkdir -p /tmp/stremio-clean-install
unzip -q "$zipfile" -d /tmp/stremio-clean-install
install_root="$(find /tmp/stremio-clean-install -mindepth 1 -maxdepth 1 -type d -print -quit)"
test -n "$install_root"
cd "$install_root"
test ! -e .env
cp .env.example .env
IPADDRESS=192.0.2.10 IPADDRESS_SOURCE=manual GPU_BACKEND=cpu sh start.sh config >/tmp/clean-install-compose.yaml
grep -q 'stremio-libtorrent-server' /tmp/clean-install-compose.yaml
grep -q 'stremio-webadmin' /tmp/clean-install-compose.yaml
grep -q 'stremio-gluetun' /tmp/clean-install-compose.yaml

echo "Full regression passed."
