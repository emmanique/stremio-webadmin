# Quick Start

This fork runs three coordinated services with Docker Compose:

- `stremio-libtorrent-server` — published Stremio streaming runtime from GHCR;
- `webadmin` — published administration UI from GHCR on port `8090`;
- `pihole` — Pi-hole image, with its web UI on port `8053` by default.

The default deployment is **package-only**. `compose.yaml` does not build the application from local source. It pulls the published Server and WebAdmin images plus Pi-hole.

The current server release is tracked by `SERVER_VERSION` / `FORK_VERSION`, WebAdmin by `webadmin/WEBADMIN_VERSION`, and the core package version by `pyproject.toml`.

Current coordinated release:

```text
Core            1.6.9
Server/Fork     1.6.9-server.18
WebAdmin        1.4.1
VPN Gateway     1.6.9-server.18
```

## 1. Obtain the deployment files

For a normal managed installation, clone the repository so that you also have `start.sh`, overrides and documentation:

```bash
git clone https://github.com/emmanique/stremio-libtorrent-server-webadmin.git
cd stremio-libtorrent-server-webadmin
```

The application itself is **not built from this checkout**. The checkout only supplies Compose/launcher configuration; application images are pulled from GHCR.

For a minimal one-file deployment you may download only `compose.yaml`:

```bash
mkdir -p stremio-platform
cd stremio-platform
curl -fsSLO https://raw.githubusercontent.com/emmanique/stremio-libtorrent-server-webadmin/main/compose.yaml
docker compose pull
docker compose up -d
```

In that minimal mode, set `IPADDRESS` explicitly when you want ports/certificate generation tied to a specific LAN address.

## 2. Published images

The default images are:

```text
ghcr.io/emmanique/stremio-libtorrent-server-webadmin:latest
ghcr.io/emmanique/stremio-libtorrent-server-webadmin-webadmin:latest
ghcr.io/emmanique/stremio-libtorrent-server-webadmin-vpn:latest
pihole/pihole:latest
```

You can pin the coordinated release in `.env`:

```env
STREMIO_IMAGE=ghcr.io/emmanique/stremio-libtorrent-server-webadmin:1.6.9-server.18
WEBADMIN_IMAGE=ghcr.io/emmanique/stremio-libtorrent-server-webadmin-webadmin:1.4.1
VPN_IMAGE=ghcr.io/emmanique/stremio-libtorrent-server-webadmin-vpn:1.6.9-server.18
```

Do not store passwords, API tokens, private keys or certificates in the versioned `.env`.

## 3. Host IP detection

The tracked `.env` deliberately leaves `IPADDRESS`, `PIHOLE_WEB_BIND_IP` and `PIHOLE_DNS_BIND_IP` empty.

Start the stack through `start.sh`. Before Docker Compose is evaluated, the script asks the Linux routing table which IPv4 address the host would use for its default route. That address is exported as `IPADDRESS` and is also used for the Pi-hole bindings.

For example, on a host currently using `192.168.1.244`, the launcher prints:

```text
[start] detected host IPv4: 192.168.1.244
[start] Web Player : http://192.168.1.244:8080
[start] WebAdmin   : http://192.168.1.244:8090
[start] API        : http://192.168.1.244:11470
[start] Library    : https://192.168.1.244:12470/library/
```

If the machine later receives another address through DHCP, running `start.sh` again detects the new address automatically. The tracked `.env` does not need to be edited.

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
- automatic learning of `IMDb/Stremio ID ↔ cached torrent` from playback reports, without exposing file names in logs.

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

For a full platform/performance check, including container health, HTTP latency, DNS, VPN path and transcoding readiness:

```bash
python3 tools/platform_performance_test.py
```

See `docs/PERFORMANCE.md` for interpretation and optional synthetic encoding tests.

## 8. Pi-hole LAN DNS (optional)

The base `compose.yaml` does not publish DNS port 53 on the host. When LAN DNS exposure is required, preserve the automatically detected address while adding the DNS override:

```bash
IPADDRESS="$(ip route get 1.1.1.1 | awk '{for (i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}')"
export IPADDRESS PIHOLE_DNS_BIND_IP="$IPADDRESS"
docker compose -f compose.yaml -f compose.dns.yaml up -d
```

Ensure host port 53 is available first.

## 9. VAAPI / NVIDIA transcoding (optional)

The platform is **copy first**: compatible streams remain Direct Stream/`copy`. Choosing a hardware profile does not force needless re-encoding. The selected profile is applied only when the Stremio core has already decided that video transcoding is required.

WebAdmin exposes explicit profiles only after real FFmpeg runtime self-tests. Available profiles can include VAAPI encode-only, VAAPI Full GPU, NVIDIA NVENC and CPU libx264/libx265 modes.

VAAPI:

```bash
docker compose -f compose.yaml -f compose.vaapi.yaml up -d
```

NVIDIA/NVENC:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml up -d
```

For VAAPI Full GPU, decoded frames stay on VAAPI surfaces through scaling/format normalization and encoding, using `scale_vaapi` with `NV12` rather than a redundant software-download/hardware-upload cycle.

After starting playback that genuinely requires transcoding, use **WebAdmin → Transcoding** to confirm the selected execution profile, runtime self-test result and effective `[ffmpeg-policy]` decision.
