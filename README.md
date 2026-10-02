# 🎬 Stremio Libtorrent Server + WebAdmin

[![Latest release](https://img.shields.io/github/v/release/emmanique/stremio-libtorrent-server-webadmin?display_name=tag&sort=semver)](https://github.com/emmanique/stremio-libtorrent-server-webadmin/releases/latest)
[![Fork integration guard](https://github.com/emmanique/stremio-libtorrent-server-webadmin/actions/workflows/fork-guard.yml/badge.svg?branch=main)](https://github.com/emmanique/stremio-libtorrent-server-webadmin/actions/workflows/fork-guard.yml)
[![Library addon guard](https://github.com/emmanique/stremio-libtorrent-server-webadmin/actions/workflows/library-addon-guard.yml/badge.svg?branch=main)](https://github.com/emmanique/stremio-libtorrent-server-webadmin/actions/workflows/library-addon-guard.yml)
[![VPN integration guard](https://github.com/emmanique/stremio-libtorrent-server-webadmin/actions/workflows/vpn-integration-guard.yml/badge.svg?branch=main)](https://github.com/emmanique/stremio-libtorrent-server-webadmin/actions/workflows/vpn-integration-guard.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-3DA639.svg)](LICENSE)

A self-hosted **Stremio streaming platform** built around an open `libtorrent` server and extended with WebAdmin, Library/Cache UI, a Stremio Library Addon, Pi-hole, hardware-aware transcoding, safe package updates and optional **CyberGhost OpenVPN** routing through Gluetun.

The normal installation is **package-only**: Docker Compose pulls published images from GHCR. Local application builds are not required for normal use or updates.

> This repository does not bundle movies, series, torrent indexes or third-party content addons. It provides streaming, cache, administration and integration infrastructure.

---

## Current release components

```text
Core            1.6.9
Server/Fork     1.6.9-server.16
WebAdmin        1.4.0
VPN Gateway     1.6.9-server.16
```

Authoritative version files:

```text
SERVER_VERSION
FORK_VERSION
webadmin/WEBADMIN_VERSION
pyproject.toml
```

See `VERSIONING.md` for the release rules.

---

## What this fork adds

| Area | Added in this fork |
| --- | --- |
| Deployment | Full Server + WebAdmin + Pi-hole stack with published GHCR images. |
| WebAdmin | Browser UI on `8090` for status, configuration, cache, logs, updates, addons, transcoding, VPN and Gluetun gateway management. |
| Library | Poster-based cache/library UI, add-by-magnet, pin/keep/delete, progress, series/episode navigation and disk awareness. |
| Library Addon | Exposes cached titles to Stremio as `My Library` with local streams and metadata learning. |
| Metadata | Conservative release recognition, Cinemeta lookup and artwork fallback. |
| Updates | Transactional Server update with health validation/rollback plus independent WebAdmin lifecycle. |
| Pi-hole | Internal DNS by default and optional LAN DNS publication. |
| Transcoding | Copy-first/direct-play policy, VAAPI, NVIDIA/NVENC and CPU fallback. |
| VPN | Multi-profile CyberGhost OpenVPN manager: ZIP import, create/edit/activate/disconnect/reconnect/delete, startup profile, kill switch, protection test and private credential storage. |
| Gluetun management | Dedicated WebAdmin page for gateway status, Docker health, VPN/DNS state, routing, kill switch, Pi-hole path validation, resources, actions and filtered logs. |
| Release safety | Permanent `future` branch, deterministic validation, fork/library/VPN guards and automated package/release publication. |

---

## Architecture

### Direct mode

```text
Stremio clients
      │
      ▼
stremio-libtorrent-server  :8080 / :11470 / :12470
      │
      ├──────── WebAdmin :8090
      └──────── Pi-hole  :8053 / internal DNS
```

### VPN mode

```text
Internet
   │
CyberGhost OpenVPN
   │
Gluetun gateway + kill switch
   │
   └── stremio-libtorrent-server

WebAdmin + Pi-hole remain directly reachable on the LAN.
```

Only Stremio shares Gluetun's network namespace. If the VPN tunnel fails or is disconnected, Stremio remains blocked rather than falling back to the host WAN.

The DNS path in VPN mode is designed as:

```text
Stremio
   ↓
Pi-hole
   ↓
private Gluetun DNS proxy
   ↓
Gluetun internal DNS
   ↓
VPN tunnel
```

---

## Published images

```text
ghcr.io/emmanique/stremio-libtorrent-server-webadmin:latest
ghcr.io/emmanique/stremio-libtorrent-server-webadmin-webadmin:latest
ghcr.io/emmanique/stremio-libtorrent-server-webadmin-vpn:latest
pihole/pihole:latest
```

Versioned images for this release:

```text
ghcr.io/emmanique/stremio-libtorrent-server-webadmin:1.6.9-server.16
ghcr.io/emmanique/stremio-libtorrent-server-webadmin-webadmin:1.4.0
ghcr.io/emmanique/stremio-libtorrent-server-webadmin-vpn:1.6.9-server.16
```

---

# 🚀 Installation

## Option A — Git clone (recommended)

Requirements: Linux, Docker Engine, Docker Compose v2 and LAN access to the host.

```bash
git clone https://github.com/emmanique/stremio-libtorrent-server-webadmin.git && \
cd stremio-libtorrent-server-webadmin && \
sh start.sh
```

`start.sh` detects the host LAN IPv4, pulls the current published images and starts the direct stack.

To force one address:

```bash
IPADDRESS=192.168.1.244 sh start.sh
```

To start directly in VPN mode after the repository has been cloned:

```bash
sh start-vpn.sh
```

The VPN gateway stays fail-closed until a usable VPN profile is selected. WebAdmin and Pi-hole remain reachable on the LAN.

## Option B — RUN / package-only installation without Git clone

This mode is for installations created by downloading/running the published Compose definition instead of keeping a local Git checkout.

```bash
mkdir -p ~/stremio-libtorrent-server-webadmin && \
cd ~/stremio-libtorrent-server-webadmin && \
curl -fsSL https://raw.githubusercontent.com/emmanique/stremio-libtorrent-server-webadmin/main/compose.yaml -o compose.yaml && \
docker compose pull && \
docker compose up -d --remove-orphans
```

This starts the published Server + WebAdmin + Pi-hole packages without compiling the project locally.

For the **full managed feature set**, especially VPN profile management, Gluetun gateway management, launch helpers, hardware overlays and validation-controlled defaults, the Git-clone installation is preferred because those features use more files than `compose.yaml` alone.

> The complete platform is a multi-container stack. A single standalone `docker run` command is not considered a full installation because it would not provide the complete Server + WebAdmin + Pi-hole + optional VPN topology.

## Access points

For a host at `192.168.1.244`:

| Service | Address |
| --- | --- |
| Web Player | `http://192.168.1.244:8080` |
| WebAdmin | `http://192.168.1.244:8090` |
| Streaming API | `http://192.168.1.244:11470` |
| Trusted HTTPS / Library | `https://<trusted-stremio-host>:12470/` |
| Pi-hole Admin | `http://192.168.1.244:8053/admin/` |
| BitTorrent in direct mode | `6881/tcp` + `6881/udp` |

When ports are bound to a specific `IPADDRESS`, test them through that LAN address rather than `127.0.0.1` on the host.

---

# 🔄 Updating

Persistent named volumes are retained by all normal update procedures below. **Never use `docker compose down -v` for a routine update** because `-v` removes persistent cache/configuration volumes.

## A. Update an installation made with `git clone`

Direct mode:

```bash
git status
git fetch --prune origin
git checkout main
git pull --ff-only origin main
sh start.sh
```

VPN mode:

```bash
git status
git fetch --prune origin
git checkout main
git pull --ff-only origin main
sh start-vpn.sh
```

`git status` should be clean before updating. If you have deliberate local tracked-file changes, save or commit them first; do not discard them blindly.

The launchers pull the current GHCR packages and recreate only what is required while keeping named volumes and saved WebAdmin/VPN state.

### Git clone — single-command update

Direct mode:

```bash
cd /path/to/stremio-libtorrent-server-webadmin && git fetch --prune origin && git checkout main && git pull --ff-only origin main && sh start.sh
```

VPN mode:

```bash
cd /path/to/stremio-libtorrent-server-webadmin && git fetch --prune origin && git checkout main && git pull --ff-only origin main && sh start-vpn.sh
```

## B. Update an installation made by RUN / package-only Compose

```bash
cd /path/to/your/stremio-directory
curl -fsSL https://raw.githubusercontent.com/emmanique/stremio-libtorrent-server-webadmin/main/compose.yaml -o compose.yaml
docker compose pull
docker compose up -d --remove-orphans
```

Single command:

```bash
cd /path/to/your/stremio-directory && curl -fsSL https://raw.githubusercontent.com/emmanique/stremio-libtorrent-server-webadmin/main/compose.yaml -o compose.yaml && docker compose pull && docker compose up -d --remove-orphans
```

This method updates the package-only/direct stack while preserving named volumes.

If a package-only installation needs the VPN connection manager or the dedicated Gluetun administration page, convert it to the managed Git-clone layout rather than trying to maintain only one Compose file:

```bash
cd ~
git clone https://github.com/emmanique/stremio-libtorrent-server-webadmin.git
cd stremio-libtorrent-server-webadmin
sh start-vpn.sh
```

Before converting an existing deployment, keep the same Docker named volumes/environment values so cached data and persisted state remain associated with the same services. Do not remove volumes during the migration.

## C. Refresh only the published images

```bash
docker compose pull
docker compose up -d --remove-orphans
```

## D. WebAdmin only

```bash
docker compose pull webadmin
docker compose up -d --no-deps webadmin
```

## E. Server update from WebAdmin

The Server updater pulls an immutable GHCR image, validates the expected version, preserves the previous image as a rollback candidate, recreates only the Server, waits for `/health`, and restores the previous container automatically if activation fails.

---

# 🌐 CyberGhost VPN connection manager

The **WebAdmin → VPN** page is designed around the same manual/router OpenVPN material generated by CyberGhost and supports **multiple independent VPN connections**.

For each new connection, download the CyberGhost configuration ZIP containing:

```text
openvpn.ovpn
ca.crt
client.crt
client.key
```

In **WebAdmin → VPN → New connection**, provide the connection name and, where applicable:

- protocol: OpenVPN;
- country;
- server group/hostname;
- generated OpenVPN username;
- generated OpenVPN password;
- pre-shared value;
- extra-feature selections;
- the CyberGhost ZIP.

## VPN profile lifecycle

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

Only one profile can be active at a time and only one profile can be selected as the startup profile.

Example:

```text
Portugal       ACTIVE
Netherlands    STARTUP
Germany
Spain
```

Activating `Germany` switches the current tunnel to Germany. The configured startup profile can remain `Netherlands` for the next gateway restart.

## Private profile storage

Each profile keeps its own private material inside persistent `vpn-data`, conceptually:

```text
vpn-data/
└── profiles/
    ├── portugal/
    │   ├── profile.json
    │   ├── openvpn.runtime.ovpn
    │   ├── ca.crt
    │   ├── client.crt
    │   ├── client.key
    │   ├── username
    │   └── password
    └── another-profile/
        └── ...
```

Passwords, certificates and private keys are not returned to the browser after they are saved.

## ZIP validation and runtime sanitation

The importer:

1. checks archive paths and rejects unsafe members;
2. requires `openvpn.ovpn`, `ca.crt`, `client.crt` and `client.key`;
3. validates certificate/key material;
4. detects the remote endpoint and UDP/TCP settings;
5. creates a sanitized runtime OpenVPN configuration;
6. stores the connection material in the private persistent VPN volume;
7. excludes executable script/plugin/management directives from the generated runtime configuration.

The CyberGhost bundle controls the actual remote endpoint/protocol. The VPN gateway runs Gluetun with the custom OpenVPN profile selected by WebAdmin.

## Startup profile behaviour

```text
explicitly requested profile
        ↓
configured startup profile
        ↓
last active/usable profile
        ↓
no usable profile → Stremio Internet remains blocked
```

This is intentionally fail-closed: there is no silent fallback from VPN mode to the normal host WAN.

## Starting and leaving VPN mode

Start VPN mode:

```bash
sh start-vpn.sh
```

Return to direct mode:

```bash
sh start.sh
```

WebAdmin provides VPN public IP, traffic counters, kill-switch/routing state, protection test and redacted logs.

CyberGhost does not provide VPN-side port forwarding. VPN mode therefore does not publish Stremio's BitTorrent listen port on the host.

Full details: `VPN.md`.

---

# 🧭 Gluetun gateway management

WebAdmin `1.4.0` adds a dedicated **WebAdmin → Gluetun** page. This page is separate from **VPN**: the VPN page manages CyberGhost connection profiles, while the Gluetun page manages and observes the gateway runtime itself.

The menu becomes conceptually:

```text
Dashboard | Server | Transcoding | VPN | Gluetun | Logs
```

## Gateway status

The Gluetun page displays:

- container presence and runtime state;
- Docker health status;
- VPN tunnel status;
- VPN public IP;
- active VPN profile;
- container uptime and restart count;
- CPU and memory usage;
- received/transmitted network bytes;
- Gluetun DNS state;
- Gluetun updater state;
- Docker network addresses.

## Gateway actions

From the page you can:

```text
Start gateway
Stop gateway
Restart gateway
Validate path
Open VPN connections
```

Stopping or restarting the gateway preserves the fail-closed model. Stremio must not fall back to the host WAN while Gluetun is unavailable.

## Configuration visibility

The page shows the effective non-secret Gluetun configuration, including:

- VPN provider mode;
- VPN type;
- firewall / kill switch state;
- firewall input ports;
- allowed LAN CIDRs outside the tunnel;
- DNS service state;
- DNS listen address;
- DNS upstream transport and resolvers;
- DNS cache state;
- private Pi-hole DNS proxy port;
- VPN auto-heal setting;
- timezone;
- TLS and ICMP healthcheck targets.

Security-critical settings remain protected. The page does **not** expose or return:

- OpenVPN username/password;
- client private keys;
- client certificates as editable secrets;
- Gluetun control API key.

The firewall/kill-switch and DNS loopback binding are intentionally not switchable off from this page.

## Network and security validation

The page correlates the Gluetun container, Stremio and Pi-hole and can validate:

```text
Gluetun container running
Docker health healthy
Gluetun control API reachable
VPN tunnel running
DNS service available
Private DNS proxy reachable
Pi-hole upstream points to Gluetun
Stremio shares the Gluetun network namespace
Kill switch remains active
```

This is intended to make VPN routing and DNS failures visible without requiring SSH access for every diagnostic step.

## Gluetun logs

The dedicated log viewer supports:

- 100 / 200 / 500 / 1000 lines;
- All / Error / Warn / Info / Debug filters;
- free-text search;
- manual refresh;
- optional auto-refresh;
- clearing only the browser viewer without deleting Docker logs.

Sensitive VPN values are redacted server-side before log output is returned to the browser.

Implementation components:

```text
webadmin/gluetun_admin.py
webadmin/static/gluetun-admin.js
```

---

# 📚 Library / Cache and Stremio Addon

The Library UI is enabled by default through `STREMIOSRV_LIBRARY_UI=true`. It can show downloaded/downloading content, posters, continue-watching state, actual pack files, cache capacity/free space, pin/keep state and controlled deletion.

The built-in Stremio Library Addon can expose cached titles as `My Library`, provide local streams and learn playback identity/metadata. Its generated addon URL contains a per-install secret token and should not be published in screenshots, logs or public issues.

---

# 🎞️ Streaming and transcoding

The server remains a real `libtorrent` client and maintains cache/seeding state. The fork adds a copy-first/direct-play FFmpeg policy with hardware acceleration options.

Default policy includes VAAPI with CPU fallback. For VAAPI:

```bash
docker compose -f compose.yaml -f compose.vaapi.yaml up -d
```

For NVIDIA/NVENC on a host with NVIDIA Container Toolkit:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml up -d
```

The VPN Compose file can use the same VAAPI/NVIDIA overlays.

---

# 🛡️ Pi-hole

Pi-hole is part of the default stack. Its Web UI is normally on port `8053`; DNS is available internally to the Docker stack without occupying host port `53`.

To expose Pi-hole DNS to the LAN:

```bash
docker compose -f compose.yaml -f compose.dns.yaml up -d
```

Ensure TCP/UDP port `53` is free on the selected host address first.

In VPN mode, Pi-hole remains reachable on the LAN while its configured private upstream path can be validated from the dedicated Gluetun page.

---

# ⚙️ Important environment variables

| Variable | Purpose |
| --- | --- |
| `IPADDRESS` | Host LAN IPv4; normally detected automatically. |
| `STREMIO_IMAGE` | Server GHCR image override/pin. |
| `WEBADMIN_IMAGE` | WebAdmin GHCR image override/pin. |
| `VPN_IMAGE` | CyberGhost/Gluetun gateway image override/pin. |
| `STREMIO_DATA_DIR` | Cache/state Docker volume. |
| `STREMIOSRV_BT_LISTEN_PORT` | BitTorrent listen port in direct mode. |
| `STREMIOSRV_LIBRARY_UI` | Enable Library UI/addon integration. |
| `STREMIOSRV_LIBRARY_ADDON_ALLOW` | Optional addon network/CIDR allowlist. |
| `STREMIO_UPDATE_HEALTH_TIMEOUT` | Server update health timeout. |
| `VPN_LAN_CIDRS` | LAN ranges allowed outside the VPN tunnel. |
| `PIHOLE_WEB_PORT` | Pi-hole Web UI port. |
| `PIHOLE_DNS_PORT` | Optional LAN DNS publication port. |
| `TRANSCODING_*` | Direct-play/FFmpeg/hardware policy. |

Do not put passwords, tokens, VPN credentials, private keys or certificates in tracked `.env` files.

---

# 🩺 Health and troubleshooting

Resolved direct Compose configuration:

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

For normal operational diagnostics, use **WebAdmin → Gluetun** before dropping to SSH. It provides status, routing checks, DNS/Pi-hole validation and filtered Gluetun logs in one place.

---

# 🧪 Development and release model

All development changes are made on the permanent `future` branch first.

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
  └─ create/update GitHub Release
```

`main` is promoted only by fast-forward after `future` validation succeeds. Fork-owned paths are protected from automatic upstream replacement.

---

# 📁 Main repository components

```text
compose.yaml                     Direct Server + WebAdmin + Pi-hole stack
compose.vpn.yaml                 CyberGhost/Gluetun full VPN stack
compose.dns.yaml                 Optional Pi-hole LAN DNS publication
compose.vaapi.yaml               VAAPI device overlay
compose.gpu.yaml                 NVIDIA/NVENC runtime overlay
start.sh                         Direct launcher + image refresh
start-vpn.sh                     VPN launcher + image refresh
vpn/                             Gluetun wrapper and active/startup profile selection
webadmin/vpn_admin.py            VPN status/control/protection test
webadmin/vpn_profiles.py         CyberGhost profile CRUD/import/startup management
webadmin/gluetun_admin.py        Gluetun status/actions/config/validation/log API
webadmin/static/gluetun-admin.js Dedicated Gluetun WebAdmin page
src/stremiosrv/library/          Library UI, addon, labels and metadata
.github/workflows/               Validation, release and package checks
VPN.md                           VPN setup/security/profile documentation
VERSIONING.md                    Component version policy
docs/releases/                   Release notes
```

---

# 🔐 Security considerations

- Keep WebAdmin `8090` on a trusted LAN/VPN because it can control Docker through the mounted socket.
- Treat the Stremio Library Addon URL as a secret.
- VPN credentials and private keys belong only in the private `vpn-data` volume.
- The Gluetun management page intentionally exposes only non-secret configuration and runtime state.
- Do not weaken the VPN LAN allowlist to public networks unless you understand the leak implications.
- Do not expose Docker socket access or WebAdmin directly to the public Internet.

---

## License

MIT. See `LICENSE`.
