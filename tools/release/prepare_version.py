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
    current = read("SERVER_VERSION").strip()

    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", requested):
        raise SystemExit(f"Invalid semantic version: {requested!r}")

    current_tuple = tuple(map(int, current.split(".")))
    requested_tuple = tuple(map(int, requested.split(".")))

    if requested_tuple <= current_tuple:
        raise SystemExit(
            f"Version must increase: current={current}, requested={requested}"
        )
    if requested_tuple[0] != 2:
        raise SystemExit("This release workflow manages the 2.x line only.")

    write("SERVER_VERSION", requested + "\n")
    write("FORK_VERSION", requested + "\n")
    write("webadmin/WEBADMIN_VERSION", requested + "\n")

    pyproject = ROOT / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'(?m)^version\s*=\s*"[^"]+"\s*$',
        f'version = "{requested}"',
        text,
        count=1,
    )
    if count != 1:
        raise SystemExit("Could not update pyproject.toml version")
    pyproject.write_text(updated, encoding="utf-8")

    for filename in ("README.md", "QUICKSTART.md"):
        path = ROOT / filename
        text = path.read_text(encoding="utf-8")
        if current not in text:
            raise SystemExit(
                f"{filename} does not contain current version {current}"
            )
        path.write_text(text.replace(current, requested), encoding="utf-8")

    notes = ROOT / "docs" / "releases" / f"v{requested}.md"
    if not notes.exists():
        notes.write_text(
            f"""# Stremio Server WebAdmin {requested}

## Summary

Describe the user-visible changes in this release.

## Components

- Fork platform/server: {requested}
- WebAdmin: {requested}
- VPN gateway: {requested}

## Validation

- CI
- Dependency validation
- Deterministic regression tests
- Network integration tests
- Server/WebAdmin/VPN image builds and smoke tests

## Upgrade notes

Preserve persistent Docker volumes. Do not use `docker compose down -v` during upgrade.
""",
            encoding="utf-8",
        )

    subprocess.run(["uv", "lock"], cwd=ROOT, check=True)
    print(f"Prepared coordinated version {current} -> {requested}")


if __name__ == "__main__":
    main()
