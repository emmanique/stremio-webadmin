#!/usr/bin/env bash
set -euo pipefail

bash tools/ci/repo-guard.sh
python -m compileall -q src webadmin docker tools
python -m compileall -q tools/ci tools/release tools/upstream

for file in start.sh start-vpn.sh vpn/entrypoint.sh docker/launch.sh docker/publish.sh docker/push-readme.sh tools/ci/repo-guard.sh tools/ci/static-check.sh tools/ci/compose-check.sh tools/ci/run-tests.sh; do
  sh -n "$file" 2>/dev/null || bash -n "$file"
done

node --check webadmin/static/component-versions.js
node --check webadmin/static/transcoding-dashboard.js
node --check webadmin/static/transcoding-runtime-fix.js
node --check webadmin/static/transcoding-simple-config.js
node --check webadmin/static/vpn-admin.js
node --check webadmin/static/addon-connect.js

pwsh -NoProfile -Command '
  $ErrorActionPreference = "Stop"
  foreach ($file in @("start.ps1", "start-vpn.ps1")) {
    $tokens = $null
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile(
      (Resolve-Path $file), [ref]$tokens, [ref]$errors
    ) | Out-Null
    if ($errors.Count -gt 0) {
      $errors | ForEach-Object { Write-Host $_.Message -ForegroundColor Red }
      exit 1
    }
  }
'
