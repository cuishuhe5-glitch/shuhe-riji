"""macOS permission checks and settings shortcuts."""

from __future__ import annotations

import platform
import subprocess
from typing import Any

import mss

from . import window

SCREEN_RECORDING_URL = "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"
ACCESSIBILITY_URL = "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"


def status() -> dict[str, Any]:
    return {
        "platform": platform.system(),
        "screen_recording": _screen_recording_status(),
        "accessibility": _accessibility_status(),
        "screen_recording_url": SCREEN_RECORDING_URL,
        "accessibility_url": ACCESSIBILITY_URL,
    }


def open_settings(kind: str) -> str:
    url = ACCESSIBILITY_URL if kind == "accessibility" else SCREEN_RECORDING_URL
    subprocess.run(["open", url], check=False)
    return url


def _screen_recording_status() -> dict[str, str]:
    if platform.system() != "Darwin":
        return {"state": "not_required", "message": "当前平台不需要 macOS 屏幕录制权限"}
    try:
        with mss.mss() as sct:
            mon = sct.monitors[1]
            raw = sct.grab(mon)
        if raw.width > 1 and raw.height > 1:
            return {"state": "granted", "message": "屏幕录制权限可用"}
    except Exception as exc:
        return {"state": "missing", "message": f"需要开启屏幕录制权限：{exc}"}
    return {"state": "unknown", "message": "无法确认屏幕录制权限"}


def _accessibility_status() -> dict[str, str]:
    if platform.system() != "Darwin":
        return {"state": "not_required", "message": "当前平台不需要 macOS 辅助功能权限"}
    info = window.frontmost()
    if info.app:
        return {"state": "granted", "message": f"辅助功能权限可用，当前应用：{info.app}"}
    return {"state": "unknown", "message": "无法读取前台应用；如窗口标题为空，请开启辅助功能权限"}
