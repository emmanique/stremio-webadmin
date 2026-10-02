#!/usr/bin/env python3
from __future__ import annotations

import os
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, value: str) -> None:
    (ROOT / path).write_text(value, encoding="utf-8")


def main() -> None:
    requested = os.environ.get("REQUESTED_VERSION", "").strip()
    current = read("FORK_VERSION").strip()
    server = read("SERVER_VERSION").strip()
    core_match = re.search(r'(?m)^version\s*=\s*"([^"]+)"\s*$', read("pyproject.toml"))
    if not core_match:
        raise SystemExit("Could not read pyproject.toml version")
    core = core_match.group(1)
    if server != core:
        raise SystemExit(f"Core version mismatch: SERVER_VERSION={server}, pyproject.toml={core}")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", requested):
        raise SystemExit(f"Invalid semantic version: {requested!r}")

    current_tuple = tuple(map(int, current.split(".")))
    requested_tuple = tuple(map(int, requested.split(".")))
    if requested_tuple <= current_tuple:
        raise SystemExit(f"Version must increase: current={current}, requested={requested}")
    if requested_tuple[0] != 2:
        raise SystemExit("This release workflow manages the 2.x line only.")

    write("FORK_VERSION", requested + "\n")
    write("webadmin/WEBADMIN_VERSION", requested + "\n")

    notes = ROOT / "docs" / "releases" / f"v{requested}.md"
    if notes.exists():
        raise SystemExit(f"Release notes already exist: {notes.relative_to(ROOT)}")
    notes.write_text(
        f"""# Stremio Server WebAdmin {requested}

## Summary

TODO: Describe the user-visible changes in this release.

## Components

- Fork platform: {requested}
- WebAdmin: {requested}
- VPN gateway: {requested}
- Integrated server/core: {server}

## Validation

TODO: Record Fast CI, Full regression, integration, image smoke tests and deployment-package validation.

## Upgrade notes

TODO: Document new/removed variables, persistent-state migrations and any operator action. If there is no manual action, state that explicitly.
""",
        encoding="utf-8",
    )

    subprocess.run(["uv", "lock"], cwd=ROOT, check=True)
    print(
        f"Prepared platform version {current} -> {requested} "
        f"(integrated core remains {server}). "
        "README/QUICKSTART are intentionally not rewritten automatically; update them in the release PR."
    )


if __name__ == "__main__":
    main()
