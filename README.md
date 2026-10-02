# Stremio Server WebAdmin 2.0.3

[![2.x Continuous Validation](https://github.com/emmanique/stremio-libtorrent-server-webadmin/actions/workflows/2x-ci.yml/badge.svg?branch=develop%2F2.x)](https://github.com/emmanique/stremio-libtorrent-server-webadmin/actions/workflows/2x-ci.yml)
[![VPN integration guard](https://github.com/emmanique/stremio-libtorrent-server-webadmin/actions/workflows/vpn-integration-guard.yml/badge.svg)](https://github.com/emmanique/stremio-libtorrent-server-webadmin/actions/workflows/vpn-integration-guard.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-3DA639.svg)](LICENSE)

Self-hosted Stremio streaming platform with an open libtorrent server, WebAdmin, Pi-hole, hardware transcoding support and optional CyberGhost/OpenVPN routing through Gluetun.

Version **2.0.3** integrates upstream server/core **1.6.14** while keeping the fork platform, WebAdmin and VPN gateway on the independent **2.0.3** release line. It uses one runtime topology and one primary Compose file.

> This repository does not bundle movies, series, torrent indexes or third-party content addons.

---

## 2.0.3 at a glance

```text
Upstream Core  1.6.14
Upstream Server 1.6.14
WebAdmin    2.0.3
VPN Gateway 2.0.3
```

Version sources:

```text
pyproject.toml
SERVER_VERSION
FORK_VERSION
webadmin/WEBADMIN_VERSION
```

`SERVER_VERSION` and `pyproject.toml` must match the integrated upstream server/core release. `FORK_VERSION` and `webadmin/WEBADMIN_VERSION` must match the 2.x fork release. These version lines are intentionally independent.

---

# Architecture

## One stack, two operating states

Version 2.x removes the old split between `compose.yaml` and `compose.vpn.yaml`.

The platform always starts from:

```bash
docker compose up -d
```

or:

```bash
sh start.sh
```

Runtime topology:

```text
                         Host / LAN
                             │
               ┌─────────────┼─────────────┐
               │             │             │
               ▼             ▼             ▼
          WebAdmin :8090  Pi-hole :8053  Published Stremio ports
               │             │             │
               │             │             ▼
               │             └──────► stremio-gluetun
               │                        │
               │                        │ persistent network namespace
               │                        ▼
               └────────────────► stremio-libtorrent-server
```

Gluetun is always present as the stable gateway/network namespace.

Its internal VPN state is independent:

```text
VPN OFF
  Gluetun container: running
  OpenVPN tunnel:    stopped
  Stremio egress:    direct

VPN ON
  Gluetun container: running
  OpenVPN tunnel:    running
  Stremio egress:    VPN

VPN ON + tunnel failure
  Gluetun container: running
  OpenVPN tunnel:    failed/recovering
  Stremio egress:    blocked/fail-closed
```

The gateway container is not stopped when the user disables VPN.

---

# First installation

Clone the repository:

```bash
git clone https://github.com/emmanique/stremio-libtorrent-server-webadmin.git
cd stremio-libtorrent-server-webadmin
sh start.sh
```

The initial installation does **not** require a VPN account.

Expected initial state:

```text
stremio-gluetun             running / DIRECT
stremio-libtorrent-server   running
stremio-webadmin            running
stremio-pihole              running
```

Access points for a host such as `192.168.1.245`:

| Service | Address |
| --- | --- |
| Web Player | `http://192.168.1.245:8080` |
| WebAdmin | `http://192.168.1.245:8090` |
| Streaming API | `http://192.168.1.245:11470` |
| Trusted HTTPS / Library | `https://<trusted-host>:12470/` |
| Pi-hole Admin | `http://192.168.1.245:8053/admin/` |
| BitTorrent | `6881/tcp` and `6881/udp` |

To override automatic LAN IP detection:

```bash
IPADDRESS=192.168.1.245 sh start.sh
```

---

# VPN

VPN configuration is performed from:

```text
WebAdmin → VPN
```

A fresh installation shows VPN as disabled until a valid CyberGhost/OpenVPN profile exists.

A CyberGhost ZIP is expected to contain:

```text
openvpn.ovpn
ca.crt
client.crt
client.key
```

The profile also stores the generated OpenVPN username/password in the private `vpn-data` volume.

## State model

```text
NOT CONFIGURED
      │
      ▼
CONFIGURED / OFF
      │ Enable VPN
      ▼
STARTING
   ┌──┴────┐
   ▼       ▼
CONNECTED ERROR
   │
   │ Disable VPN
   ▼
DIRECT
```

VPN enable state is persistent.

If the host reboots while VPN was enabled, the supervisor restores the requested VPN state instead of intentionally returning to direct mode.

## Profile change

Changing the active VPN profile does not restart the Gluetun container. Only the VPN child/tunnel is recycled so the Stremio network namespace remains stable.

## Compatibility launcher

`start-vpn.sh`, `start-vpn.ps1` and `start-vpn.bat` are retained only for compatibility.

They now start the same unified Compose stack. VPN itself is controlled from WebAdmin.

---

# Configuration persistence and restart reliability

Version 2.x treats configuration persistence as a release-blocking capability.

WebAdmin mounts:

```text
stremio-config:/config
```

read/write.

Stremio mounts the same volume:

```text
stremio-config:/config:ro
```

The save path is:

```text
/config/admin-settings.json
```

Save flow:

```text
WebAdmin
   │
   ▼
atomic write to temporary file
   │
   ▼
fsync
   │
   ▼
atomic replace
   │
   ▼
read-back verification
   │
   ▼
docker exec Stremio:
cat /config/admin-settings.json
   │
   ▼
saved values must match
```

The Server restart endpoint uses Docker directly:

```text
POST /api/restart
      │
      ▼
docker restart stremio-libtorrent-server
      │
      ▼
StartedAt must change
      │
      ▼
curl 127.0.0.1:11470/health
inside the Stremio container
```

This management path does not depend on the VPN being connected.

Required behavior:

| VPN state | Save configuration | Restart Server |
| --- | --- | --- |
| Not configured | Yes | Yes |
| Configured / OFF | Yes | Yes |
| Connected | Yes | Yes |
| VPN error | Yes | Yes |

---

# Pi-hole and DNS

Pi-hole uses one stable internal upstream:

```text
172.30.0.10#1053
```

The persistent gateway exposes this private DNS bridge.

In DIRECT mode:

```text
Stremio
   ↓
Pi-hole
   ↓
Gateway DNS bridge
   ↓
configured public resolver
   ↓
Internet
```

In VPN mode:

```text
Stremio
   ↓
Pi-hole
   ↓
Gateway DNS bridge
   ↓
Gluetun resolver
   ↓
VPN tunnel
```

The Pi-hole performance/security baseline remains controlled through Compose `FTLCONF_*` values.

To expose Pi-hole DNS to the LAN:

```bash
docker compose -f compose.yaml -f compose.dns.yaml up -d
```

---

# Transcoding

The project keeps the copy-first policy: compatible media is not needlessly transcoded.

Supported execution profiles include:

```text
Preserve Stremio decision
H.264 VAAPI
HEVC VAAPI
H.264 VAAPI Full GPU
HEVC VAAPI Full GPU
H.264 NVIDIA NVENC
HEVC NVIDIA NVENC
H.264 CPU / libx264
HEVC CPU / libx265
```

Hardware profiles are exposed only after runtime verification.

VAAPI overlay:

```bash
docker compose -f compose.yaml -f compose.vaapi.yaml up -d
```

NVIDIA overlay:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml up -d
```

---

# Persistent data

Normal upgrades preserve named volumes.

Important volumes:

```text
stremio-cache
stremio-config
webadmin-data
pihole-etc
pihole-dnsmasq
vpn-data
gluetun-data
```

Do not use:

```bash
docker compose down -v
```

for routine upgrades.

---

# Upgrading from a previous version

The normal upgrade path preserves the named Docker volumes and therefore keeps WebAdmin settings, Stremio configuration/cache, Pi-hole data and VPN profile/state.

Before upgrading, confirm the current installation directory and optionally record the running images:

```bash
cd ~/stremio-libtorrent-server-webadmin
docker compose ps
docker compose images
```

Upgrade a normal Git-based installation from **2.0.2 or an earlier 2.x release** to the current release:

```bash
cd ~/stremio-libtorrent-server-webadmin

git fetch --prune origin
git checkout main
git pull --ff-only origin main

docker compose pull
sh start.sh
```

Do **not** run `docker compose down -v`: the `-v` option deletes the persistent named volumes.

After the upgrade, validate the stack:

```bash
docker compose ps
curl -fsS http://127.0.0.1:8090/health
curl -fsS http://127.0.0.1:11470/health
```

For a LAN host such as `192.168.1.245`, also verify the WebAdmin and server externally:

```bash
curl -fsS http://192.168.1.245:8090/health
curl -fsS http://192.168.1.245:11470/health
```

Then confirm in WebAdmin that the saved configuration is still present and that the expected VPN state is shown. A server restart from WebAdmin should complete without losing `/config/admin-settings.json`.

If the previous installation used the old `compose.vpn.yaml` topology, do not continue launching that file. Version 2.x uses the unified `compose.yaml`; `start-vpn.sh` is only a compatibility wrapper and VPN enable/disable is controlled from WebAdmin.

For VAAPI installations, start with the hardware overlay after updating:

```bash
docker compose -f compose.yaml -f compose.vaapi.yaml pull
docker compose -f compose.yaml -f compose.vaapi.yaml up -d
```

For NVIDIA installations:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml pull
docker compose -f compose.yaml -f compose.gpu.yaml up -d
```

## Rollback after an upgrade

If an upgrade must be rolled back, keep the persistent volumes and return the repository to the previous release tag, for example `v2.0.2`:

```bash
cd ~/stremio-libtorrent-server-webadmin
git fetch --tags origin
git checkout v2.0.2
docker compose pull
sh start.sh
```

Do not use `down -v` during rollback. After validation, return to the stable branch with `git checkout main`.

## Development 2.x installation

```bash
git fetch --prune origin
git checkout develop/2.x
git pull --ff-only origin develop/2.x
sh start.sh
```

---

# Published images

## GitHub Container Registry

```text
ghcr.io/emmanique/stremio-libtorrent-server-webadmin:2.0.3
ghcr.io/emmanique/stremio-libtorrent-server-webadmin-webadmin:2.0.3
ghcr.io/emmanique/stremio-libtorrent-server-webadmin-vpn:2.0.3
```

Stable moving aliases:

```text
:2
:latest
```

These aliases are updated only by the validated 2.x release workflow.

## Docker Hub

```text
edmanique/stremio-libtorrent-server-webadmin:2.0.3
edmanique/stremio-libtorrent-server-webadmin:webadmin-2.0.3
edmanique/stremio-libtorrent-server-webadmin:vpn-2.0.3
```

---

# Repository automation

The repository uses five permanent workflows for CI, dependency validation, coordinated version bumps, releases and selective upstream review.

See [docs/WORKFLOWS.md](docs/WORKFLOWS.md) for the complete operating model.

---

# Development model

2.x uses dedicated branches:

```text
feature/*
    │
    ▼
develop/2.x
    │
    ▼
release/2.x.y
    │
    ▼
main
    │
    ▼
v2.x.y
```

Urgent fixes:

```text
main
  │
  ▼
hotfix/2.x.y
  │
  ├──► main
  └──► develop/2.x
```

See [docs/BRANCHING-2X.md](docs/BRANCHING-2X.md).

---

# CI/CD for 2.x

## 2.x Continuous Validation

`.github/workflows/2x-ci.yml`

Validates:
- unified component versions;
- Python/Ruff syntax and style;
- shell scripts;
- WebAdmin JavaScript syntax;
- unified Compose and overlays;
- full pytest suite;
- Save Configuration regression;
- Server Restart regression;
- VPN single-Compose regression;
- Server/WebAdmin/VPN Docker builds;
- image smoke tests.

## 2.x Dependency Validation

`.github/workflows/2x-dependency-validation.yml`

Runs for dependency changes and validates:
- `uv.lock`;
- Python dependency consistency;
- dependency audit;
- runtime-sensitive tests;
- Docker builds.

## Dependency updates

`.github/dependabot.yml`

Dependabot checks weekly:
- root Python packages;
- WebAdmin Python packages;
- root/WebAdmin/VPN Docker bases;
- GitHub Actions.

Updates target `develop/2.x`, not `main`.

## 2.x Release

`.github/workflows/2x-release.yml`

Triggered by:

```text
v2.x.y
```

The release workflow:
1. validates version consistency;
2. runs the complete test gate;
3. validates Compose;
4. builds Server, WebAdmin and VPN images;
5. smoke-tests images;
6. publishes GHCR versioned, `:2` and `:latest` tags;
7. mirrors the validated images to Docker Hub when credentials are configured;
8. creates or updates the GitHub Release from `docs/releases/v2.x.y.md`.

Legacy 1.x release automation is isolated from 2.x tags.

---

# Repository structure

```text
compose.yaml
compose.dns.yaml
compose.vaapi.yaml
compose.gpu.yaml

start.sh
start-vpn.sh                 compatibility wrapper

src/                         Stremio server
webadmin/                    WebAdmin
vpn/                         persistent gateway/VPN supervisor
docker/                      runtime wrappers and publishing helpers
tests/                       unit and regression tests
tools/                       host-side validation tools

docs/BRANCHING-2X.md
docs/releases/
VERSIONING.md

.github/workflows/2x-ci.yml
.github/workflows/2x-dependency-validation.yml
.github/workflows/2x-release.yml
.github/dependabot.yml
```

---

# Security notes

- WebAdmin has access to the Docker socket and must remain on a trusted LAN/VPN.
- Do not expose port 8090 directly to the public Internet.
- VPN credentials, private keys and certificates remain in `vpn-data`.
- Keep the VPN kill switch enabled.
- Do not store passwords, tokens or VPN credentials in tracked `.env` files.
- Treat Library Addon URLs/tokens as secrets.

---

# Release information

Current planned release:

[docs/releases/v2.0.3.md](docs/releases/v2.0.3.md)

Versioning:

[VERSIONING.md](VERSIONING.md)

Branch strategy:

[docs/BRANCHING-2X.md](docs/BRANCHING-2X.md)

---

## License

MIT. See [LICENSE](LICENSE).
