#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import re

root = pathlib.Path(__file__).resolve().parents[2]
version = (root / "FORK_VERSION").read_text(encoding="utf-8").strip()
readme = (root / "README.md").read_text(encoding="utf-8")
quick = (root / "QUICKSTART.md").read_text(encoding="utf-8")
notes_path = root / "docs" / "releases" / f"v{version}.md"

errors: list[str] = []
if not re.search(rf"^# Stremio Server WebAdmin {re.escape(version)}\s*$", readme, re.M):
    errors.append(f"README.md title must identify current platform version {version}")
if version not in quick:
    errors.append(f"QUICKSTART.md must reference current platform version {version}")
if not notes_path.is_file():
    errors.append(f"Missing release notes: {notes_path.relative_to(root)}")
else:
    notes = notes_path.read_text(encoding="utf-8")
    if "TODO:" in notes or "Describe the user-visible changes" in notes:
        errors.append(f"Release notes {notes_path.name} still contain TODO/placeholder text")
    for heading in ("## Summary", "## Components", "## Validation", "## Upgrade notes"):
        if heading not in notes:
            errors.append(f"Release notes {notes_path.name} missing {heading}")

if errors:
    raise SystemExit("Release documentation contract failed:\n- " + "\n- ".join(errors))
print(f"Release documentation contract OK for {version}")
