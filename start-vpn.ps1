$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Get-PreferredIPv4 {
    if ($env:IPADDRESS) { return $env:IPADDRESS }

    $udp = $null
    try {
        $udp = New-Object System.Net.Sockets.UdpClient
        $udp.Connect('1.1.1.1', 53)
        $endpoint = [System.Net.IPEndPoint]$udp.Client.LocalEndPoint
        $ip = $endpoint.Address.IPAddressToString
        $udp.Dispose()
        if ($ip) { return $ip }
    } catch {
        try { if ($udp) { $udp.Dispose() } } catch {}
    }

    try {
        $cfg = Get-NetIPConfiguration |
            Where-Object { $_.IPv4DefaultGateway -and $_.IPv4Address } |
            Sort-Object { $_.NetIPv4Interface.RouteMetric } |
            Select-Object -First 1
        if ($cfg) { return $cfg.IPv4Address.IPAddress }
    } catch {}

    return $null
}

function Test-IPv4([string]$Address) {
    $parsed = $null
    if (-not [System.Net.IPAddress]::TryParse($Address, [ref]$parsed)) { return $false }
    return $parsed.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork
}

function New-ControlKey {
    $bytes = New-Object byte[] 24
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return (($bytes | ForEach-Object { $_.ToString('x2') }) -join '')
}

function Protect-KeyFile([string]$Path) {
    try {
        $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        $acl = Get-Acl $Path
        $acl.SetAccessRuleProtection($true, $false)
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($identity, 'FullControl', 'Allow')
        $acl.SetAccessRule($rule)
        Set-Acl -Path $Path -AclObject $acl
    } catch {
        Write-Warning "[vpn] could not tighten ACLs on ${Path}: $($_.Exception.Message)"
    }
}

function Invoke-NativeQuiet([string]$FilePath, [string[]]$Arguments) {
    $previousPreference = $ErrorActionPreference
    try {
        # Windows PowerShell 5.1 turns native stderr into ErrorRecord objects.
        # Several Docker checks below are probes where a non-zero result is
        # expected and handled explicitly.
        $ErrorActionPreference = 'Continue'
        & $FilePath @Arguments *> $null
        return [int]$LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
}

function Test-ContainerExists([string]$Name) {
    $rc = Invoke-NativeQuiet 'docker' @('container', 'inspect', $Name)
    return $rc -eq 0
}

function Invoke-Compose([string[]]$ComposeArgs) {
    $dockerArgs = @('compose', '-f', 'compose.vpn.yaml') + $ComposeArgs
    & docker @dockerArgs | Out-Host
    $code = $LASTEXITCODE
    return [int]$code
}

$ip = Get-PreferredIPv4
if (-not $ip -or -not (Test-IPv4 $ip)) {
    [Console]::Error.WriteLine('[vpn] unable to determine a valid host IPv4 address. Set $env:IPADDRESS, e.g. $env:IPADDRESS="192.168.1.244"; .\start-vpn.ps1')
    exit 1
}

$env:IPADDRESS = $ip
if (-not $env:PIHOLE_WEB_BIND_IP) { $env:PIHOLE_WEB_BIND_IP = $ip }
if (-not $env:PIHOLE_DNS_BIND_IP) { $env:PIHOLE_DNS_BIND_IP = $ip }

$trustedDomain = ($ip -replace '\.', '-') + '.519b6502d940.stremio.rocks'
$keyFile = if ($env:VPN_CONTROL_KEY_FILE) { $env:VPN_CONTROL_KEY_FILE } else { Join-Path $Root '.vpn-control-key' }

if (-not $env:VPN_CONTROL_API_KEY) {
    if (Test-Path $keyFile) {
        $env:VPN_CONTROL_API_KEY = (Get-Content -Raw $keyFile).Trim()
    } else {
        $env:VPN_CONTROL_API_KEY = New-ControlKey
        Set-Content -Path $keyFile -Value $env:VPN_CONTROL_API_KEY -NoNewline -Encoding ASCII
        Protect-KeyFile $keyFile
        Write-Host '[vpn] generated private Gluetun control key in .vpn-control-key'
    }
}

$composeVersionRc = Invoke-NativeQuiet 'docker' @('compose', 'version')
if ($composeVersionRc -ne 0) {
    [Console]::Error.WriteLine('[vpn] Docker Compose is not available. Install/start Docker Desktop and use Linux containers.')
    exit 1
}

Write-Host "[vpn] host IPv4 : $ip"
Write-Host "[vpn] Web Player : http://${ip}:8080"
Write-Host "[vpn] WebAdmin   : http://${ip}:8090"
Write-Host "[vpn] API        : http://${ip}:11470"
Write-Host "[vpn] Library    : https://${trustedDomain}:12470/library/"
Write-Host "[vpn] Pi-hole    : http://$($env:PIHOLE_WEB_BIND_IP):8053/admin/"
Write-Host '[vpn] Stremio Internet egress is fail-closed behind Gluetun.'
Write-Host '[vpn] Docker Desktop must be running with the Linux/WSL2 backend.'

if ($args.Count -eq 0) {
    Write-Host '[vpn] pulling published images...'
    $rc = Invoke-Compose @('pull')
    if ($rc -ne 0) { exit $rc }

    $vpnImage = if ($env:VPN_IMAGE) { $env:VPN_IMAGE } else { 'ghcr.io/emmanique/stremio-libtorrent-server-webadmin-vpn:latest' }
    Write-Host '[vpn] checking TUN support in the Docker Desktop Linux backend...'
    $tunRc = Invoke-NativeQuiet 'docker' @('run', '--rm', '--privileged', '--device', '/dev/net/tun:/dev/net/tun', '--entrypoint', '/bin/sh', $vpnImage, '-c', 'test -c /dev/net/tun')
    if ($tunRc -ne 0) {
        [Console]::Error.WriteLine('[vpn] /dev/net/tun is not available to Docker Desktop. Ensure Linux containers/WSL2 are enabled and restart Docker Desktop.')
        exit 1
    }

    Write-Host '[vpn] validating/refreshing trusted LAN certificate outside the VPN tunnel...'
    $rc = Invoke-Compose @('--profile', 'bootstrap', 'run', '--rm', 'cert-bootstrap')
    if ($rc -ne 0) {
        [Console]::Error.WriteLine('[vpn] trusted stremio.rocks certificate is not available. VPN mode was not started.')
        exit 1
    }

    if (-not (Test-ContainerExists 'stremio-gluetun') -and (Test-ContainerExists 'stremio-libtorrent-server')) {
        Write-Host '[vpn] switching direct -> VPN mode (persistent volumes are preserved)...'
        [void](Invoke-NativeQuiet 'docker' @('rm', '-f', 'stremio-libtorrent-server'))
    }

    $rc = Invoke-Compose @('up', '-d', '--remove-orphans')
    exit $rc
}

$rc = Invoke-Compose $args
exit $rc
