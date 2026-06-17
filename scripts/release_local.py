"""Build local release artifacts for macOS and Windows."""

from __future__ import annotations

import shutil
import subprocess
import sys
import hashlib
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
MAC_APP = DIST / "书赫日报助手.app"
MAC_ZIP = DIST / "shuhe-riji-macos-app.zip"
MAC_DMG = DIST / "shuhe-riji-macos.dmg"
WIN_ZIP = DIST / "shuhe-riji-windows-portable.zip"
CHECKSUMS = DIST / "SHA256SUMS"


def main() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True, exist_ok=True)
    _run([sys.executable, "-m", "riji", "package-app", "--output", str(DIST), "--mode", "desktop", "--portable"])
    _zip_mac_app()
    _run([sys.executable, "-m", "riji", "package-dmg", "--output", str(DIST), "--mode", "desktop"])
    _remove_staging_app()
    _run([sys.executable, "-m", "riji", "package-windows", "--output", str(DIST)])
    _write_checksums([MAC_ZIP, MAC_DMG, WIN_ZIP])
    print(f"macOS:   {MAC_ZIP}")
    print(f"DMG:     {MAC_DMG}")
    print(f"Windows: {WIN_ZIP}")
    print(f"SHA256:  {CHECKSUMS}")


def _zip_mac_app() -> None:
    if not MAC_APP.exists():
        raise FileNotFoundError(MAC_APP)
    if MAC_ZIP.exists():
        MAC_ZIP.unlink()
    if shutil.which("ditto"):
        _run(["ditto", "-c", "-k", "--norsrc", "--keepParent", str(MAC_APP), str(MAC_ZIP)])
        return
    archive_base = DIST / "shuhe-riji-macos-app"
    shutil.make_archive(str(archive_base), "zip", root_dir=DIST, base_dir=MAC_APP.name)


def _run(args: list[str]) -> None:
    env = os.environ.copy()
    env["COPYFILE_DISABLE"] = "1"
    subprocess.run(args, cwd=ROOT, check=True, env=env)


def _remove_staging_app() -> None:
    if MAC_APP.exists():
        shutil.rmtree(MAC_APP)


def _write_checksums(paths: list[Path]) -> None:
    lines = []
    for path in paths:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.name}")
    CHECKSUMS.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
