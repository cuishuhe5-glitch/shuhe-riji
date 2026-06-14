"""macOS Keychain helpers for storing local model credentials."""

from __future__ import annotations

import platform
import subprocess

SERVICE = "书赫日报助手"
OPENAI_ACCOUNT = "RIJI_OPENAI_API_KEY"


def available() -> bool:
    return platform.system() == "Darwin"


def get_password(account: str = OPENAI_ACCOUNT) -> str:
    if not available():
        return ""
    result = subprocess.run(
        ["security", "find-generic-password", "-s", SERVICE, "-a", account, "-w"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def set_password(password: str, account: str = OPENAI_ACCOUNT) -> bool:
    if not available() or not password:
        return False
    subprocess.run(
        ["security", "delete-generic-password", "-s", SERVICE, "-a", account],
        capture_output=True,
        text=True,
    )
    result = subprocess.run(
        [
            "security",
            "add-generic-password",
            "-U",
            "-s",
            SERVICE,
            "-a",
            account,
            "-w",
            password,
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0
