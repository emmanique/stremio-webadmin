# Stremio Server WebAdmin 2.0.20

[![Fast CI](https://github.com/emmanique/stremio-libtorrent-server-webadmin/actions/workflows/ci-fast.yml/badge.svg?branch=main)](https://github.com/emmanique/stremio-libtorrent-server-webadmin/actions/workflows/ci-fast.yml)
[![Full regression](https://github.com/emmanique/stremio-libtorrent-server-webadmin/actions/workflows/regression.yml/badge.svg?branch=main)](https://github.com/emmanique/stremio-libtorrent-server-webadmin/actions/workflows/regression.yml)

Self-hosted Stremio streaming platform with Stremio/libtorrent server, WebAdmin, Pi-hole, optional Gluetun/OpenVPN routing and hardware transcoding support.

Current versions:

| Component | Version |
| --- | --- |
| Fork / Platform | 2.0.20 |
| WebAdmin | 2.0.20 |
| VPN Gateway | 2.0.20 |
| Upstream Server/Core | 1.6.15 |

## What changed in 2.0.20

- Clean installs no longer seed an active blank `LIBVA_DRIVER_NAME=` assignment.
- Existing empty `LIBVA_DRIVER_NAME=` entries are normalized safely; explicit non-empty overrides such as `iHD` remain supported.
- WebAdmin now receives and reports the detected `VAAPI_DEVICE`, so hosts using render nodes such as `/dev/dri/renderD129` no longer display the stale `renderD128` default.
- VPN provider telemetry is normalized from the active profile, avoiding stale `pia` or `custom` labels when CyberGhost is active.
- The integrated Stremio/libtorrent core remains 1.6.15.
- Physical validation covered configuration persistence/restart and a complete DIRECT -> VPN -> DIRECT routing cycle.

## Runtime architecture

~~~text
Host / LAN
  |
  +-- WebAdmin :8090
  +-- Pi-hole  :8053
  +-- Gluetun gateway/network namespace
        |
        +-- Stremio Server :8080 / :11470 / :12470 / :6881
        +-- DIRECT egress when VPN is disabled
        +-- VPN egress when enabled
~~~

The Gluetun container remains present as the stable network namespace. Disabling VPN stops the tunnel, not the container.

# New installation

## 1. Requirements

- Linux host with Docker Engine and Docker Compose plugin.
- curl or wget and tar/unzip.
- A writable installation directory such as /opt/stremio-webadmin.
- Ports 8080, 8090, 11470, 12470 and 6881 TCP/UDP available on the selected host IP.
- Port 8053 for Pi-hole Web. Host DNS port 53 is optional and only used with compose.dns.yaml.

Verify Docker first:

~~~bash
docker --version
docker compose version
~~~

## 2. Obtain the deployment package

For production, use the deployment ZIP or TAR.GZ attached to the desired GitHub Release. Do not clone the complete repository on a normal production host.

Example using a released TAR.GZ:

~~~bash
VERSION=2.0.20
INSTALL_DIR=/opt/stremio-webadmin

sudo mkdir -p "$INSTALL_DIR"
curl -fL \
  -o "/tmp/stremio-webadmin-${VERSION}-deployment.tar.gz" \
  "https://github.com/emmanique/stremio-libtorrent-server-webadmin/releases/download/v${VERSION}/stremio-webadmin-${VERSION}-deployment.tar.gz"

sudo tar -xzf "/tmp/stremio-webadmin-${VERSION}-deployment.tar.gz" \
  -C "$INSTALL_DIR" --strip-components=1

cd "$INSTALL_DIR"
~~~

For an unreleased release candidate, use the deployment artifact produced by the Full regression workflow. Do not treat an unreleased main commit as a published production package.

## 3. Create the local configuration

~~~bash
cp .env.example .env
~~~

The .env file is installation state and must never be committed or replaced by an upgrade.

Review these parameters before first start:

| Variable | Action on a new installation |
| --- | --- |
| TZ | Set the local IANA timezone, for example Europe/Lisbon or Africa/Luanda. |
| PIHOLE_PASSWORD | Set a unique Pi-hole administrator password. |
| IPADDRESS_SOURCE | Keep auto normally. Use manual only when the host has multiple interfaces or autodetection is not appropriate. |
| IPADDRESS | Leave empty with auto. Set the exact host IPv4 when IPADDRESS_SOURCE=manual. |
| VPN_LAN_CIDRS | Change when the LAN is not covered by 192.168.0.0/16; include only trusted LAN subnets plus the platform internal subnet. |
| STREMIO_DIRECT_DNS_UPSTREAM | Change only if another resolver is required in DIRECT mode. |
| STREMIO_IMAGE / WEBADMIN_IMAGE / VPN_IMAGE | latest is convenient; pin all three to the same release for reproducible production installs. |
| SERVER_URL | Optional. Set when an explicit trusted Stremio HTTPS endpoint is required. |
| STREMIOSRV_LIBRARY_OWNER | Optional. Use only when ownership restriction is intentionally required. |
| STREMIOSRV_LIBRARY_ADDON_ALLOW | Leave empty for the built-in private-network allowlist unless a deliberate custom allowlist is required. |
| GPU_BACKEND | Keep auto for normal installations. |
| VAAPI_DEVICE | Leave empty unless a specific local render node has been validated. |
| LIBVA_DRIVER_NAME | Omit it by default. Add a non-empty override such as iHD only when the host requires it. |

VPN credentials, certificates and private keys are not entered in .env. Configure/import them later in WebAdmin -> VPN.

## 4. Validate before starting

~~~bash
sh start.sh config
~~~

Do not continue if Compose reports an unresolved variable, invalid bind address, unavailable port or invalid topology.

## 5. Start

~~~bash
sh start.sh
~~~

With no arguments the launcher pulls the configured images and starts/reconciles the stack.

Typical access points, using the IP printed by start.sh:

| Service | URL / Port |
| --- | --- |
| Web Player | http://HOST-IP:8080 |
| WebAdmin | http://HOST-IP:8090 |
| Streaming API | http://HOST-IP:11470 |
| Trusted HTTPS / Library | https://HOST-IP:12470 |
| Pi-hole Web | http://HOST-IP:8053/admin/ |
| BitTorrent | 6881/tcp and 6881/udp |

## 6. First-install validation

~~~bash
sh start.sh ps
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
curl -fsS http://HOST-IP:11470/health
curl -fsS http://HOST-IP:8090/health
curl -fsS http://HOST-IP:8090/api/component-versions
~~~

Then verify in WebAdmin:

- configuration save and read-back;
- Server restart;
- Pi-hole state;
- VPN remains NOT CONFIGURED / DIRECT until explicitly configured;
- transcoding capability matrix;
- Library access if enabled.

# Configuration rules

## IP addressing

With IPADDRESS_SOURCE=auto, start.sh detects the IPv4 used by the default route and refreshes the local .env when the host address changes. On multi-homed hosts use manual mode instead of relying on an arbitrary interface choice.

## GPU / transcoding

The baseline is copy-first and CPU-safe. Compatible streams are not re-encoded merely because a GPU exists.

Recommended baseline:

~~~env
GPU_BACKEND=auto
VAAPI_DEVICE=
# LIBVA_DRIVER_NAME=iHD  # optional explicit override only
TRANSCODING_HWACCEL=cpu
TRANSCODING_VIDEO_CODEC=libx264
~~~

start.sh adds the VAAPI or NVIDIA overlay only when the local host can support it. Explicit GPU values should be treated as host-specific overrides.

## VPN

Configure VPN from WebAdmin -> VPN. A new installation does not require VPN credentials.

State model:

~~~text
NOT CONFIGURED -> DIRECT
CONFIGURED/OFF  -> DIRECT
CONFIGURED/ON   -> VPN
VPN failure     -> fail-closed while VPN is requested
~~~

## Pi-hole DNS

The base stack does not expose host DNS port 53. To expose Pi-hole DNS to the LAN, first ensure the selected host IP has port 53 available and then use compose.dns.yaml.

# Upgrade

Upgrades must preserve the local .env and named Docker volumes.

## 1. Backup before every upgrade

~~~bash
cd /opt/stremio-webadmin
sh scripts/backup-before-upgrade.sh
~~~

Use --with-cache only when the large cache volume must also be archived:

~~~bash
sh scripts/backup-before-upgrade.sh --with-cache
~~~

The normal backup set includes configuration/state volumes such as stremio-config, webadmin-data, vpn-data, gluetun-data, pihole-etc and pihole-dnsmasq plus deployment metadata.

Never use docker compose down -v for a routine upgrade or rollback.

## 2. Preserve local configuration

Do not delete or overwrite:

- .env
- named Docker volumes;
- imported VPN material stored in persistent volumes;
- persistent certificate/cache data unless intentionally rebuilding it.

## 3. Replace deployment files

Download the new deployment package and extract it over the existing installation directory. The package intentionally does not contain .env.

## 4. Reconcile new variables

After extracting the new version, check which variables exist in the new template but are absent from the local .env:

~~~bash
sh scripts/check-env-upgrade.sh
~~~

The script only reports missing/obsolete variable names; it does not rewrite the local .env. Review each new variable and add it manually only when its default/behaviour is understood.

For a raw comparison you can also use:

~~~bash
diff -u .env .env.example || true
~~~

## 5. Validate and upgrade

~~~bash
sh start.sh config
sh start.sh pull
sh start.sh up -d --force-recreate
~~~

## 6. Post-upgrade validation

~~~bash
sh start.sh ps
curl -fsS http://HOST-IP:11470/health
curl -fsS http://HOST-IP:8090/health
curl -fsS http://HOST-IP:8090/api/component-versions
~~~

Also validate configuration save/restart, VPN state, DNS path and transcoding capability after each release upgrade.

# Rollback

Keep the backup created before the upgrade. Roll back deployment files/images to the previous coordinated release while preserving the persistent volumes. Do not remove volumes as part of a normal rollback.

If image variables are pinned, restore all coordinated component tags to the same prior platform release and run:

~~~bash
sh start.sh config
sh start.sh pull
sh start.sh up -d --force-recreate
~~~

# Development and branch model

Normal users do not need Git. Contributors use the source repository.

Long-lived branches:

- main: production/releasable state;
- development: integration for the next release.

Temporary branches:

- feature/<short-name> from development;
- fix/<short-name> from development;
- release/<x.y.z> from development and merged to main after full regression;
- hotfix/<short-name> from main and merged back/synchronised to development.

Do not create a permanent branch for each version. Historical branches such as develop/2.x are legacy references only and are not CI targets.

See docs/BRANCHING.md and docs/WORKFLOWS.md.

# CI / release gates

Fast CI: syntax, repository contracts, Compose validation, documentation contract and deterministic tests.

Dependencies: dependency graph, audits, dependency-sensitive tests and image builds.

Full regression: complete regression suite, integration tests, Server/WebAdmin/VPN builds and smoke tests, deployment-package generation and clean-install simulation.

Prepare release: creates the temporary release/<version> branch from development.

Release: publishes only from validated main, creates immutable version tags/images and attaches the deployment ZIP/TAR plus SHA256SUMS.

Upstream sync: isolates upstream changes in upstream/integration and proposes them to development; it never promotes directly to main.

# Repository vs deployment package

The source repository contains src/, webadmin/, vpn/, tests/, tools/, Actions and engineering documentation.

The production deployment package intentionally contains only the supported runtime surface: Compose files, launchers, .env.example, backup/upgrade helpers and operational documentation.

# Security notes

- Keep WebAdmin on a trusted LAN/VPN; it has Docker management access.
- Do not expose port 8090 directly to the public Internet.
- Do not commit .env, VPN credentials, private keys, certificates or Library tokens.
- Keep the VPN kill switch/fail-closed behaviour enabled.
- Treat explicit allowlists and LAN CIDRs as security boundaries, not convenience defaults.

# Release information

Release notes: docs/releases/v2.0.20.md

License: MIT. See LICENSE.
