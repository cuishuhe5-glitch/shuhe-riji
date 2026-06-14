"""Foreground app/window helpers.

On macOS this uses System Events. If Accessibility permission is not granted,
callers get an empty result and screenshot recognition still works.
"""

from __future__ import annotations

import platform
import subprocess
import ctypes
from ctypes import wintypes
from dataclasses import dataclass


@dataclass(frozen=True)
class WindowInfo:
    app: str | None = None
    title: str | None = None


def frontmost() -> WindowInfo:
    system = platform.system()
    if system == "Windows":
        return _frontmost_windows()
    if system != "Darwin":
        return WindowInfo()
    script = """
    tell application "System Events"
      set frontApp to first application process whose frontmost is true
      set appName to name of frontApp
      try
        set windowTitle to name of front window of frontApp
      on error
        set windowTitle to ""
      end try
      return appName & linefeed & windowTitle
    end tell
    """
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return WindowInfo()
    lines = result.stdout.splitlines()
    app = lines[0].strip() if lines else ""
    title = lines[1].strip() if len(lines) > 1 else ""
    return WindowInfo(app or None, title or None)


def _frontmost_windows() -> WindowInfo:
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return WindowInfo()
        length = user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        app = _windows_process_name(int(pid.value))
        return WindowInfo(app or None, buffer.value.strip() or None)
    except Exception:
        return WindowInfo()


def _windows_process_name(pid: int) -> str:
    try:
        kernel32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi
        process = kernel32.OpenProcess(0x0400 | 0x0010, False, pid)
        if not process:
            return ""
        try:
            buffer = ctypes.create_unicode_buffer(260)
            if psapi.GetModuleBaseNameW(process, None, buffer, len(buffer)):
                return buffer.value
        finally:
            kernel32.CloseHandle(process)
    except Exception:
        return ""
    return ""
