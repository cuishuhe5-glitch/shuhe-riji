"""Create a lightweight macOS .app wrapper for Shuhe Riji."""

from __future__ import annotations

import os
import plistlib
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

from PIL import Image, ImageDraw, ImageFont

from . import keychain

APP_NAME = "书赫日报助手"
BUNDLE_ID = "com.shuhe.riji"
DEFAULT_OUTPUT_DIR = Path("/Users/shuhe/临时文件")
DEFAULT_INSTALL_DIR = Path.home() / "Applications"


def build(output_dir: str | Path | None = None, mode: str = "desktop", portable: bool = False) -> Path:
    root = Path(__file__).resolve().parents[1]
    out = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    app = out / f"{APP_NAME}.app"
    contents = app / "Contents"
    macos = contents / "MacOS"
    resources = contents / "Resources"

    if app.exists():
        shutil.rmtree(app)
    macos.mkdir(parents=True, exist_ok=True)
    resources.mkdir(parents=True, exist_ok=True)

    launcher = macos / "shuhe-riji"
    if portable:
        _copy_portable_payload(root, resources)
    launcher.write_text(_launcher_script(root, mode, portable=portable), encoding="utf-8")
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    icon_path = resources / "AppIcon.icns"
    _write_icon(icon_path)

    info = {
        "CFBundleDevelopmentRegion": "zh_CN",
        "CFBundleDisplayName": APP_NAME,
        "CFBundleExecutable": launcher.name,
        "CFBundleIconFile": icon_path.name,
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": APP_NAME,
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        "LSMinimumSystemVersion": "11.0",
        "LSUIElement": mode == "menubar",
        "NSHighResolutionCapable": True,
        "ShuheRijiPortable": portable,
    }
    (contents / "Info.plist").write_bytes(plistlib.dumps(info, sort_keys=False))
    return app


def install_app(
    source: str | Path | None = None,
    target_dir: str | Path | None = None,
    mode: str = "menubar",
    portable: bool = False,
    replace: bool = True,
) -> Path:
    app = Path(source) if source else build(mode=mode, portable=portable)
    if not app.exists() or app.suffix != ".app":
        raise FileNotFoundError(f"找不到可安装的 .app：{app}")

    destination_dir = Path(target_dir).expanduser() if target_dir else DEFAULT_INSTALL_DIR
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / app.name

    if destination.exists():
        if not replace:
            raise FileExistsError(f"目标已存在：{destination}")
        shutil.rmtree(destination)
    shutil.copytree(app, destination, symlinks=True)
    return destination


def write_env_template(
    path: str | Path | None = None,
    *,
    api_key: str | None = None,
    base_url: str = "http://localhost:55021/v1",
    model: str = "gpt-5.5",
    provider: str = "openai",
    overwrite: bool = False,
) -> Path:
    target = Path(path) if path else Path.home() / ".xiaohei-riji" / "env.sh"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        return target
    key_saved_to_keychain = keychain.set_password(api_key or "")
    key_note = (
        "# API key 已保存到 macOS 钥匙串。"
        if key_saved_to_keychain
        else "# API key 会优先从 macOS 钥匙串读取；非 macOS 可取消下一行注释手动填写。"
    )
    target.write_text(
        dedent(
            f"""\
            # 书赫日报助手本地环境变量
            # Finder 双击 .app 或开机自启时会读取这个文件。
            export RIJI_LLM_PROVIDER={_shell_quote(provider)}
            export RIJI_OPENAI_BASE_URL={_shell_quote(base_url)}
            export RIJI_OPENAI_MODEL={_shell_quote(model)}
            {key_note}
            # export RIJI_OPENAI_API_KEY=...
            """
        ),
        encoding="utf-8",
    )
    target.chmod(0o600)
    return target


def _shell_quote(value: str) -> str:
    return "'" + str(value).replace("'", "'\"'\"'") + "'"


def _launcher_script(root: Path, mode: str, portable: bool = False) -> str:
    python = Path(sys.executable)
    commands = {
        "desktop": "desktop",
        "menubar": "menubar",
        "panel": "panel --no-open",
    }
    command = commands.get(mode, "desktop")
    if portable:
        return dedent(
            f"""\
            #!/bin/zsh
            set -e
            APP_ROOT="${{0:A:h:h}}"
            RESOURCES="$APP_ROOT/Resources"
            export RIJI_LLM_PROVIDER="${{RIJI_LLM_PROVIDER:-openai}}"
            export RIJI_OPENAI_BASE_URL="${{RIJI_OPENAI_BASE_URL:-http://localhost:55021/v1}}"
            export RIJI_OPENAI_MODEL="${{RIJI_OPENAI_MODEL:-gpt-5.5}}"
            if [ -f "$HOME/.xiaohei-riji/env.sh" ]; then
              source "$HOME/.xiaohei-riji/env.sh"
            fi
            if [ -z "$RIJI_OPENAI_API_KEY" ] && command -v security >/dev/null 2>&1; then
              RIJI_KEYCHAIN_KEY="$(security find-generic-password -s "书赫日报助手" -a "RIJI_OPENAI_API_KEY" -w 2>/dev/null || true)"
              if [ -n "$RIJI_KEYCHAIN_KEY" ]; then
                export RIJI_OPENAI_API_KEY="$RIJI_KEYCHAIN_KEY"
              fi
              unset RIJI_KEYCHAIN_KEY
            fi
            export PYTHONPATH="$RESOURCES/app:$RESOURCES/site-packages${{PYTHONPATH:+:$PYTHONPATH}}"
            cd "$RESOURCES/app"
            if [ -x "$RESOURCES/venv/bin/python" ]; then
              exec "$RESOURCES/venv/bin/python" -m riji {command}
            fi
            exec /usr/bin/python3 -m riji {command}
            """
        )
    return dedent(
        f"""\
        #!/bin/zsh
        set -e
        export RIJI_LLM_PROVIDER="${{RIJI_LLM_PROVIDER:-openai}}"
        export RIJI_OPENAI_BASE_URL="${{RIJI_OPENAI_BASE_URL:-http://localhost:55021/v1}}"
        export RIJI_OPENAI_MODEL="${{RIJI_OPENAI_MODEL:-gpt-5.5}}"
        if [ -f "$HOME/.xiaohei-riji/env.sh" ]; then
          source "$HOME/.xiaohei-riji/env.sh"
        fi
        if [ -z "$RIJI_OPENAI_API_KEY" ] && command -v security >/dev/null 2>&1; then
          RIJI_KEYCHAIN_KEY="$(security find-generic-password -s "书赫日报助手" -a "RIJI_OPENAI_API_KEY" -w 2>/dev/null || true)"
          if [ -n "$RIJI_KEYCHAIN_KEY" ]; then
            export RIJI_OPENAI_API_KEY="$RIJI_KEYCHAIN_KEY"
          fi
          unset RIJI_KEYCHAIN_KEY
        fi
        cd "{root}"
        exec "{python}" -m riji {command}
        """
    )


def _copy_portable_payload(root: Path, resources: Path) -> None:
    app_payload = resources / "app"
    site_packages = resources / "site-packages"
    venv_payload = resources / "venv"
    for path in [app_payload, site_packages, venv_payload]:
        if path.exists():
            shutil.rmtree(path)
    app_payload.mkdir(parents=True, exist_ok=True)
    shutil.copytree(root / "riji", app_payload / "riji", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for filename in ["requirements.txt", "README.md"]:
        source = root / filename
        if source.exists():
            shutil.copy2(source, app_payload / filename)

    source_site = _current_site_packages()
    if source_site and source_site.exists():
        shutil.copytree(
            source_site,
            site_packages,
            symlinks=True,
            ignore=shutil.ignore_patterns(
                "__pycache__",
                "*.pyc",
                "pip*",
                "setuptools*",
                "wheel*",
                "*.dist-info/RECORD",
            ),
        )
    source_venv = root / ".venv"
    if source_venv.exists():
        shutil.copytree(
            source_venv,
            venv_payload,
            symlinks=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "pip*", "setuptools*", "wheel*"),
        )


def _current_site_packages() -> Path | None:
    candidates = [Path(item) for item in sys.path if item.endswith("site-packages")]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _write_icon(output: Path) -> None:
    if shutil.which("iconutil") is None:
        _write_png_icon(output.with_suffix(".png"), 1024)
        return
    iconset = output.parent / "AppIcon.iconset"
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir(parents=True, exist_ok=True)
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    for size in sizes:
        _write_png_icon(iconset / f"icon_{size}x{size}.png", size)
    for size in [16, 32, 128, 256, 512]:
        _write_png_icon(iconset / f"icon_{size}x{size}@2x.png", size * 2)
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(output)], check=True)
    shutil.rmtree(iconset)


def _write_png_icon(path: Path, size: int) -> None:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    radius = max(4, size // 5)
    draw.rounded_rectangle(
        [0, 0, size - 1, size - 1],
        radius=radius,
        fill=(17, 26, 24, 255),
    )
    inset = max(2, size // 12)
    draw.rounded_rectangle(
        [inset, inset, size - inset - 1, size - inset - 1],
        radius=max(3, radius - inset),
        outline=(15, 118, 110, 255),
        width=max(1, size // 32),
    )
    font = _font(size)
    text = "书"
    bbox = draw.textbbox((0, 0), text, font=font)
    x = (size - (bbox[2] - bbox[0])) / 2 - bbox[0]
    y = (size - (bbox[3] - bbox[1])) / 2 - bbox[1] - size * 0.02
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
    image.save(path)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, int(size * 0.48), index=0)
        except OSError:
            continue
    return ImageFont.load_default()
