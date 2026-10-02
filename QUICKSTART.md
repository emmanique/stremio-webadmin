# Quick Start

This fork runs four coordinated services from one Docker Compose topology:

- `gluetun` — persistent network gateway; DIRECT when VPN is disabled and VPN gateway when enabled;

- `stremio-libtorrent-server` — published Stremio streaming runtime from GHCR by default, mirrored to Docker Hub;
- `webadmin` — published administration UI from GHCR by default, mirrored to Docker Hub, on port `8090`;
- `pihole` — Pi-hole image, with its web UI on port `8053` by default.

The default deployment is **package-only**. `compose.yaml` does not build the application from local source. It pulls the published Server and WebAdmin images plus Pi-hole.

GHCR remains the default registry used by the project. The same validated Server, WebAdmin and VPN images are also mirrored to Docker Hub under `edmanique/stremio-libtorrent-server-webadmin`, so Docker Hub can be used as an alternative registry without rebuilding the application.

The current server release is tracked by `SERVER_VERSION` / `FORK_VERSION`, WebAdmin by `webadmin/WEBADMIN_VERSION`, and the core package version by `pyproject.toml`.

Current platform release:

```text
Upstream Core   1.6.20
Fork/Platform   3.0.2
WebAdmin        3.0.2
VPN Gateway     3.0.2
```

## 1. Obtain the deployment files

For production, download the `stremio-webadmin-<version>-deployment.zip` or `.tar.gz` attached to the GitHub Release. This package contains only the supported deployment surface and excludes source code, tests and CI tooling.

```bash
mkdir -p /opt/stremio-webadmin
tar -xzf stremio-webadmin-<version>-deployment.tar.gz -C /opt/stremio-webadmin --strip-components=1
cd /opt/stremio-webadmin
cp .env.example .env
```

For source development only, clone the repository and use `development`:

```bash
git clone https://github.com/emmanique/stremio-libtorrent-server-webadmin.git
cd stremio-libtorrent-server-webadmin
git checkout development
```

The application itself is **not built from the deployment package**. Compose pulls the published Server, WebAdmin and VPN images from the selected registry.

## 2. Published images

### GHCR — default

The default images are:

```text
ghcr.io/emmanique/stremio-libtorrent-server-webadmin:latest
ghcr.io/emmanique/stremio-libtorrent-server-webadmin-webadmin:latest
ghcr.io/emmanique/stremio-libtorrent-server-webadmin-vpn:latest
pihole/pihole:latest
```

You can pin the coordinated release in `.env`:

```env
STREMIO_IMAGE=ghcr.io/emmanique/stremio-libtorrent-server-webadmin:3.0.2
WEBADMIN_IMAGE=ghcr.io/emmanique/stremio-libtorrent-server-webadmin-webadmin:3.0.2
VPN_IMAGE=ghcr.io/emmanique/stremio-libtorrent-server-webadmin-vpn:3.0.2
```

### Docker Hub — alternative mirror

The same validated artifacts are mirrored to Docker Hub using tags in a single repository:

```text
edmanique/stremio-libtorrent-server-webadmin:latest
edmanique/stremio-libtorrent-server-webadmin:3.0.2

edmanique/stremio-libtorrent-server-webadmin:webadmin-latest
edmanique/stremio-libtorrent-server-webadmin:webadmin-3.0.2

edmanique/stremio-libtorrent-server-webadmin:vpn-latest
edmanique/stremio-libtorrent-server-webadmin:vpn-3.0.2
```

To use Docker Hub instead of GHCR, set the image overrides in `.env`:

```env
STREMIO_IMAGE=edmanique/stremio-libtorrent-server-webadmin:3.0.2
WEBADMIN_IMAGE=edmanique/stremio-libtorrent-server-webadmin:webadmin-3.0.2
VPN_IMAGE=edmanique/stremio-libtorrent-server-webadmin:vpn-3.0.2
```

Or follow the moving aliases:

```env
STREMIO_IMAGE=edmanique/stremio-libtorrent-server-webadmin:latest
WEBADMIN_IMAGE=edmanique/stremio-libtorrent-server-webadmin:webadmin-latest
VPN_IMAGE=edmanique/stremio-libtorrent-server-webadmin:vpn-latest
```

For reproducible deployments, prefer the versioned tags. GHCR and Docker Hub contain the same validated release artifacts; they are not independently rebuilt.

Do not store passwords, API tokens, private keys or certificates in the versioned `.env`.

## 3. Host IP detection

The `.env.example` template leaves `IPADDRESS`, `PIHOLE_WEB_BIND_IP` and `PIHOLE_DNS_BIND_IP` empty. A local `.env` is created from that template.

Start the stack through `start.sh`. Before Docker Compose is evaluated, the script asks the Linux routing table which IPv4 address the host would use for its default route. That address is exported as `IPADDRESS` and is also used for the Pi-hole bindings.

For example, on a host currently using `192.168.1.244`, the launcher prints:

```text
[start] detected host IPv4: 192.168.1.244
[start] Web Player : http://192.168.1.244:8080
[start] WebAdmin   : http://192.168.1.244:8090
[start] API        : http://192.168.1.244:11470
[start] Library    : https://192.168.1.244:12470/library/
```

If the machine later receives another address through DHCP, running `start.sh` again detects the new address automatically. With `IPADDRESS_SOURCE=auto`, the local `.env` is refreshed by the launcher when the host address changes.

To force a specific address for a particular run:

```bash
IPADDRESS=192.168.1.244 sh start.sh
```

## 4. Start or update the full stack

Recommended:

```bash
sh start.sh
```

With no arguments, the launcher performs:

```bash
docker compose pull
docker compose up -d
```

No `docker compose build` is required.

You can also pass any Docker Compose command through the launcher:

```bash
sh start.sh config
sh start.sh ps
sh start.sh up -d --force-recreate
```

To update all published services manually:

```bash
docker compose pull
docker compose up -d
```

The persistent volumes remain untouched during image updates. Do not use `docker compose down -v` during upgrades unless you intentionally want to delete cache/configuration data.

The WebAdmin reports independent Server and WebAdmin versions. Server updates use a transactional GHCR package pull with health validation and rollback. A Server-only update replaces only the Stremio runtime; it does not recreate WebAdmin or Pi-hole.

WebAdmin updates are host-side:

```bash
docker compose pull webadmin
docker compose up -d --no-deps webadmin
```

## 5. Access the services

Use the IP printed by `start.sh`. If the detected address is `192.168.1.244`:

| Service | Address |
| --- | --- |
| Web Player | `http://192.168.1.244:8080` |
| WebAdmin | `http://192.168.1.244:8090` |
| Streaming API | `http://192.168.1.244:11470` |
| HTTPS / Stremio endpoint | `https://192.168.1.244:12470` |
| Library | `https://192.168.1.244:12470/library/` |
| Pi-hole Web | `http://192.168.1.244:8053/admin/` |

The Compose file binds published ports to the detected `IPADDRESS`. Therefore `127.0.0.1:<port>` on the Docker host is not expected to answer those published ports when a specific LAN address is in use.

`IPADDRESS` is also passed to the Stremio container so the entrypoint can obtain the matching trusted `*.stremio.rocks` certificate.

## 6. Cache / Library Addon

The Library addon is enabled by default in `.env` and `compose.yaml`.

Open the Library URL printed by `start.sh`, for example:

```text
https://192.168.1.244:12470/library/
```

After signing in with the owning Stremio account, use the **Watch this library in Stremio** panel to copy the generated addon manifest URL and install it in Stremio.

The addon exposes:

- a `My Library` catalog containing content already present on the server;
- local streams for recognised cached movies/episodes;
- automatic learning of `IMDb/Stremio ID → cached torrent` from playback reports, without exposing file names in logs.

`STREMIOSRV_LIBRARY_ADDON_ALLOW` is empty by default, which activates the server's built-in private-network allowlist. That already includes RFC1918 LAN ranges such as `192.168.0.0/16`.

## 7. Validate the server

First ask the launcher which address Compose will use:

```bash
sh start.sh config | grep -E 'published|IPADDRESS|11470' || true
```

Then test the address printed by `start.sh`. Example:

```bash
curl -fsS http://192.168.1.244:11470/health
curl -fsS http://192.168.1.244:11470/stats.json | python3 -m json.tool
```

To test the process directly inside the container, independent of host port binding:

```bash
docker exec stremio-libtorrent-server curl -fsS http://127.0.0.1:11470/health
```

If the host-address request fails, inspect:

```bash
sh start.sh ps
ss -lntp | grep 11470 || true
docker compose logs --tail=200 stremio-libtorrent-server
```

For Library learning diagnostics, look under `playback` for:

```text
librarySubtitlesAsks
librarySubtitlesReports
libraryLabelsLearned
```

For contributors using a full source checkout, the repository also contains `tools/platform_performance_test.py` and `docs/PERFORMANCE.md`. These development diagnostics are intentionally not included in the minimal production deployment package.

## 8. Pi-hole LAN DNS (optional)

The base `compose.yaml` does not publish DNS port 53 on the host. When LAN DNS exposure is required, preserve the automatically detected address while adding the DNS override:

```bash
IPADDRESS="$(ip route get 1.1.1.1 | awk '{for (i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}')"
export IPADDRESS PIHOLE_DNS_BIND_IP="$IPADDRESS"
docker compose -f compose.yaml -f compose.dns.yaml up -d
```

Ensure host port 53 is available first.

## 9. Automatic VAAPI / NVIDIA transcoding

Transcoding is **AUTO-only** in 3.0.2. There is no manual playback profile for Copy, H.264, HEVC, VAAPI, NVENC or CPU.

The decision flow is:

```text
Stremio core
   |
   +-- compatible media --> Direct Stream / video copy
   |
   +-- transcode required --> requested output codec
                                |
                                +-- AUTO backend discovery
                                      +-- VAAPI when valid
                                      +-- NVENC when valid
                                      +-- Stremio/CPU default otherwise
```

GPU detection never forces transcoding. A VAAPI/NVENC-capable host may legitimately show an active playback with `-c:v copy`; that means Stremio decided video transcoding was unnecessary.

Normal installations should keep:

```env
GPU_BACKEND=auto
VAAPI_DEVICE=
LIBVA_DRIVER_NAME=
TRANSCODING_MODE=auto
TRANSCODING_HWACCEL=auto
```

`start.sh` detects and applies the supported GPU overlay. Use the Compose overlays directly only for diagnostics or deliberate manual deployment:

VAAPI:

```bash
VAAPI_DEVICE=/dev/dri/renderD129 docker compose -f compose.yaml -f compose.vaapi.yaml up -d
```

NVIDIA/NVENC:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml up -d
```

Do not copy the example `renderD129` blindly; use the render node detected on the actual host.

WebAdmin shows hardware capabilities and live runtime telemetry. H.264/HEVC hardware tests are diagnostics only and do not select the codec for playback. Legacy manual profile/codec settings from older installations are retained for compatibility but are no longer authoritative execution controls.

Validate discovery and runtime state with:

```bash
curl -fsS http://HOST-IP:11470/transcode.json | python3 -m json.tool
curl -fsS http://HOST-IP:8090/api/transcoding/status | python3 -m json.tool
```

For a real hardware-transcode validation, start media/client playback for which **Stremio itself** decides that video transcoding is required. Then verify the active FFmpeg command and GPU device usage. Do not force H.264/HEVC merely to make the GPU appear active.

Equivalent HLS requests are deduplicated by effective workload and may share one main video FFmpeg/HLS job. Subtitle extraction can run as a separate FFmpeg process and should not be interpreted as a duplicate video transcode.


## 10. VPN in 3.x

There is no separate VPN Compose stack in 3.x.

Start the platform normally:

```bash
sh start.sh
```

On first start the gateway remains in DIRECT mode. Configure a CyberGhost/OpenVPN profile in **WebAdmin → VPN**, then enable the VPN there. Disabling VPN returns the persistent gateway to DIRECT mode without stopping the Gluetun container or changing Stremio's network namespace.

The legacy `start-vpn.*` files are compatibility wrappers only.


## Upgrade rule

Before every upgrade run `sh scripts/backup-before-upgrade.sh`, keep the existing `.env`, extract the new deployment package over the installation directory, run `sh scripts/check-env-upgrade.sh` to identify newly introduced variables, review any reported changes, run `sh start.sh config`, then start the stack with `sh start.sh`. Never use `docker compose down -v` for a routine upgrade.

## 3.0.1 AUTO launcher and transcoding

Use `./start.sh` for normal installation/startup. It detects the host IP and GPU, exports the detected VAAPI render node to the Compose overlay, and leaves `VAAPI_DEVICE` portable/unset in `.env` unless the administrator explicitly overrides it. `./start.sh --help` is side-effect-free: it does not create/update `.env`, probe hardware, pull images, or start the stack. Direct use of `compose.vaapi.yaml` bypasses discovery and requires `VAAPI_DEVICE` in the invoking shell.

AUTO preserves Stremio's playback decision: COPY stays COPY. Only after the core requests video transcoding does AUTO select the available execution backend (VAAPI encode, NVENC encode, or CPU/libx264 fallback). Hardware decode is not forced by GPU discovery.
