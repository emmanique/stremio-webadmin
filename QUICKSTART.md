# Quick Start

This fork runs three coordinated services with Docker Compose:

- `stremio-libtorrent-server` — Stremio streaming engine and HTTPS endpoint;
- `webadmin` — administration UI on port `8090`;
- `pihole` — internal DNS service, with its web UI on port `8053` by default.

The current server release is tracked by `SERVER_VERSION` / `FORK_VERSION` and the core package version by `pyproject.toml`.

## 1. Host IP detection

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

Do not store passwords, API tokens, private keys or certificates in the versioned `.env`.

## 2. Start the stack

Recommended:

```bash
sh start.sh
```

This is equivalent to running `docker compose up -d --build`, but with the host IPv4 detected and exported first.

You can also pass any Docker Compose command through the launcher:

```bash
sh start.sh config
sh start.sh ps
sh start.sh up -d --build --force-recreate
```

Do not use `docker compose down -v` during upgrades unless you intentionally want to delete persistent volumes.

## 3. Access the services

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

## 4. Cache / Library Addon

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

`STREMIOSRV_LIBRARY_ADDON_ALLOW` is empty by default, which activates the server's built-in private-network allowlist. That already includes RFC1918 LAN ranges such as `192.168.0.0/16`, so changing from `192.168.1.254` to `192.168.1.244` requires no addon CIDR edit.

## 5. Validate the server

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

## 6. Pi-hole LAN DNS (optional)

The base `compose.yaml` does not publish DNS port 53 on the host. When LAN DNS exposure is required, preserve the automatically detected address while adding the DNS override:

```bash
IPADDRESS="$(ip route get 1.1.1.1 | awk '{for (i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}')"
export IPADDRESS PIHOLE_DNS_BIND_IP="$IPADDRESS"
docker compose -f compose.yaml -f compose.dns.yaml up -d
```

Ensure host port 53 is available first.

## 7. VAAPI (optional)

Use the provided VAAPI compose override when the host exposes `/dev/dri` and hardware acceleration is required. The default `.env` keeps the fork's VAAPI-oriented transcoding policy while retaining software fallback.
