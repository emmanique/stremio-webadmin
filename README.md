# Stremio Server WebAdmin 2.0.8

[![2.x Continuous Validation](https://github.com/emmanique/stremio-libtorrent-server-webadmin/actions/workflows/2x-ci.yml/badge.svg?branch=main)](https://github.com/emmanique/stremio-libtorrent-server-webadmin/actions/workflows/2x-ci.yml)
[![VPN integration guard](https://github.com/emmanique/stremio-libtorrent-server-webadmin/actions/workflows/vpn-integration-guard.yml/badge.svg)](https://github.com/emmanique/stremio-libtorrent-server-webadmin/actions/workflows/vpn-integration-guard.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-3DA639.svg)](LICENSE)

Self-hosted Stremio streaming platform with an open libtorrent server, WebAdmin, Pi-hole, hardware transcoding support and optional CyberGhost/OpenVPN routing through Gluetun.

Version **2.0.8** integrates upstream server/core **1.6.15** while keeping the fork platform, WebAdmin and VPN gateway on the independent **2.0.8** release line. It stabilizes configuration persistence/restart verification, VPN/DNS transitions, trusted certificate handling, automatic VAAPI capability verification and live FFmpeg runtime/policy telemetry.

> This repository does not bundle movies, series, torrent indexes or third-party content addons.

---

## 2.0.8 at a glance

```text
Upstream Core   1.6.15
Upstream Server 1.6.15
Fork            2.0.8
WebAdmin        2.0.8
VPN Gateway     2.0.8
```

Version sources:

```text
pyproject.toml
SERVER_VERSION
FORK_VERSION
webadmin/WEBADMIN_VERSION
```

`SERVER_VERSION` and `pyproject.toml` must match the integrated upstream server/core release. `FORK_VERSION` and `webadmin/WEBADMIN_VERSION` must match the 2.x fork release. These version lines are intentionally independent.

## What is implemented today

The current 2.0.8 baseline includes the work completed across the 2.x release line:

- unified `compose.yaml` runtime for Stremio Server, WebAdmin, Pi-hole and the persistent Gluetun gateway;
- VPN configuration and enable/disable lifecycle from WebAdmin, without a separate `compose.vpn.yaml`;
- persistent WebAdmin/server configuration in `/config/admin-settings.json`, with atomic save, read-back verification and reliable server restart;
- persistent Pi-hole DNS chain through the Gluetun private DNS bridge;
- VPN validation covering container health, control API, tunnel state, public IP, DNS, Pi-hole upstream, Stremio routing and kill switch;
- automatic VAAPI/GPU overlay detection while keeping the base Compose hardware-agnostic;
- copy-first transcoding policy: compatible H.264 can remain Direct Stream while incompatible HEVC can be converted to H.264 with VAAPI;
- full-GPU VAAPI profiles with hardware decode, `scale_vaapi` and hardware encode when the host supports them;
- automatic repair of a stale Stremio → Gluetun network namespace after Gluetun container recreation;
- versioned Server, WebAdmin and VPN images published through the validated release workflow;
- transactional server update metadata and rollback support exposed through WebAdmin;
- live per-session transcoding monitoring in WebAdmin, correlating each active FFmpeg process with its own job log and exposing Direct Stream/Transcoding state, source → target video/audio codecs, execution engine, PID, elapsed time, CPU/RAM, FFmpeg progress and the applied policy decision.

### 2.0.5 transcoding policy

The explicit transcoding profile now respects the Direct Stream codec allow-list instead of preserving every upstream `-c:v copy` decision unconditionally.

With a typical `vaapi-full-h264` configuration and `h264` as the Direct Stream video codec:

```text
H.264 source
  → video=copy preserved; source=h264; direct=yes
  → no unnecessary video transcode

HEVC/H.265 source
  → video=copy(hevc)->h264_vaapi
  → VAAPI hardware decode
  → scale_vaapi
  → H.264 VAAPI hardware encode
```

If codec probing cannot determine the source codec, the wrapper fails safely by preserving the original copy decision.

### 2.0.6 Gluetun namespace lifecycle

Stremio uses the Gluetun network namespace. Docker binds that relationship to a concrete Gluetun container ID when the Stremio container is created. If Gluetun is later recreated, an unchanged Stremio container can otherwise remain attached to the old namespace.

`start.sh` now performs a post-start integrity check:

```text
Gluetun starts / becomes healthy
          │
          ▼
Compare current Gluetun container ID
with Stremio NetworkMode
          │
     ┌────┴────┐
     │         │
   match     stale
     │         │
     ▼         ▼
   no-op   recreate only Stremio
               │
               ▼
         verify repaired namespace
```

The repair reuses the active Compose configuration and hardware overlay selection. Pi-hole and WebAdmin are not recreated merely to repair this relationship.

### 2.0.7 live transcoding monitor

WebAdmin now provides a live per-session view of active FFmpeg work instead of relying only on the most recently modified transcoding log. Each active process is correlated with its own job log, which makes simultaneous Direct Stream and transcoding sessions distinguishable.

The monitor exposes, when available:

```text
Session action      Direct Stream / Transcoding
Video               source codec → target codec
Audio               source codec → target codec
Engine              copy / VAAPI / CPU / other active engine
Process             PID and elapsed time
Resources           CPU % and memory %
Progress            FPS and processing speed
Policy              active ffmpeg-policy decision
```

If the policy line does not expose the source codec, WebAdmin can recover it from the corresponding FFmpeg stream metadata in that session's log. Process telemetry is read-only and does not change the transcoding decision.

This feature does **not** yet claim automatic client-capability detection. Unknown client playback capability continues to use the validated safe transcoding policy: compatible H.264 can remain Direct Stream while incompatible HEVC can be converted to H.264 using the selected hardware profile such as VAAPI.



### 2.0.8 runtime stability and verified telemetry

Version 2.0.8 hardens the 2.0.7 observability and runtime lifecycle without changing the integrated upstream core version.

Key improvements include:

- configuration save/read-back verification and restart validation;
- explicit Requested, Effective and Actual transcoding state;
- FFmpeg PID, CPU, memory, elapsed-time and per-session progress telemetry;
- reliable parsing and preservation of the active `ffmpeg-policy` decision;
- automatic VAAPI profile verification on a fresh WebAdmin process;
- verified `vaapi-full-h264` hardware decode/encode execution when supported;
- Stremio health validation across VPN enable/disable transitions;
- hardened DIRECT-mode DNS forwarding through Pi-hole and the gateway resolver;
- safer trusted-certificate refresh with validation before replacement.

The integrated server/core remains **1.6.15**. Platform, WebAdmin and VPN gateway are released as **2.0.8**.


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

Upgrade a normal Git-based installation from an earlier 2.x release to the current release:

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

If an upgrade must be rolled back, keep the persistent volumes and return the repository to the previous release tag, for example `v2.0.5`:

```bash
cd ~/stremio-libtorrent-server-webadmin
git fetch --tags origin
git checkout v2.0.5
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
ghcr.io/emmanique/stremio-libtorrent-server-webadmin:2.0.7
ghcr.io/emmanique/stremio-libtorrent-server-webadmin-webadmin:2.0.7
ghcr.io/emmanique/stremio-libtorrent-server-webadmin-vpn:2.0.7
```

Stable moving aliases:

```text
:2
:latest
```

These aliases are updated only by the validated 2.x release workflow.

## Docker Hub

```text
edmanique/stremio-libtorrent-server-webadmin:2.0.7
edmanique/stremio-libtorrent-server-webadmin:webadmin-2.0.7
edmanique/stremio-libtorrent-server-webadmin:vpn-2.0.7
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

Triggered manually with the target release version (for example `2.0.7`). The workflow validates the release contract and creates the corresponding `v2.x.y` tag/release.

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

Current stable release:

[docs/releases/v2.0.7.md](docs/releases/v2.0.7.md)

Versioning:

[VERSIONING.md](VERSIONING.md)

Branch strategy:

[docs/BRANCHING-2X.md](docs/BRANCHING-2X.md)

---

## License

MIT. See [LICENSE](LICENSE).
