#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import subprocess
import sys

base = os.environ.get("BASE_SHA", "").strip()
if not base:
    print("BASE_SHA not set; documentation contract skipped")
    raise SystemExit(0)

changed = subprocess.check_output(
    ["git", "diff", "--name-only", f"{base}...HEAD"], text=True
).splitlines()
changed_set = set(changed)

runtime_prefixes = ("src/", "webadmin/", "vpn/", "docker/", "scripts/")
runtime_files = {
    "compose.yaml", "compose.dns.yaml", "compose.gpu.yaml", "compose.vaapi.yaml",
    "start.sh", "start.ps1", "start.bat", ".env.example",
}
user_visible = any(path.startswith(runtime_prefixes) or path in runtime_files for path in changed)

# Require .env.example only when a Compose/launcher diff actually introduces or
# removes an environment-variable reference. Pure topology/comment changes do
# not need a meaningless edit to the template.
config_files = [
    path for path in changed
    if path.startswith("compose") and path.endswith(".yaml")
    or path in {"start.sh", "start.ps1", "start.bat"}
]
config_var_changed = False
if config_files:
    diff = subprocess.check_output(
        ["git", "diff", "--unified=0", f"{base}...HEAD", "--", *config_files],
        text=True,
        errors="replace",
    )
    config_var_changed = bool(re.search(r"^[+-](?![+-]).*\$\{?[A-Z][A-Z0-9_]*", diff, re.M))

errors: list[str] = []
if user_visible and "README.md" not in changed_set:
    errors.append(
        "User-visible/runtime files changed but README.md was not updated. "
        "Document functionality, installation and upgrade impact."
    )
if config_var_changed and ".env.example" not in changed_set:
    errors.append(
        "Runtime environment-variable references changed but .env.example was not updated."
    )

if errors:
    print("Documentation contract failed:", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    raise SystemExit(1)

print("Documentation contract OK")
