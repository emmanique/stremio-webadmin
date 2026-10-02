#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import pathlib
import shutil
import tarfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
FILES = [
    ".env.example",
    "compose.yaml",
    "compose.dns.yaml",
    "compose.vaapi.yaml",
    "compose.gpu.yaml",
    "start.sh",
    "start.ps1",
    "start.bat",
    "scripts/backup-before-upgrade.sh",
    "scripts/check-env-upgrade.sh",
    "README.md",
    "QUICKSTART.md",
    "VPN.md",
    "WINDOWS.md",
    "LICENSE",
    "FORK_VERSION",
    "SERVER_VERSION",
    "docs/DEPLOYMENT_PACKAGE.md",
    "docs/CLEAN_INSTALL_TEST.md",
]


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="dist")
    parser.add_argument("--version", default="")
    args = parser.parse_args()

    version = args.version.strip() or (ROOT / "FORK_VERSION").read_text().strip()
    out = ROOT / args.output
    stage = out / f"stremio-webadmin-{version}"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True, exist_ok=True)

    release_notes = f"docs/releases/v{version}.md"
    selected = FILES + ([release_notes] if (ROOT / release_notes).exists() else [])
    for rel in selected:
        src = ROOT / rel
        if not src.is_file():
            raise SystemExit(f"Missing deployment input: {rel}")
        dst = stage / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    zip_path = out / f"stremio-webadmin-{version}-deployment.zip"
    tar_path = out / f"stremio-webadmin-{version}-deployment.tar.gz"
    for path in (zip_path, tar_path):
        path.unlink(missing_ok=True)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(out))

    with tarfile.open(tar_path, "w:gz") as tf:
        tf.add(stage, arcname=stage.name)

    sums = out / "SHA256SUMS"
    sums.write_text(
        f"{sha256(zip_path)}  {zip_path.name}\n{sha256(tar_path)}  {tar_path.name}\n",
        encoding="utf-8",
    )
    print(zip_path)
    print(tar_path)
    print(sums)


if __name__ == "__main__":
    main()
