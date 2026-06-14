"""Cross-platform autostart helpers."""

from __future__ import annotations

import os
import platform
import plistlib
import subprocess
import sys
from pathlib import Path
from typing import Any

LABEL = "com.shuhe.riji"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
WINDOWS_STARTUP = (
    Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs"
    / "Startup"
)
WINDOWS_CMD = WINDOWS_STARTUP / "书赫日报助手.cmd"


def install(host: str = "127.0.0.1", port: int = 8765) -> Path:
    if platform.system() == "Windows":
        return _install_windows(host, port)
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    plist = _plist(host, port)
    PLIST_PATH.write_bytes(plistlib.dumps(plist, sort_keys=False))
    _launchctl("bootout", f"gui/{os.getuid()}", str(PLIST_PATH), check=False)
    _launchctl("bootstrap", f"gui/{os.getuid()}", str(PLIST_PATH))
    _launchctl("enable", f"gui/{os.getuid()}/{LABEL}")
    return PLIST_PATH


def uninstall() -> Path:
    if platform.system() == "Windows":
        try:
            WINDOWS_CMD.unlink()
        except FileNotFoundError:
            pass
        return WINDOWS_CMD
    _launchctl("bootout", f"gui/{os.getuid()}", str(PLIST_PATH), check=False)
    try:
        PLIST_PATH.unlink()
    except FileNotFoundError:
        pass
    return PLIST_PATH


def status() -> dict[str, Any]:
    if platform.system() == "Windows":
        return {
            "label": LABEL,
            "plist": str(WINDOWS_CMD),
            "installed": WINDOWS_CMD.exists(),
            "loaded": False,
            "launchctl": "Windows 启动文件夹方式；下次登录后自动启动。",
        }
    exists = PLIST_PATH.exists()
    result = _launchctl("print", f"gui/{os.getuid()}/{LABEL}", check=False)
    return {
        "label": LABEL,
        "plist": str(PLIST_PATH),
        "installed": exists,
        "loaded": result.returncode == 0,
        "launchctl": result.stdout.strip() or result.stderr.strip(),
    }


def _plist(host: str, port: int) -> dict[str, Any]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key.startswith("RIJI_") or key in {"OPENAI_BASE_URL", "OPENAI_API_KEY", "OLLAMA_HOST"}
    }
    env.setdefault("PATH", os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"))
    log_dir = Path.home() / ".xiaohei-riji" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return {
        "Label": LABEL,
        "ProgramArguments": [
            sys.executable,
            "-m",
            "riji",
            "menubar",
            "--host",
            host,
            "--port",
            str(port),
        ],
        "WorkingDirectory": str(Path.cwd()),
        "EnvironmentVariables": env,
        "RunAtLoad": True,
        "KeepAlive": False,
        "StandardOutPath": str(log_dir / "menubar.log"),
        "StandardErrorPath": str(log_dir / "menubar.error.log"),
    }


def _launchctl(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["launchctl", *args],
        check=check,
        capture_output=True,
        text=True,
    )


def _install_windows(host: str, port: int) -> Path:
    WINDOWS_STARTUP.mkdir(parents=True, exist_ok=True)
    log_dir = Path.home() / ".xiaohei-riji" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    script = f"""@echo off
set RIJI_LLM_PROVIDER=%RIJI_LLM_PROVIDER%
set RIJI_OPENAI_BASE_URL=%RIJI_OPENAI_BASE_URL%
set RIJI_OPENAI_MODEL=%RIJI_OPENAI_MODEL%
cd /d "{Path.cwd()}"
start "书赫日报助手" /min "{sys.executable}" -m riji panel --host {host} --port {port} --no-open >> "{log_dir / 'panel.log'}" 2>> "{log_dir / 'panel.error.log'}"
"""
    WINDOWS_CMD.write_text(script, encoding="utf-8")
    return WINDOWS_CMD
