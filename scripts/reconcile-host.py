#!/usr/bin/env python3
"""Host-side integration: Gateway observations are consumed by existing Stremio port sync."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def main():
    if not (ROOT / ".env").is_file():
        print("Stremio .env unavailable", file=sys.stderr)
        return 1
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/gateway-port-sync.py")],
        cwd=ROOT, timeout=180, check=False,
    )
    return result.returncode

if __name__ == "__main__":
    raise SystemExit(main())
