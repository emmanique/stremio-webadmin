@echo off
setlocal EnableExtensions

echo [vpn] start-vpn.bat is kept only for compatibility.
echo [vpn] This release uses one compose.yaml. Start the platform normally and enable VPN in WebAdmin ^> VPN.

set "SCRIPT_DIR=%~dp0"

where powershell.exe >nul 2>&1
if errorlevel 1 (
    echo [vpn] PowerShell is required on Windows.
    exit /b 1
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start-vpn.ps1" %*
exit /b %ERRORLEVEL%
