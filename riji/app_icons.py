"""Application icon extraction and caching."""

from __future__ import annotations

import hashlib
import platform
import plistlib
import shutil
import subprocess
from pathlib import Path

from . import config

ICON_DIR = config.DATA_DIR / "app-icons"


def icon_url(app_name: str | None) -> str:
    if not app_name:
        return ""
    path = ensure_icon(app_name)
    return f"/app-icons/{_icon_filename(app_name)}" if path else ""


def ensure_icon(app_name: str) -> Path | None:
    if platform.system() != "Darwin":
        return None
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    out = ICON_DIR / _icon_filename(app_name)
    if out.exists() and out.stat().st_size > 0:
        return out
    app_path = _find_app(app_name)
    if not app_path:
        return None
    source = _icon_source(app_path)
    if not source:
        return None
    try:
        subprocess.run(["sips", "-s", "format", "png", str(source), "--out", str(out)], check=True, capture_output=True)
        return out if out.exists() else None
    except (OSError, subprocess.SubprocessError):
        return None


def resolve_cached(filename: str) -> Path | None:
    if "/" in filename or ".." in filename:
        return None
    path = ICON_DIR / filename
    return path if path.exists() else None


def _find_app(app_name: str) -> Path | None:
    candidates = [
        Path("/Applications") / f"{app_name}.app",
        Path.home() / "Applications" / f"{app_name}.app",
        Path("/System/Applications") / f"{app_name}.app",
    ]
    for path in candidates:
        if path.exists():
            return path
    try:
        result = subprocess.run(
            ["mdfind", f"kMDItemKind == 'Application' && kMDItemFSName == '{app_name}.app'"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for line in result.stdout.splitlines():
        path = Path(line.strip())
        if path.exists() and path.suffix == ".app":
            return path
    return None


def _icon_source(app_path: Path) -> Path | None:
    plist_path = app_path / "Contents" / "Info.plist"
    try:
        info = plistlib.loads(plist_path.read_bytes())
    except (OSError, plistlib.InvalidFileException):
        return None
    icon = info.get("CFBundleIconFile")
    if not icon:
        return None
    icon_path = app_path / "Contents" / "Resources" / icon
    if icon_path.suffix == "":
        icon_path = icon_path.with_suffix(".icns")
    if icon_path.exists():
        return icon_path
    fallback = shutil.which("fileicon")
    if fallback:
        return None
    return None


def _icon_filename(app_name: str) -> str:
    digest = hashlib.sha1(app_name.encode("utf-8")).hexdigest()[:12]
    return f"{digest}.png"
