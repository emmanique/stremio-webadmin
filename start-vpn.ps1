Write-Host "[vpn] start-vpn.ps1 is kept only for compatibility."
Write-Host "[vpn] This release uses one compose.yaml. Start the platform normally and enable VPN in WebAdmin -> VPN."
& "$PSScriptRoot\start.ps1" @args
exit $LASTEXITCODE
