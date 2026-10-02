# Windows / Docker Desktop

The repository includes native Windows launchers for Docker Desktop:

```text
start.bat       -> start.ps1       -> direct mode
start-vpn.bat   -> start-vpn.ps1   -> CyberGhost/Gluetun VPN mode
```

The `.bat` files are convenience wrappers for Windows Command Prompt and double-click use. The PowerShell files contain the actual Windows launcher logic so the behaviour stays maintainable and close to the Linux `start.sh` / `start-vpn.sh` launchers.

## Requirements

Use Windows 10/11 x64 with:

- Docker Desktop installed and running;
- Docker Desktop configured for **Linux containers**;
- WSL2 backend enabled/recommended;
- Docker Compose v2 available as `docker compose`;
- PowerShell 5.1 or newer.

VPN mode additionally requires `/dev/net/tun` to be available inside Docker Desktop's Linux backend. `start-vpn.ps1` performs a TUN readiness check before starting Gluetun.

## Clone

From Command Prompt or PowerShell:

```powershell
git clone https://github.com/emmanique/stremio-libtorrent-server-webadmin.git
cd stremio-libtorrent-server-webadmin
```

## Direct mode

Command Prompt:

```bat
start.bat
```

PowerShell:

```powershell
.\start.ps1
```

The launcher:

1. determines the IPv4 address selected by the Windows routing table;
2. exports `IPADDRESS`, `PIHOLE_WEB_BIND_IP` and `PIHOLE_DNS_BIND_IP` to the current launcher process;
3. checks Docker Compose availability;
4. pulls the published images;
5. safely removes transient VPN-mode containers when returning from VPN mode;
6. runs `docker compose up -d --remove-orphans`.

Named volumes are preserved when switching modes.

### Pass Docker Compose commands through the launcher

Command Prompt:

```bat
start.bat config
start.bat ps
start.bat up -d --force-recreate
```

PowerShell:

```powershell
.\start.ps1 config
.\start.ps1 ps
.\start.ps1 up -d --force-recreate
```

## VPN mode

Command Prompt:

```bat
start-vpn.bat
```

PowerShell:

```powershell
.\start-vpn.ps1
```

The VPN launcher additionally:

1. creates or reuses `.vpn-control-key`;
2. restricts the key file ACL to the current Windows user where the filesystem supports Windows ACLs;
3. pulls the Server, WebAdmin and VPN images;
4. validates `/dev/net/tun` inside Docker Desktop;
5. runs the trusted `stremio.rocks` certificate bootstrap outside the VPN path;
6. removes the direct Stremio container only when switching into VPN mode;
7. starts `compose.vpn.yaml` with Gluetun fail-closed routing.

The generated `.vpn-control-key` is already ignored by Git and must remain private.

### Pass VPN Compose commands through the launcher

```bat
start-vpn.bat config
start-vpn.bat ps
start-vpn.bat logs gluetun
```

or:

```powershell
.\start-vpn.ps1 config
.\start-vpn.ps1 ps
.\start-vpn.ps1 logs gluetun
```

## Override the detected IP address

Command Prompt:

```bat
set IPADDRESS=192.168.1.244
start.bat
```

VPN mode:

```bat
set IPADDRESS=192.168.1.244
start-vpn.bat
```

PowerShell:

```powershell
$env:IPADDRESS = '192.168.1.244'
.\start.ps1
```

or:

```powershell
$env:IPADDRESS = '192.168.1.244'
.\start-vpn.ps1
```

## Use Docker Hub instead of GHCR

The default Compose configuration uses GHCR. To use the Docker Hub mirror for the current shell session:

```powershell
$env:STREMIO_IMAGE = 'edmanique/stremio-libtorrent-server-webadmin:1.6.9-server.18'
$env:WEBADMIN_IMAGE = 'edmanique/stremio-libtorrent-server-webadmin:webadmin-1.4.1'
$env:VPN_IMAGE = 'edmanique/stremio-libtorrent-server-webadmin:vpn-1.6.9-server.18'
$env:STREMIO_PACKAGE_REPO = 'edmanique/stremio-libtorrent-server-webadmin'
.\start.ps1
```

For VPN mode use the same variables and run `start-vpn.ps1`.

The same values can be placed in a local `.env` file. Do not put passwords, API tokens, VPN credentials, private keys or certificates in tracked files.

## Windows networking notes

Docker Desktop runs the containers inside a Linux VM/WSL2 backend. The launcher publishes services on the Windows host IPv4 selected by the routing table. If the machine has multiple Ethernet, Wi-Fi, Hyper-V, WSL, VMware or corporate VPN adapters, the automatically selected address may not be the LAN address you want. Override `IPADDRESS` explicitly in that case.

Windows Firewall must allow the required ports on the selected network profile. Typical service ports are:

```text
8080    Web Player
8090    WebAdmin
11470   Streaming API
12470   Trusted HTTPS / Library
8053    Pi-hole Web UI
6881    BitTorrent TCP/UDP in direct mode
```

Do not expose WebAdmin or the Docker socket-backed management interface directly to the public Internet.

## GPU/transcoding notes

NVIDIA GPU acceleration under Docker Desktop normally depends on the Windows NVIDIA driver plus WSL2 GPU support. Validate it from WebAdmin -> Transcoding and with the repository performance test before relying on NVENC.

Linux-style VAAPI device paths such as `/dev/dri/renderD128` are not guaranteed to be available through Docker Desktop on every Windows GPU/driver combination. If `/dev/dri` is not exposed inside the Linux backend, use a supported NVIDIA/NVENC path or CPU transcoding instead.

Selecting a hardware profile does not force re-encoding. The platform remains copy-first and uses the selected execution profile only when Stremio has already requested video transcoding.

## Troubleshooting

Check Docker Desktop:

```powershell
docker version
docker compose version
docker info
```

Resolve the direct Compose configuration:

```powershell
.\start.ps1 config
```

Resolve the VPN Compose configuration:

```powershell
.\start-vpn.ps1 config
```

Show running containers:

```powershell
docker ps
```

Check Server health, replacing the address with the one printed by the launcher:

```powershell
curl.exe -fsS http://192.168.1.244:11470/health
```

VPN logs:

```powershell
docker logs --tail 200 stremio-gluetun
```

If VPN mode reports that `/dev/net/tun` is unavailable, confirm that Docker Desktop is using Linux containers/WSL2, restart Docker Desktop, and retry. The launcher intentionally refuses to start the VPN stack when the TUN device cannot be presented to Gluetun.

## PowerShell execution policy

The `.bat` wrappers launch PowerShell with `-ExecutionPolicy Bypass` for these repository scripts only. This does not change the machine-wide execution policy.

When invoking the `.ps1` files directly, a restrictive local policy may block execution. In that case use the `.bat` wrappers or an approved PowerShell execution policy for your environment.
