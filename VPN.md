# VPN / CyberGhost — 2.x

Version 2.x uses one Docker Compose topology for DIRECT and VPN operation. The Gluetun container is a persistent gateway and owns the network namespace shared by `stremio-libtorrent-server`.

## Runtime states

```text
VPN disabled
  Gluetun container  running
  OpenVPN tunnel     stopped
  Stremio egress     direct

VPN enabled
  Gluetun container  running
  OpenVPN tunnel     running
  Stremio egress     CyberGhost/OpenVPN

VPN enabled + failure
  Gluetun container  running
  OpenVPN tunnel     failed/recovering
  Stremio egress     fail-closed
```

Stopping VPN does not stop the Gluetun container.

## First start

No VPN account is required for the initial installation:

```bash
sh start.sh
```

The platform starts in DIRECT mode. Open **WebAdmin → VPN** when you are ready to configure VPN.

## CyberGhost profile

Create a manual OpenVPN configuration in the CyberGhost portal. Import the ZIP in WebAdmin. It must contain:

```text
openvpn.ovpn
ca.crt
client.crt
client.key
```

Provide the generated OpenVPN username and password. Secrets and certificates are stored only in the private persistent `vpn-data` volume and are not returned to the browser after saving.

## Lifecycle

WebAdmin supports:

- Create and edit VPN profiles.
- Activate a profile.
- Enable or disable VPN.
- Reconnect the active tunnel.
- Select startup profile.
- Change active profile without restarting the gateway container.
- Test VPN protection.
- Inspect redacted VPN/Gluetun logs.

The persistent state file `/vpn/enabled` records whether VPN is requested. If VPN was enabled before a host/container restart, the supervisor attempts to restore the VPN state.

## Network namespace

Stremio always uses:

```yaml
network_mode: "service:gluetun"
```

This is intentional. It prevents DIRECT and VPN modes from having different container topology and protects WebAdmin Save/Restart behavior from mode changes.

## DNS path

Pi-hole always forwards to the private gateway DNS bridge:

```text
172.30.0.10#1053
```

DIRECT:

```text
Stremio → Pi-hole → Gateway DNS bridge → public resolver
```

VPN:

```text
Stremio → Pi-hole → Gateway DNS bridge → Gluetun resolver → VPN
```

## Fail-closed rule

When VPN is explicitly enabled and the tunnel fails, the supervisor does not intentionally enable direct fallback. Direct egress returns only after the user disables VPN.

## Configuration and Server restart

VPN state must not block WebAdmin management.

The following are supported in all states:

| State | Save configuration | Restart Stremio |
| --- | --- | --- |
| VPN not configured | Yes | Yes |
| VPN configured / OFF | Yes | Yes |
| VPN connected | Yes | Yes |
| VPN error/recovering | Yes | Yes |

WebAdmin writes `/config/admin-settings.json` through the shared persistent volume and validates that the Stremio container sees the same values. Server restart uses the Docker API and validates `http://127.0.0.1:11470/health` inside the Stremio container.

## Troubleshooting

Container state:

```bash
docker compose ps
```

Gateway logs:

```bash
docker logs --tail=200 stremio-gluetun
```

Stremio network namespace:

```bash
docker inspect stremio-libtorrent-server --format '{{.HostConfig.NetworkMode}}'
```

Expected output starts with `container:` and points to the Gluetun container.

Check Stremio health independently of host port publishing:

```bash
docker exec stremio-libtorrent-server curl -fsS http://127.0.0.1:11470/health
```

If `/dev/net/tun` is unavailable, VPN cannot start, but the platform can still operate in DIRECT mode.

## Compatibility launchers

`start-vpn.sh`, `start-vpn.ps1` and `start-vpn.bat` remain only for compatibility. They start the same unified stack as the normal launcher. VPN itself is controlled through WebAdmin.
