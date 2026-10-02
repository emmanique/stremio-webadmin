# 🎬 Stremio Libtorrent Server + WebAdmin

[![Latest release](https://img.shields.io/github/v/release/emmanique/stremio-libtorrent-server-webadmin?display_name=tag&sort=semver)](https://github.com/emmanique/stremio-libtorrent-server-webadmin/releases/latest)
[![Fork integration guard](https://github.com/emmanique/stremio-libtorrent-server-webadmin/actions/workflows/fork-guard.yml/badge.svg?branch=main)](https://github.com/emmanique/stremio-libtorrent-server-webadmin/actions/workflows/fork-guard.yml)
[![Library addon guard](https://github.com/emmanique/stremio-libtorrent-server-webadmin/actions/workflows/library-addon-guard.yml/badge.svg?branch=main)](https://github.com/emmanique/stremio-libtorrent-server-webadmin/actions/workflows/library-addon-guard.yml)
[![VPN integration guard](https://github.com/emmanique/stremio-libtorrent-server-webadmin/actions/workflows/vpn-integration-guard.yml/badge.svg?branch=main)](https://github.com/emmanique/stremio-libtorrent-server-webadmin/actions/workflows/vpn-integration-guard.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-3DA639.svg)](LICENSE)

Self-hosted **Stremio streaming platform** built around an open `libtorrent` server and extended with WebAdmin, Library/Cache UI, Stremio Library Addon, Pi-hole, runtime-verified hardware transcoding, safe package updates and optional **CyberGhost OpenVPN** routing through Gluetun.

The normal installation uses published GHCR packages by default. The same validated Server, WebAdmin and VPN images are also mirrored to Docker Hub under `edmanique/stremio-libtorrent-server-webadmin`. Local application builds are not required for normal installation or updates.

> This repository does not bundle movies, series, torrent indexes or third-party content addons.

---

## Current release components

```text
Core            1.6.9
Server/Fork     1.6.9-server.18
WebAdmin        1.4.1
VPN Gateway     1.6.9-server.18
```

Authoritative version files:

```text
SERVER_VERSION
FORK_VERSION
webadmin/WEBADMIN_VERSION
pyproject.toml
```

See `VERSIONING.md` for release rules.

---

## What this fork adds

| Area | Added in this fork |
| --- | --- |
| Deployment | Server + WebAdmin + Pi-hole stack using published GHCR images, with validated Server/WebAdmin/VPN mirrors on Docker Hub. |
| WebAdmin | Browser UI on `8090` for status, configuration, cache, logs, updates, addons, transcoding, VPN and Gluetun management. |
| Library | Cache/library UI, add-by-magnet, pin/keep/delete, progress, series/episode navigation and disk awareness. |
| Library Addon | Exposes cached titles to Stremio as `My Library` with local streams and metadata learning. |
| Updates | Transactional Server update with health validation/rollback and independent WebAdmin lifecycle. |
| Pi-hole | Internal DNS, optional LAN DNS publication and a locked optimized Pi-hole v6 baseline. |
| Transcoding | Copy-first policy plus explicit runtime-verified VAAPI, NVIDIA/NVENC and CPU execution profiles. |
| VPN | Multi-profile CyberGhost OpenVPN manager with import, lifecycle, startup profile, kill switch and protection test. |
| Gluetun | Dedicated WebAdmin page for gateway status, VPN/DNS state, resources, routing, security checks, actions and logs. |
| Release safety | Permanent `future` branch, deterministic validation, guards and automated package/release publication. |

---

# 🖥️ WebAdmin screenshots

The screenshots below come from a real running WebAdmin installation. Network addresses and runtime values are examples; the exact layout may vary slightly between releases and enabled profiles.

## Connection, health and service status

![WebAdmin connection and health status](docs/screenshots/webadmin-connect-status.jpg)

The dashboard exposes the LAN address, Web Player and TV/application endpoints, QR connection data, Stremio/streaming-server health, uptime, CPU and memory usage, HTTPS certificate status, and seeding/stream controls without requiring terminal access.

## Active streams and live transfer state

![WebAdmin active streams](docs/screenshots/webadmin-active-streams.jpg)

Active jobs expose playback/seeding state, progress, download/upload throughput and peer information. Current WebAdmin releases also provide dedicated **Dashboard**, **Server**, **Transcoding**, **VPN**, **Gluetun**, **Logs** and **All Configuration** views.

---

# Architecture

## Direct mode

```text
Stremio clients
      │
      ▼
stremio-libtorrent-server  :8080 / :11470 / :12470
      │
      ├──────── WebAdmin :8090
      └──────── Pi-hole  :8053 / internal DNS
```

## VPN mode

```text
Stremio
   ↓
Pi-hole :53
   ↓
Gluetun DNS Bridge :1053
   ↓
Gluetun Secure Resolver 127.0.0.1:53
   ↓
CyberGhost VPN tunnel
   ↓
Internet
```

Only Stremio shares Gluetun's network namespace. WebAdmin and Pi-hole remain directly reachable from the LAN. If the VPN fails or is disconnected, Stremio remains fail-closed rather than falling back to the host WAN.

The `:1053` component is a private DNS bridge, not an additional recursive resolver. It exposes Gluetun's loopback resolver to Pi-hole without making Gluetun's own healthcheck depend on its Docker bridge address.

---

## Published images

### GitHub Container Registry (default)

```text
ghcr.io/emmanique/stremio-libtorrent-server-webadmin:latest
ghcr.io/emmanique/stremio-libtorrent-server-webadmin-webadmin:latest
ghcr.io/emmanique/stremio-libtorrent-server-webadmin-vpn:latest
pihole/pihole:latest
```

Versioned GHCR images for this release:

```text
ghcr.io/emmanique/stremio-libtorrent-server-webadmin:1.6.9-server.18
ghcr.io/emmanique/stremio-libtorrent-server-webadmin-webadmin:1.4.1
ghcr.io/emmanique/stremio-libtorrent-server-webadmin-vpn:1.6.9-server.18
```

### Docker Hub mirror

The validated release images are mirrored to a single Docker Hub repository using separate tags for Server, WebAdmin and VPN:

```text
edmanique/stremio-libtorrent-server-webadmin:latest
edmanique/stremio-libtorrent-server-webadmin:1.6.9-server.18

edmanique/stremio-libtorrent-server-webadmin:webadmin-latest
edmanique/stremio-libtorrent-server-webadmin:webadmin-1.4.1

edmanique/stremio-libtorrent-server-webadmin:vpn-latest
edmanique/stremio-libtorrent-server-webadmin:vpn-1.6.9-server.18
```

Pull from Docker Hub:

```bash
docker pull edmanique/stremio-libtorrent-server-webadmin:latest
docker pull edmanique/stremio-libtorrent-server-webadmin:webadmin-latest
docker pull edmanique/stremio-libtorrent-server-webadmin:vpn-latest
```

For reproducible deployments, prefer the immutable/versioned tags instead of `latest`.

The release workflow builds and smoke-tests the images once, publishes them to GHCR, and then mirrors the same validated artifacts to Docker Hub. This prevents the two registries from containing independently built binaries for the same release.

---

# 🚀 Installation

## Git clone — recommended

```bash
git clone https://github.com/emmanique/stremio-libtorrent-server-webadmin.git && \
cd stremio-libtorrent-server-webadmin && \
sh start.sh
```

Force a specific LAN address when needed:

```bash
IPADDRESS=192.168.1.244 sh start.sh
```

Start in managed VPN mode:

```bash
sh start-vpn.sh
```

The VPN gateway remains fail-closed until a usable VPN profile is selected.

## Package-only direct installation

```bash
mkdir -p ~/stremio-libtorrent-server-webadmin && \
cd ~/stremio-libtorrent-server-webadmin && \
curl -fsSL https://raw.githubusercontent.com/emmanique/stremio-libtorrent-server-webadmin/main/compose.yaml -o compose.yaml && \
docker compose pull && \
docker compose up -d --remove-orphans
```

For VPN profile management, Gluetun management, launch helpers and validation-controlled defaults, use the Git-clone layout.

## Access points

For a host at `192.168.1.244`:

| Service | Address |
| --- | --- |
| Web Player | `http://192.168.1.244:8080` |
| WebAdmin | `http://192.168.1.244:8090` |
| Streaming API | `http://192.168.1.244:11470` |
| Trusted HTTPS / Library | `https://<trusted-stremio-host>:12470/` |
| Pi-hole Admin | `http://192.168.1.244:8053/admin/` |
| BitTorrent direct mode | `6881/tcp` + `6881/udp` |

---

# 🔄 Updating

Persistent named volumes are retained by normal update procedures. **Never use `docker compose down -v` for routine updates.**

Direct mode:

```bash
cd ~/stremio-libtorrent-server-webadmin
git fetch --prune origin
git checkout main
git pull --ff-only origin main
sh start.sh
```

VPN mode:

```bash
cd ~/stremio-libtorrent-server-webadmin
git fetch --prune origin
git checkout main
git pull --ff-only origin main
sh start-vpn.sh
```

Package-only direct mode:

```bash
cd /path/to/your/stremio-directory
curl -fsSL https://raw.githubusercontent.com/emmanique/stremio-libtorrent-server-webadmin/main/compose.yaml -o compose.yaml
docker compose pull
docker compose up -d --remove-orphans
```

The Server updater in WebAdmin pulls the immutable GHCR tag advertised by `FORK_VERSION`, validates its OCI version label, activates only the Stremio runtime container, runs health validation and retains the previous image for rollback. WebAdmin and Pi-hole are not recreated by a Server-only update.

---

# 🌐 CyberGhost VPN manager

**WebAdmin → VPN** manages CyberGhost connection profiles. Each imported ZIP is expected to contain:

```text
openvpn.ovpn
ca.crt
client.crt
client.key
```

Supported lifecycle:

```text
Create
Edit
Activate
Disconnect
Reconnect
Delete
Enable at startup
Disable at startup
Test protection
```

Passwords, private keys and certificates are stored in the private persistent `vpn-data` volume and are not returned to the browser after saving.

The imported OpenVPN configuration is sanitized before runtime use. Unsafe script/plugin/management directives are excluded. Broad LAN ranges overlapping VPN tunnel address space are also avoided.

See `VPN.md` for full details.

---

# 🧭 Gluetun gateway management

WebAdmin `1.4.1` includes a dedicated **WebAdmin → Gluetun** page, separate from the CyberGhost profile manager.

```text
Dashboard | Server | Transcoding | VPN | Gluetun | Logs
```

The page exposes non-secret operational information such as container state, Docker health, VPN state/public IP, active profile, uptime, CPU, memory, RX/TX traffic, DNS state, network addresses and updater state.

Available actions include:

```text
Start gateway
Stop gateway
Restart gateway
Validate path
Open VPN connections
```

The validation view checks the Gluetun control API, VPN tunnel, DNS service, private DNS bridge, Pi-hole upstream, Stremio routing through Gluetun and kill-switch state. Logs support level filtering, free-text search, selectable line counts and auto-refresh. Sensitive VPN values are redacted server-side.

---

# 🛡️ Pi-hole locked optimized baseline

Pi-hole is part of the default stack. Its Web UI is normally on port `8053`; DNS is available internally without occupying host port `53` unless `compose.dns.yaml` is used.

The project defines an **authoritative locked Pi-hole v6 baseline** through Docker `FTLCONF_*` environment variables. Pi-hole treats those settings as read-only while the container is running, preventing accidental changes from the Pi-hole Web UI or local `pihole.toml` from bypassing the platform policy.

Locked defaults:

```text
DNS forward concurrency      300
DNS cache entries            10000
Cache optimizer              3600 s
Blocked upstream TTL         86400 s
Domain-needed                enabled
Bogus private filtering      enabled
DNSSEC                       disabled
Query logging                enabled
Rate limit                   1000 queries / 60 s
Blocking                     enabled
Blocking mode                NULL
Query database retention     30 days
Database write interval      60 s
SQLite WAL                   enabled
```

The settings are deliberately conservative: enough cache and forwarding concurrency for streaming workloads without unnecessarily increasing RAM usage or database churn.

### Direct mode upstream

Direct mode uses the configured external upstream DNS, defaulting to:

```text
1.1.1.1
1.0.0.1
```

### VPN mode upstream — locked

In VPN mode the Pi-hole upstream is locked to:

```text
172.30.0.10#1053
```

This ensures the external DNS path remains:

```text
Stremio
  ↓
Pi-hole
  ↓
Gluetun DNS Bridge
  ↓
Gluetun Secure Resolver
  ↓
VPN tunnel
```

Do not replace the VPN-mode upstream with a public resolver such as `8.8.8.8` or `1.1.1.1`, because Pi-hole itself does not share Gluetun's network namespace and that could create a DNS path outside the VPN.

To expose Pi-hole DNS to the LAN:

```bash
docker compose -f compose.yaml -f compose.dns.yaml up -d
```

Ensure TCP/UDP port `53` is free on the selected host address first.

---

# 📚 Library / Cache and Stremio Addon

The Library UI is enabled by default with `STREMIOSRV_LIBRARY_UI=true`. It exposes cached/downloading content, progress, files, disk capacity, pin/keep state and controlled deletion.

The built-in Stremio Library Addon exposes cached titles as `My Library` and provides local streams. Its generated addon URL contains a per-install secret token and must not be published in screenshots, logs or public issues.

---

# 🎞️ Streaming and transcoding

The transcoding design is deliberately **copy first**. The Stremio core remains authoritative for the Direct Stream versus transcode decision. Selecting a hardware profile does **not** force re-encoding of a compatible stream: if the core requests `-c:v copy`, the wrapper preserves that decision. This avoids needless quality loss, latency and GPU/CPU load.

When the core actually requests video transcoding, WebAdmin can replace the execution pipeline with one explicit runtime-verified profile:

```text
Preserve Stremio decision
H.264 VAAPI — GPU encode only
HEVC VAAPI — GPU encode only
H.264 VAAPI — Full GPU
HEVC VAAPI — Full GPU
H.264 NVIDIA NVENC
HEVC NVIDIA NVENC
H.264 CPU (libx264)
HEVC CPU (libx265)
```

Profiles are exposed as available only after a real FFmpeg runtime self-test. A compiled encoder name by itself is not treated as proof that the GPU/device path is usable. WebAdmin also reports the effective profile decision from `[ffmpeg-policy]` telemetry.

For VAAPI Full GPU, decoded frames remain as VAAPI hardware surfaces through scaling/pixel-format normalization and encoding. The pipeline uses `scale_vaapi(...,format=nv12)` rather than downloading frames to software and uploading them again.

VAAPI device overlay:

```bash
docker compose -f compose.yaml -f compose.vaapi.yaml up -d
```

NVIDIA/NVENC runtime overlay:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml up -d
```

The VPN Compose file can use the same hardware overlays.

To validate the complete platform and the selected transcoding profile from the host:

```bash
python3 tools/platform_performance_test.py
```

See `docs/PERFORMANCE.md` for the measured indicators, optional synthetic encoding test and JSON output used for before/after comparisons.

---

# ⚙️ Important environment variables

| Variable | Purpose |
| --- | --- |
| `IPADDRESS` | Host LAN IPv4; normally detected automatically. |
| `STREMIO_IMAGE` | Server GHCR image override/pin. |
| `WEBADMIN_IMAGE` | WebAdmin GHCR image override/pin. |
| `VPN_IMAGE` | Gluetun gateway image override/pin. |
| `STREMIO_DATA_DIR` | Cache/state Docker volume. |
| `STREMIOSRV_BT_LISTEN_PORT` | BitTorrent listen port in direct mode. |
| `STREMIOSRV_LIBRARY_UI` | Enable Library UI/addon integration. |
| `VPN_LAN_CIDRS` | LAN ranges allowed outside the VPN tunnel. |
| `PIHOLE_WEB_PORT` | Pi-hole Web UI port. |
| `PIHOLE_DNS_PORT` | Optional LAN DNS publication port. |
| `VAAPI_DEVICE` | VAAPI render device used by the FFmpeg execution profile; default `/dev/dri/renderD128`. |
| `TRANSCODING_*` | WebAdmin/FFmpeg execution policy and transcoding settings. |

The locked Pi-hole tuning values are intentionally defined in Compose instead of exposed as routine `.env` tuning options. Change them only as a controlled repository change followed by validation.

Do not put passwords, tokens, VPN credentials, private keys or certificates in tracked `.env` files.

---

# 🩺 Health and troubleshooting

Direct stack configuration:

```bash
sh start.sh config
```

Container state:

```bash
sh start.sh ps
```

Server health:

```bash
curl -fsS http://SERVER_IP:11470/health
```

VPN state/logs:

```bash
VPN_CONTROL_API_KEY="$(cat .vpn-control-key)" docker compose -f compose.vpn.yaml ps
docker logs --tail=200 stremio-gluetun
```

For normal VPN diagnostics use **WebAdmin → Gluetun** first; it correlates gateway status, routing, DNS/Pi-hole path and logs.

For transcoding diagnostics, use **WebAdmin → Transcoding**, refresh the runtime profile self-tests, start a stream that genuinely requires transcoding, and confirm that the effective `[ffmpeg-policy]` decision matches the selected execution profile.

---

# 🧪 Development and release model

All changes are made on the permanent `future` branch first:

```text
future
  │
  ├─ Future full validation
  └─ VPN integration guard
  │
  ▼
main
  │
  ├─ Fork integration guard
  ├─ Library addon guard
  └─ VPN integration guard
  │
  ▼
version tag
  │
  ├─ build/test Server image
  ├─ build/test WebAdmin image
  ├─ build/test VPN gateway image
  ├─ publish versioned + latest GHCR packages
  ├─ mirror validated Server/WebAdmin/VPN tags to Docker Hub
  └─ create/update GitHub Release
```

`main` is promoted only by fast-forward after `future` validation succeeds.

---

# 📁 Main repository components

```text
compose.yaml                     Direct Server + WebAdmin + Pi-hole stack
compose.vpn.yaml                 CyberGhost/Gluetun VPN stack
compose.dns.yaml                 Optional Pi-hole LAN DNS publication
compose.vaapi.yaml               VAAPI device overlay
compose.gpu.yaml                 NVIDIA/NVENC runtime overlay
start.sh                         Direct launcher + image refresh
start-vpn.sh                     VPN launcher + image refresh
docker/ffmpeg_wrapper.py         Runtime execution-profile policy for FFmpeg
docker/publish.sh                Manual validated Docker Hub publisher
docker/push-readme.sh            Docker Hub overview synchronization helper
vpn/                             Gluetun wrapper/profile selection
webadmin/transcoding_profiles.py Runtime profile tests and profile selection API
webadmin/transcoding_verified_status.py Verified capability/policy telemetry
webadmin/vpn_admin.py            VPN status/control/protection test
webadmin/vpn_profiles.py         CyberGhost profile CRUD/import/startup
webadmin/gluetun_admin.py        Gluetun status/actions/config/validation/log API
webadmin/static/gluetun-admin.js Dedicated Gluetun WebAdmin page
src/stremiosrv/transcode/        Native FFmpeg/HLS command construction and job lifecycle
src/stremiosrv/library/          Library UI/addon/metadata
tools/platform_performance_test.py Host-side end-to-end performance/readiness validation
docs/screenshots/                WebAdmin screenshots used in this README
.github/workflows/               Validation/release/package workflows
VPN.md                           VPN setup/security documentation
VERSIONING.md                    Component version policy
docs/PERFORMANCE.md              Performance/transcoding validation guide
docs/releases/                   Release notes
```

---

# 🔐 Security considerations

- Keep WebAdmin `8090` on a trusted LAN/VPN because it can control Docker through the mounted socket.
- Treat the Stremio Library Addon URL as a secret.
- VPN credentials and private keys belong only in the private `vpn-data` volume.
- Gluetun management exposes only non-secret configuration and runtime state.
- Keep the VPN kill-switch and locked Pi-hole VPN upstream enabled.
- Do not expose Docker socket access or WebAdmin directly to the public Internet.

---

## License

MIT. See `LICENSE`.