#!/usr/bin/env python3
"""Run and validate the versioned functional regression matrix."""
from __future__ import annotations
import argparse
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
MATRIX = ROOT / "tools/ci/functional-regression.matrix"

def load():
    groups: dict[str, list[str]] = {}
    current = None
    for raw in MATRIX.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1]
            groups[current] = []
        elif current:
            groups[current].append(line)
        else:
            raise SystemExit(f"Entry outside group: {line}")
    return groups

def validate(groups):
    errors = []
    for group, files in groups.items():
        if not files:
            errors.append(f"{group}: empty")
        for rel in files:
            if not (ROOT / rel).is_file():
                errors.append(f"{group}: missing {rel}")
    all_tests = {str(p.relative_to(ROOT)) for p in (ROOT / "tests").glob("test_*.py")}
    covered = {p for files in groups.values() for p in files}
    missing = sorted(all_tests - covered)
    if missing:
        errors.append("unclassified tests: " + ", ".join(missing))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Matrix valid: {len(groups)} groups, {len(all_tests)} test files classified.")
    return 0

def run(group, files):
    print(f"\n=== FUNCTION: {group} ({len(files)} files) ===", flush=True)
    cmd = ["uv","run","--frozen","--with","pytest","--with-requirements","webadmin/requirements.txt",
           "python","-m","pytest","-q","-m","not integration",*files]
    return subprocess.call(cmd, cwd=ROOT)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("group", nargs="?", default="all")
    ap.add_argument("--validate", action="store_true")
    args=ap.parse_args()
    groups=load()
    if validate(groups):
        return 1
    if args.validate:
        return 0
    selected=list(groups) if args.group=="all" else [args.group]
    if args.group!="all" and args.group not in groups:
        print("Unknown group. Available: "+", ".join(groups), file=sys.stderr)
        return 2
    for group in selected:
        if run(group, groups[group]):
            return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
