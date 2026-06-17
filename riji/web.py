"""Local web dashboard for Shuhe Riji."""

from __future__ import annotations

import json
import mimetypes
import os
import platform
import plistlib
import re
import shutil
import shlex
import subprocess
import tempfile
import threading
import webbrowser
import csv
import zipfile
from collections import Counter
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import requests

from . import __version__, app_icons, autostart, capture, config, db, keychain, llm, permissions, recognize, report, settings, storage, timeline, window

STATIC_DIR = Path(__file__).with_name("static")
WORK_CATEGORIES = {
    "编码开发",
    "会议沟通",
    "文档写作",
    "阅读学习",
    "邮件即时通讯",
    "设计",
    "数据分析",
    "网页浏览",
}
PROJECT_CONTEXT_MAX_FILES = 12
PROJECT_CONTEXT_MAX_CHARS = 36000
PROJECT_CONTEXT_FILE_CHARS = 2400
PROJECT_CONTEXT_EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".next",
    "dist",
    "build",
    "DerivedData",
}
PROJECT_CONTEXT_ALLOWED_SUFFIXES = {
    ".md",
    ".txt",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".css",
    ".html",
    ".sql",
}
PROJECT_CONTEXT_PRIORITY_NAMES = {
    "readme.md",
    "agents.md",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "setup.py",
    "vite.config.js",
    "vite.config.ts",
}
REQUEST_LOGS: list[dict[str, Any]] = []
REQUEST_LOGS_LOCK = threading.Lock()
REQUEST_LOG_LIMIT = 200
UPDATE_STATE_LOCK = threading.Lock()
UPDATE_STATE: dict[str, Any] = {
    "running": False,
    "ok": False,
    "error": "",
    "phase": "idle",
    "percent": 0,
    "received": 0,
    "total": 0,
    "message": "",
    "filename": "",
    "version": "",
    "installing": False,
}
PROJECT_CONTEXT_SECRET_HINTS = {
    ".env",
    "secret",
    "token",
    "password",
    "apikey",
    "api_key",
    "keychain",
    "credential",
    "private",
}
RELEASE_INFO = {
    "version": f"v{__version__}",
    "url": f"https://github.com/cuishuhe5-glitch/shuhe-riji/releases/tag/v{__version__}",
    "assets": [
        {
            "name": "macOS 独立版",
            "filename": "shuhe-riji-macos-app.zip",
            "url": f"https://github.com/cuishuhe5-glitch/shuhe-riji/releases/download/v{__version__}/shuhe-riji-macos-app.zip",
            "sha256": "",
        },
        {
            "name": "macOS DMG",
            "filename": "shuhe-riji-macos.dmg",
            "url": f"https://github.com/cuishuhe5-glitch/shuhe-riji/releases/download/v{__version__}/shuhe-riji-macos.dmg",
            "sha256": "",
        },
        {
            "name": "Windows 便携版",
            "filename": "shuhe-riji-windows-portable.zip",
            "url": f"https://github.com/cuishuhe5-glitch/shuhe-riji/releases/download/v{__version__}/shuhe-riji-windows-portable.zip",
            "sha256": "",
        },
        {
            "name": "校验文件",
            "filename": "SHA256SUMS",
            "url": f"https://github.com/cuishuhe5-glitch/shuhe-riji/releases/download/v{__version__}/SHA256SUMS",
            "sha256": "",
        },
    ],
}
RELEASE_REPO = "cuishuhe5-glitch/shuhe-riji"


def _version_parts(version: str | None) -> tuple[int, ...]:
    if not version:
        return ()
    return tuple(int(part) for part in re.findall(r"\d+", version))


def _is_newer_version(latest: str | None, current: str | None) -> bool:
    latest_parts = _version_parts(latest)
    current_parts = _version_parts(current)
    return bool(latest_parts and current_parts and latest_parts > current_parts)


def _release_check() -> dict[str, Any]:
    current_version = RELEASE_INFO["version"]
    checked_at = datetime.now().isoformat(timespec="seconds")
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ShuheRiji/0.1",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    base = {
        "ok": False,
        "current_version": current_version,
        "current_url": RELEASE_INFO["url"],
        "latest_version": None,
        "latest_url": None,
        "body": "",
        "update_available": False,
        "checked_at": checked_at,
        "assets": [],
    }
    def fallback_latest(message: str) -> dict[str, Any]:
        try:
            latest_resp = requests.get(
                f"https://github.com/{RELEASE_REPO}/releases/latest",
                headers={"User-Agent": "ShuheRiji/0.1"},
                timeout=8,
                allow_redirects=True,
            )
            latest_resp.raise_for_status()
            latest_url = latest_resp.url
            latest_version = latest_url.rstrip("/").split("/")[-1]
            if not latest_version.startswith("v"):
                return {**base, "message": message}
            filenames = [asset["filename"] for asset in RELEASE_INFO["assets"]]
            assets = [
                {
                    "name": filename,
                    "filename": filename,
                    "url": f"https://github.com/{RELEASE_REPO}/releases/download/{latest_version}/{filename}",
                    "size": 0,
                }
                for filename in filenames
            ]
            return {
                **base,
                "ok": True,
                "message": "检查完成",
                "latest_version": latest_version,
                "latest_url": latest_url,
                "update_available": _is_newer_version(latest_version, current_version),
                "assets": assets,
            }
        except requests.RequestException:
            return {**base, "message": message}

    try:
        response = requests.get(f"https://api.github.com/repos/{RELEASE_REPO}/releases/latest", headers=headers, timeout=8)
        if response.status_code == 404:
            return fallback_latest("没有权限读取 GitHub Release，或仓库仍是私有状态。")
        response.raise_for_status()
        payload = response.json()
    except requests.Timeout:
        return fallback_latest("连接 GitHub 超时，请稍后再试。")
    except requests.RequestException as exc:
        status = getattr(exc.response, "status_code", None)
        detail = f"GitHub 返回 {status}" if status else "无法连接 GitHub"
        return fallback_latest(f"{detail}，请稍后再试。")
    except ValueError:
        return {**base, "message": "GitHub 返回内容无法解析，请稍后再试。"}

    latest_version = payload.get("tag_name") or payload.get("name") or ""
    assets = [
        {
            "name": asset.get("label") or asset.get("name") or "下载",
            "filename": asset.get("name") or "",
            "url": asset.get("browser_download_url") or "",
            "size": asset.get("size") or 0,
        }
        for asset in payload.get("assets", [])
        if isinstance(asset, dict)
    ]
    return {
        **base,
        "ok": True,
        "message": "检查完成",
        "latest_version": latest_version,
        "latest_url": payload.get("html_url") or RELEASE_INFO["url"],
        "body": payload.get("body") or "",
        "update_available": _is_newer_version(latest_version, current_version),
        "assets": assets,
    }


def _preferred_release_asset(release: dict[str, Any]) -> dict[str, Any] | None:
    assets = release.get("assets") or []
    system = platform.system().lower()

    def matches(patterns: list[str]) -> dict[str, Any] | None:
        for pattern in patterns:
            for asset in assets:
                name = f"{asset.get('filename') or ''} {asset.get('name') or ''}".lower()
                if pattern in name:
                    return asset
        return None

    if system == "darwin":
        return matches(["macos-app", "shuhe-riji-macos-app.zip", "macos.dmg", ".dmg", "mac"])
    if system == "windows":
        return matches(["windows", "win"])
    return assets[0] if assets else None


def _safe_download_filename(asset: dict[str, Any], url: str) -> str:
    raw = str(asset.get("filename") or asset.get("name") or Path(urlparse(url).path).name or "shuhe-riji-update")
    filename = re.sub(r"[^A-Za-z0-9._ -]+", "-", raw).strip(" .-")
    return filename or "shuhe-riji-update"


def _validate_release_download_url(url: str) -> None:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path
    allowed_hosts = {"github.com", "objects.githubusercontent.com"}
    if host not in allowed_hosts or not parsed.scheme.startswith("http"):
        raise ValueError("下载地址不是可信的 GitHub Release 链接")
    if host == "github.com" and f"/{RELEASE_REPO}/releases/download/" not in path:
        raise ValueError("下载地址不是书赫日报助手的发布包")


def _open_downloaded_update(path: Path) -> None:
    try:
        if platform.system() == "Darwin":
            subprocess.Popen(["open", str(path)])
        elif platform.system() == "Windows":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            opener = shutil.which("xdg-open")
            if opener:
                subprocess.Popen([opener, str(path)])
    except Exception:
        return


def _install_macos_app_zip(path: Path, version: str | None) -> dict[str, Any]:
    install_root = Path(tempfile.mkdtemp(prefix="shuhe-riji-update-"))
    with zipfile.ZipFile(path) as archive:
        archive.extractall(install_root)
    app_candidates = [item for item in install_root.iterdir() if item.suffix == ".app" and item.is_dir()]
    if not app_candidates:
        raise RuntimeError("更新包里没有找到书赫日报助手.app")
    source_app = app_candidates[0]
    target_app = Path(_desktop_app_status()["app_path"]).expanduser()
    target_app.parent.mkdir(parents=True, exist_ok=True)
    script_path = install_root / "install-update.zsh"
    log_path = config.LOGS_DIR / "update-install.log"
    config.ensure_dirs()
    script_path.write_text(
        "\n".join(
            [
                "#!/bin/zsh",
                "set -e",
                f"echo \"$(date '+%Y-%m-%d %H:%M:%S') installing {version or ''}\" >> {shlex.quote(str(log_path))}",
                f"APP_SRC={shlex.quote(str(source_app))}",
                f"APP_DST={shlex.quote(str(target_app))}",
                f"APP_PID={os.getpid()}",
                "osascript -e 'tell application \"书赫日报助手\" to quit' >/dev/null 2>&1 || true",
                "for i in {1..80}; do",
                "  if ! kill -0 \"$APP_PID\" >/dev/null 2>&1; then break; fi",
                "  sleep 0.25",
                "done",
                "rm -rf \"$APP_DST\"",
                "ditto \"$APP_SRC\" \"$APP_DST\"",
                "xattr -dr com.apple.quarantine \"$APP_DST\" >/dev/null 2>&1 || true",
                "open \"$APP_DST\"",
                f"echo \"$(date '+%Y-%m-%d %H:%M:%S') installed\" >> {shlex.quote(str(log_path))}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script_path.chmod(0o755)
    subprocess.Popen(["/bin/zsh", str(script_path)], start_new_session=True)
    return {
        "installing": True,
        "path": str(target_app),
        "filename": target_app.name,
        "version": version,
        "message": "更新包已解压，正在自动安装并重启应用。",
    }


def _update_state(**patch: Any) -> dict[str, Any]:
    with UPDATE_STATE_LOCK:
        UPDATE_STATE.update(patch)
        return dict(UPDATE_STATE)


def _download_status() -> dict[str, Any]:
    with UPDATE_STATE_LOCK:
        return dict(UPDATE_STATE)


def _start_release_download() -> dict[str, Any]:
    with UPDATE_STATE_LOCK:
        if UPDATE_STATE.get("running"):
            return dict(UPDATE_STATE)
        UPDATE_STATE.update(
            {
                "running": True,
                "ok": False,
                "error": "",
                "phase": "checking",
                "percent": 0,
                "received": 0,
                "total": 0,
                "message": "正在检查更新包...",
                "filename": "",
                "version": "",
                "installing": False,
            }
        )
        snapshot = dict(UPDATE_STATE)

    thread = threading.Thread(target=_download_latest_release_worker, daemon=True)
    thread.start()
    return snapshot


def _download_latest_release_worker() -> None:
    try:
        result = _download_latest_release()
        result.update(
            {
                "running": False,
                "ok": True,
                "error": "",
                "phase": "done",
                "percent": 100,
                "message": result.get("message") or "更新包已准备好。",
            }
        )
        _update_state(**result)
    except Exception as exc:
        _update_state(running=False, ok=False, error=str(exc), phase="error", message=str(exc))


def _download_latest_release() -> dict[str, Any]:
    release = _release_check()
    if not release.get("ok"):
        raise RuntimeError(release.get("message") or "暂时无法检查更新")
    _update_state(phase="selecting", message="正在选择适合当前系统的安装包...", version=release.get("latest_version") or "")
    asset = _preferred_release_asset(release)
    url = str((asset or {}).get("url") or release.get("latest_url") or "").strip()
    if not asset or not url:
        raise RuntimeError("暂时没有可用下载地址")
    _validate_release_download_url(url)

    downloads = Path.home() / "Downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    filename = _safe_download_filename(asset, url)
    _update_state(phase="downloading", filename=filename, message=f"正在下载 {filename}...", percent=0, received=0, total=0)
    target = downloads / filename
    if target.exists():
        stem = target.stem
        suffix = target.suffix
        target = downloads / f"{stem}-{datetime.now().strftime('%Y%m%d-%H%M%S')}{suffix}"

    with requests.get(url, headers={"User-Agent": "ShuheRiji/0.1"}, stream=True, timeout=30, allow_redirects=True) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length") or 0)
        received = 0
        _update_state(total=total)
        with target.open("wb") as file:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if chunk:
                    file.write(chunk)
                    received += len(chunk)
                    percent = int(received * 100 / total) if total else 0
                    _update_state(received=received, total=total, percent=min(percent, 99 if total else 0))

    if platform.system() == "Darwin" and target.suffix.lower() == ".zip":
        _update_state(phase="installing", percent=100, message="下载完成，正在解压并准备覆盖安装...")
        install = _install_macos_app_zip(target, release.get("latest_version"))
        return {
            "ok": True,
            "downloaded": str(target),
            "url": url,
            **install,
        }

    _open_downloaded_update(target)
    return {
        "ok": True,
        "path": str(target),
        "filename": target.name,
        "version": release.get("latest_version"),
        "url": url,
        "opened": True,
    }


def _notifications_snapshot(day: str | None = None, runtime: dict[str, Any] | None = None) -> list[dict[str, str]]:
    runtime = runtime or settings.load()
    day = day or date.today().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%H:%M")
    notes: list[dict[str, str]] = []
    status = permissions.status()
    storage_info = storage.stats()
    health = _health()
    screen_ok = status.get("screen_recording", {}).get("state") == "granted"
    accessibility_ok = status.get("accessibility", {}).get("state") == "granted"
    if not screen_ok:
        notes.append({"level": "warn", "title": "屏幕录制权限未开启", "message": "无法读取屏幕内容时，时间线和日报会缺少素材。", "time": now})
    if not accessibility_ok:
        notes.append({"level": "warn", "title": "辅助功能权限未开启", "message": "无法稳定识别前台应用和窗口标题。", "time": now})
    if not health.get("model", {}).get("ready"):
        notes.append({"level": "warn", "title": "模型网关需要检查", "message": health.get("model", {}).get("message") or "生成报告前请先确认 Hermes/OpenAI-compatible 网关可用。", "time": now})
    if runtime.get("privacy_mode") is False or runtime.get("keep_shots"):
        notes.append({"level": "info", "title": "截图留存已开启", "message": "如果屏幕上有客户信息、聊天或密码，建议回到隐私模式。", "time": now})
    elif int(storage_info.get("shot_files") or 0) > 0:
        notes.append({"level": "info", "title": "有可清理截图", "message": f"当前本机还有 {storage_info.get('shot_files')} 个截图文件，可以在隐私保护里清理。", "time": now})
    if not RECORDER.running and not int(storage_info.get("activities") or 0):
        notes.append({"level": "info", "title": "还没有工作记录", "message": "可以先点一次“立即识别”，确认当前屏幕能进入时间线。", "time": now})
    if runtime.get("auto_report_enabled"):
        notes.append({"level": "good", "title": "自动日报已启用", "message": f"每天 {runtime.get('auto_report_time')} 会尝试生成日报。", "time": now})
    if db.activities_for_day(day):
        notes.append({"level": "good", "title": "今天已有日报素材", "message": f"{day} 已有记录，可以直接进入“生成报告”。", "time": now})
    return notes


class Recorder:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.last_message = "尚未开始记录"
        self.last_error: str | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        with self._lock:
            if self.running:
                return False
            health = _health()
            if not health.get("ok"):
                self.last_error = "；".join(health.get("blockers") or ["启动前检查未通过"])
                self.last_message = f"后台记录未启动：{self.last_error}"
                return False
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
            self.last_message = "正在后台记录"
            self.last_error = None
            return True

    def stop(self) -> bool:
        with self._lock:
            if not self.running:
                self.last_message = "已暂停记录"
                return False
            thread = self._thread
            self._stop.set()
            self.last_message = "正在暂停..."
        if thread is not None:
            thread.join(timeout=2)
        if not self.running:
            self.last_message = "已暂停记录"
        return True

    def snapshot(self) -> dict[str, Any]:
        runtime = settings.load()
        stopping = self._stop.is_set() and self.running
        return {
            "running": self.running,
            "stopping": stopping,
            "message": self.last_message,
            "last_error": self.last_error,
            "interval": runtime["capture_interval"],
            "idle_pause_after": runtime["idle_pause_after"],
            "provider": config.LLM_PROVIDER,
            "model": config.VISION_MODEL,
            "data_dir": str(config.DATA_DIR),
        }

    def capture_once(self) -> dict[str, Any]:
        now = datetime.now()
        runtime = settings.load()
        try:
            win = window.frontmost()
            ignored, reason = settings.should_ignore(win.app, win.title, runtime)
            if ignored:
                self.last_message = reason
                return {"ok": False, "skipped": True, "message": reason, **self.snapshot()}

            img = capture.grab(runtime["capture_scope"])
            shot_path = capture.save_shot(img, now, keep=runtime["keep_shots"])
            rec = recognize.recognize(capture.to_jpeg_bytes(img), categories=runtime["activity_categories"])
            app_name = win.app or rec["app"]
            row_id = db.add_activity(
                category=rec["category"],
                summary=rec["summary"],
                app=app_name,
                window_title=win.title,
                shot_path=shot_path,
                ts=now,
            )
            if runtime["keep_shots"]:
                storage.prune_old_shots(runtime["shot_retention_days"])
            app = f"{app_name} / " if app_name else ""
            self.last_message = f"{now:%H:%M} {app}{rec['category']}：{rec['summary']}"
            self.last_error = None
            row = db.activity_by_id(row_id)
            item = _row_to_dict(row) if row else None
            return {"ok": True, "skipped": False, "item": item, **self.snapshot()}
        except Exception as exc:
            self.last_error = str(exc)
            self.last_message = f"立即记录失败：{exc}"
            return {"ok": False, "skipped": False, "error": str(exc), **self.snapshot()}

    def _loop(self) -> None:
        prev = None
        idle_since: datetime | None = None
        while not self._stop.is_set():
            try:
                now = datetime.now()
                runtime = settings.load()
                win = window.frontmost()
                ignored, reason = settings.should_ignore(win.app, win.title, runtime)
                if ignored:
                    self.last_message = reason
                    self._stop.wait(runtime["capture_interval"])
                    continue

                img = capture.grab(runtime["capture_scope"])
                ratio = capture.diff_ratio(prev, img)
                prev = img

                if ratio < config.CHANGE_THRESHOLD:
                    idle_since = idle_since or now
                    idle_secs = (now - idle_since).total_seconds()
                    self.last_message = (
                        f"闲置中 {int(idle_secs)}s"
                        if idle_secs >= runtime["idle_pause_after"]
                        else f"变化很小 {ratio:.1%}，已跳过"
                    )
                    self._stop.wait(runtime["capture_interval"])
                    continue

                idle_since = None
                shot_path = capture.save_shot(img, now, keep=runtime["keep_shots"])
                rec = recognize.recognize(capture.to_jpeg_bytes(img), categories=runtime["activity_categories"])
                app_name = win.app or rec["app"]
                db.add_activity(
                    category=rec["category"],
                    summary=rec["summary"],
                    app=app_name,
                    window_title=win.title,
                    shot_path=shot_path,
                    ts=now,
                )
                if runtime["keep_shots"]:
                    storage.prune_old_shots(runtime["shot_retention_days"])
                app = f"{app_name} / " if app_name else ""
                self.last_message = f"{now:%H:%M} {app}{rec['category']}：{rec['summary']}"
                self.last_error = None
            except Exception as exc:  # Keep the dashboard recorder alive.
                self.last_error = str(exc)
                self.last_message = f"本轮记录失败：{exc}"
            self._stop.wait(settings.load()["capture_interval"])
        self.last_message = "已暂停记录"


RECORDER = Recorder()


class AutoReporter:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.last_message = "自动日报待命"
        self.last_error: str | None = None

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def snapshot(self) -> dict[str, Any]:
        runtime = settings.load()
        return {
            "enabled": bool(runtime["auto_report_enabled"]),
            "time": runtime["auto_report_time"],
            "style": report.normalize_style(runtime["auto_report_style"], runtime["custom_report_styles"]),
            "last_day": runtime["auto_report_last_day"],
            "message": self.last_message,
            "last_error": self.last_error,
            "running": self._thread is not None and self._thread.is_alive(),
        }

    def run_now(self, day: str | None = None) -> dict[str, Any]:
        runtime = settings.load()
        target_day = day or date.today().strftime("%Y-%m-%d")
        rows = db.activities_for_day(target_day)
        if not rows:
            self.last_message = f"{target_day} 暂无记录，未生成日报"
            self.last_error = None
            return {"ok": False, "skipped": True, "message": self.last_message, **self.snapshot()}
        normalized_style = report.normalize_style(runtime["auto_report_style"], runtime["custom_report_styles"])
        text = report.daily_report(
            target_day,
            style=normalized_style,
            custom_styles=runtime["custom_report_styles"],
        )
        report_id = db.add_report(day=target_day, kind="日报", style=normalized_style, body=text)
        exported = _export_report(report_id)
        settings.save({"auto_report_last_day": target_day})
        self.last_message = f"{target_day} 自动日报已生成并归档"
        self.last_error = None
        return {
            "ok": True,
            "skipped": False,
            "report_id": report_id,
            "export": exported,
            "reports": _reports_list(),
            **self.snapshot(),
        }

    def _loop(self) -> None:
        while not self._stop.wait(60):
            try:
                runtime = settings.load()
                if not runtime["auto_report_enabled"]:
                    self.last_message = "自动日报未启用"
                    continue
                now = datetime.now()
                today = now.strftime("%Y-%m-%d")
                if runtime["auto_report_last_day"] == today:
                    self.last_message = f"{today} 自动日报已完成"
                    continue
                if now.strftime("%H:%M") < runtime["auto_report_time"]:
                    self.last_message = f"等待 {runtime['auto_report_time']} 自动生成"
                    continue
                self.run_now(today)
            except Exception as exc:
                self.last_error = str(exc)
                self.last_message = f"自动日报失败：{exc}"


AUTO_REPORTER = AutoReporter()


def start_background_services() -> None:
    AUTO_REPORTER.start()
    if settings.load()["auto_record_enabled"]:
        RECORDER.start()


def _row_to_dict(row: db.sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "ts": row["ts"],
        "time": row["ts"][11:16],
        "day": row["day"],
        "category": row["category"],
        "summary": row["summary"],
        "app": row["app"] or "",
        "app_icon_url": app_icons.icon_url(row["app"] or ""),
        "window_title": row["window_title"] or "",
        "shot_path": row["shot_path"] or "",
        "shot_url": f"/shots/{row['id']}" if row["shot_path"] else "",
    }


def _summary(day: str, heatmap_from: str = "", heatmap_to: str = "") -> dict[str, Any]:
    rows = db.activities_for_day(day)
    items = [_row_to_dict(row) for row in rows]
    segments = timeline.build_segments(items)
    cats = Counter(item["category"] for item in items)
    apps = Counter(item["app"] or "未知应用" for item in items)
    total = len(items)
    categories = [
        {
            "name": name,
            "count": count,
            "percent": round(count / total * 100) if total else 0,
            "color": _category_color(name),
        }
        for name, count in cats.most_common()
    ]
    runtime = settings.load()
    if runtime["privacy_mode"]:
        storage.clear_shots()
    return {
        "day": day,
        "total": total,
        "categories": categories,
        "top_apps": [{"name": name, "count": count} for name, count in apps.most_common(6)],
        "app_usage": _app_usage(segments),
        "productivity": _productivity_summary(segments, set(runtime["work_categories"])),
        "trends": _trend_summary(day, work_categories=set(runtime["work_categories"])),
        "time_heatmap": _time_heatmap_range(heatmap_from, heatmap_to or day) if (heatmap_from or heatmap_to) else _time_heatmap(day, days=7),
        "day_note": _day_note(day),
        "items": items,
        "segments": segments,
        "recording": RECORDER.snapshot(),
        "auto_report": AUTO_REPORTER.snapshot(),
        "styles": list(report.available_styles(runtime["custom_report_styles"]).keys()),
        "style_descriptions": report.available_styles(runtime["custom_report_styles"]),
        "style_catalog": report.style_catalog(runtime["custom_report_styles"]),
        "activity_categories": runtime["activity_categories"],
        "work_categories": runtime["work_categories"],
        "displays": _displays_snapshot(runtime["capture_scope"]),
        "settings": {
            **runtime,
            "data_dir": str(config.DATA_DIR),
            "settings_path": str(settings.SETTINGS_PATH),
            "provider": "openai",
            "base_url": config.OPENAI_BASE_URL,
            "text_model": config.TEXT_MODEL,
            "vision_model": config.VISION_MODEL,
        },
        "permissions": permissions.status(),
        "storage": storage.stats(),
        "model_config": _model_config(),
        "autostart": _autostart_status(),
        "reports": _reports_list(),
        "chat": _chat_messages(day),
        "days": _activity_days(),
        "health": _health(),
        "desktop_app": _desktop_app_status(),
        "project_context": _project_context_status(runtime),
        "release": RELEASE_INFO,
        "notifications": _notifications_snapshot(day, runtime=runtime),
    }


def _agent_docs() -> str:
    return f"""# 书赫日报助手本地 API

【服务信息】
本地 HTTP 服务地址：`http://127.0.0.1:8765`

【强制规则 — 必须遵守】

1. 每次处理用户请求前，你必须先调用 `GET http://127.0.0.1:8765/` 获取最新 API 文档。
   该接口返回的是一份 Markdown 格式的文档，其中详细说明了当前所有可用接口的路径、方法、参数、请求示例和响应示例。
   绝对不可以依赖记忆中的固定 API 列表，必须以实时拉取的文档为准。

2. 读取 Markdown 文档后，解析出其中的接口列表、参数定义、请求示例和响应结构，再动态选择接口并构造请求。

3. 所有业务接口返回 JSON 格式；具体字段以当前文档和实际响应为准。

【已知能力范围】（仅供参考，实际以 `GET /` 返回的 Markdown 文档为准）

该服务目前通常暴露以下类型的数据查询能力：

- 工作时间线查询：支持按日期和关键词查询工作记录。
- 工作报告查询：支持读取历史报告列表、单份报告正文，也支持按模板生成日报/周报/月报。
- 时段热力图查询：支持通过每日摘要读取 24 小时时段热力数据。
- 应用使用时长查询：支持按日/周/月/自定义范围查询各应用使用时长。

【接口列表】

### GET /api/summary?date=YYYY-MM-DD

获取某天的工作概览、时间线、分类分布、时段热力图、应用使用、报告模板和历史报告。

请求示例：

```http
GET /api/summary?date=2026-06-15
```

### GET /api/search?q=关键词&from=YYYY-MM-DD&to=YYYY-MM-DD&category=分类

搜索活动记录。参数均可选，`q` 支持活动摘要、应用名和窗口标题。

请求示例：

```http
GET /api/search?from=2026-06-15&to=2026-06-15&q=日报
```

### GET /api/app-usage?date=YYYY-MM-DD&period=day|week|month|custom&from=YYYY-MM-DD&to=YYYY-MM-DD

读取应用使用时长分布。`period=custom` 时使用 `from` 和 `to`，其他周期会根据 `date` 自动计算范围。

请求示例：

```http
GET /api/app-usage?period=custom&from=2026-06-09&to=2026-06-15
```

### POST /api/report

生成日报、周报或月报。

请求 JSON：

```json
{{
  "date": "2026-06-15",
  "start_date": "2026-06-09",
  "end_date": "2026-06-15",
  "kind": "day",
  "style": "成果导向",
  "instruction": "写给老板看，突出产出和风险"
}}
```

`kind` 可取：`day`、`week`、`month`。

### GET /api/reports

读取历史报告列表。

请求示例：

```http
GET /api/reports
```

### GET /api/reports/{{id}}

读取单份报告正文。

### POST /api/activity

手动补记一条活动。

请求 JSON：

```json
{{
  "ts": "2026-06-15T18:30:00",
  "category": "文档写作",
  "summary": "整理日报助手优化清单",
  "app": "Codex",
  "window_title": "书赫日报助手"
}}
```

【请你执行】

请基于以上信息，自动完成以下接入任务：

1. 请求 `GET http://127.0.0.1:8765/` 拉取最新 Markdown 格式 API 文档。
2. 仔细阅读文档，解析接口列表、参数定义、请求示例和响应结构。
3. 为用户创建一个名为「书赫日报助手数据查询」的 skill / tool。
4. 该 skill 需支持用户通过自然语言查询以下内容：
   - 某段时间的工作时间线
   - 某段时间的工作报告
   - 某段时间的时段热力图
   - 某段时间的应用使用时长统计

实现注意：

- 日期参数统一使用 `YYYY-MM-DD` 格式。
- 当用户未指定日期时，默认查询今天的数据。
- 本地查询不做分页，直接返回当前接口可用数据，无需处理翻页逻辑。

【响应说明】

- 成功响应为 JSON。
- 生成报告返回 `text`、`report_id` 和最新 `reports`。
- 摘要接口返回 `items`、`segments`、`style_catalog`、`health`、`settings` 等字段。

【当前版本】

- 应用：书赫日报助手
- Release：{RELEASE_INFO["version"]}
- 数据目录：{config.DATA_DIR}
"""


def _should_serve_agent_docs_at_root(query: dict[str, list[str]], accept: str) -> bool:
    root_mode = (query.get("format", [""])[0] or query.get("view", [""])[0]).lower()
    if root_mode in {"agent", "docs", "markdown"}:
        return True
    normalized_accept = accept.lower()
    if "text/markdown" in normalized_accept:
        return True
    return "text/html" not in normalized_accept


def _day_note(day: str) -> dict[str, str]:
    row = db.day_note(day)
    return {
        "day": day,
        "note": row["note"] if row else "",
        "updated_at": row["updated_at"] if row else "",
    }


def _displays_snapshot(selected_scope: str) -> dict[str, Any]:
    try:
        monitors = capture.displays()
    except Exception as exc:
        return {"ok": False, "error": str(exc), "items": [], "selected": selected_scope}
    scopes = {str(item["scope"]) for item in monitors}
    selected = selected_scope if selected_scope in scopes else "primary"
    return {"ok": True, "error": "", "items": monitors, "selected": selected}


def _chat_messages(day: str) -> list[dict[str, Any]]:
    return [
        {
            "id": row["id"],
            "created_at": row["created_at"],
            "day": row["day"],
            "scope": row["scope"],
            "question": row["question"],
            "answer": row["answer"],
        }
        for row in db.chat_messages(day)
    ]


def _chat_scope(day: str, scope: str) -> tuple[str, str, list[db.sqlite3.Row]]:
    end = datetime.strptime(day, "%Y-%m-%d").date()
    if scope == "week":
        start = end - timedelta(days=6)
        label = f"{start:%Y-%m-%d} ~ {end:%Y-%m-%d}"
        return start.strftime("%Y-%m-%d"), label, db.activities_between(start.strftime("%Y-%m-%d"), day)
    if scope == "month":
        start = end - timedelta(days=29)
        label = f"{start:%Y-%m-%d} ~ {end:%Y-%m-%d}"
        return start.strftime("%Y-%m-%d"), label, db.activities_between(start.strftime("%Y-%m-%d"), day)
    return day, day, db.activities_for_day(day)


def _report_source_rows(day: str, kind: str) -> tuple[str, str, list[db.sqlite3.Row]]:
    end = datetime.strptime(day, "%Y-%m-%d").date()
    if kind == "week":
        start = end - timedelta(days=6)
        return start.strftime("%Y-%m-%d"), day, db.activities_between(start.strftime("%Y-%m-%d"), day)
    if kind == "month":
        start = end - timedelta(days=29)
        return start.strftime("%Y-%m-%d"), day, db.activities_between(start.strftime("%Y-%m-%d"), day)
    return day, day, db.activities_for_day(day)


def _normalize_report_range(day: str, kind: str, start_value: Any = None, end_value: Any = None) -> tuple[str, str]:
    def clean(value: Any, fallback: str) -> str:
        text = str(value or fallback).strip()
        try:
            datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            return fallback
        return text

    fallback_start, fallback_end, _rows = _report_source_rows(day, kind)
    start_day = clean(start_value, fallback_start)
    end_day = clean(end_value, fallback_end)
    if start_day > end_day:
        start_day, end_day = end_day, start_day
    return start_day, end_day


def _chat_context(rows: list[db.sqlite3.Row], label: str) -> str:
    if not rows:
        return ""
    lines = [f"统计周期：{label}", f"活动记录数：{len(rows)}", "", "活动明细："]
    for row in rows[-220:]:
        title = f"《{row['window_title']}》" if "window_title" in row.keys() and row["window_title"] else ""
        app = f"[{row['app']}{title}] " if row["app"] else (f"[{title}] " if title else "")
        lines.append(f"- {row['ts']} {app}{row['category']}：{row['summary']}")
    return "\n".join(lines)


def _project_context_status(runtime: dict[str, Any] | None = None) -> dict[str, Any]:
    runtime = runtime or settings.load()
    paths = []
    total_files = 0
    for raw in runtime.get("project_paths", []):
        path = Path(raw).expanduser()
        exists = path.exists() and path.is_dir()
        files = _project_candidate_files(path, limit=PROJECT_CONTEXT_MAX_FILES) if exists else []
        total_files += len(files)
        paths.append(
            {
                "path": str(path),
                "name": path.name or str(path),
                "exists": exists,
                "files": len(files),
            }
        )
    return {
        "enabled": any(item["exists"] for item in paths),
        "paths": paths,
        "files": total_files,
        "max_files": PROJECT_CONTEXT_MAX_FILES,
    }


def _project_file_context(runtime: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    runtime = runtime or settings.load()
    sections: list[str] = []
    used_files = 0
    used_chars = 0
    skipped_paths = 0
    for raw in runtime.get("project_paths", []):
        root = Path(raw).expanduser()
        if not root.exists() or not root.is_dir():
            skipped_paths += 1
            continue
        root_lines = [f"项目目录：{root}"]
        for path in _project_candidate_files(root, limit=PROJECT_CONTEXT_MAX_FILES - used_files):
            if used_files >= PROJECT_CONTEXT_MAX_FILES or used_chars >= PROJECT_CONTEXT_MAX_CHARS:
                break
            try:
                text = path.read_text(encoding="utf-8", errors="ignore").strip()
            except OSError:
                continue
            if not text:
                continue
            rel = path.relative_to(root)
            text = text[:PROJECT_CONTEXT_FILE_CHARS]
            block = f"\n--- {rel} ---\n{text}"
            if used_chars + len(block) > PROJECT_CONTEXT_MAX_CHARS:
                block = block[: max(0, PROJECT_CONTEXT_MAX_CHARS - used_chars)]
            root_lines.append(block)
            used_files += 1
            used_chars += len(block)
        if len(root_lines) > 1:
            sections.append("\n".join(root_lines))
        if used_files >= PROJECT_CONTEXT_MAX_FILES or used_chars >= PROJECT_CONTEXT_MAX_CHARS:
            break
    meta = {
        "enabled": bool(sections),
        "files": used_files,
        "chars": used_chars,
        "skipped_paths": skipped_paths,
    }
    if not sections:
        return "", meta
    return "\n\n".join(sections), meta


def _project_candidate_files(root: Path, limit: int = PROJECT_CONTEXT_MAX_FILES) -> list[Path]:
    if limit <= 0:
        return []
    candidates: list[tuple[int, float, Path]] = []
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            if len(candidates) >= 200:
                break
            dirnames[:] = [name for name in dirnames if name not in PROJECT_CONTEXT_EXCLUDED_DIRS]
            current = Path(dirpath)
            try:
                rel_dir = current.relative_to(root)
            except ValueError:
                continue
            if any(part in PROJECT_CONTEXT_EXCLUDED_DIRS for part in rel_dir.parts):
                continue
            for filename in filenames:
                if len(candidates) >= 200:
                    break
                path = current / filename
                if _project_file_skipped(path):
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    continue
                if stat.st_size > 180_000:
                    continue
                name = path.name.casefold()
                priority = 0 if name in PROJECT_CONTEXT_PRIORITY_NAMES else 1
                candidates.append((priority, -stat.st_mtime, path))
    except OSError:
        return []
    return [item[2] for item in sorted(candidates)[:limit]]


def _project_file_skipped(path: Path) -> bool:
    name = path.name.casefold()
    if any(hint in name for hint in PROJECT_CONTEXT_SECRET_HINTS):
        return True
    if path.suffix.casefold() not in PROJECT_CONTEXT_ALLOWED_SUFFIXES:
        return True
    return False


def _answer_chat(day: str, scope: str, question: str) -> dict[str, Any]:
    if scope not in {"day", "week", "month"}:
        scope = "day"
    question = question.strip()
    if not question:
        raise ValueError("问题不能为空")
    runtime = settings.load()
    _start_day, label, rows = _chat_scope(day, scope)
    context = _chat_context(rows, label)
    project_context, project_meta = _project_file_context(runtime)
    if not context and not project_context:
        answer = f"{label} 没有本地活动记录，也没有可用的项目上下文，暂时无法回答这个问题。"
    else:
        prompt = (
            "你是书赫日报助手，只能根据下面的本地电脑活动记录和用户显式配置的项目文件摘要回答问题。"
            "如果素材里没有依据，就明确说没有记录依据，不要编造。"
            "回答要具体、简洁，可以引用时间段、应用、分类、已记录事项和项目文件名。\n\n"
            f"=== 本地活动记录 ===\n{context or '无'}\n=== 活动记录结束 ===\n\n"
            f"=== 项目文件摘要 ===\n{project_context or '未配置或没有可读取的文本文件'}\n=== 项目文件摘要结束 ===\n\n"
            f"用户问题：{question}"
        )
        answer = llm.openai_chat_completion(
            [{"role": "user", "content": prompt}],
            config.TEXT_MODEL,
            timeout=120,
            temperature=0.2,
        )
        answer = answer or "模型没有返回内容。"
    chat_id = db.add_chat_message(day=day, scope=scope, question=question, answer=answer)
    return {
        "id": chat_id,
        "day": day,
        "scope": scope,
        "question": question,
        "answer": answer,
        "project_context": project_meta,
    }


def _app_usage(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    usage: dict[str, dict[str, Any]] = {}
    total_minutes = 0
    for seg in segments:
        app = seg.get("app") or "未知应用"
        minutes = max(1, int(seg.get("duration_minutes") or 1))
        total_minutes += minutes
        item = usage.setdefault(
            app,
            {
                "name": app,
                "minutes": 0,
                "count": 0,
                "categories": Counter(),
                "first_time": seg.get("start_time") or "",
                "last_time": seg.get("end_time") or "",
                "icon_url": app_icons.icon_url(app if app != "未知应用" else ""),
            },
        )
        item["minutes"] += minutes
        item["count"] += int(seg.get("count") or 1)
        item["categories"][seg.get("category") or "其他"] += minutes
        if seg.get("start_time") and (not item["first_time"] or seg["start_time"] < item["first_time"]):
            item["first_time"] = seg["start_time"]
        if seg.get("end_time") and seg["end_time"] > item["last_time"]:
            item["last_time"] = seg["end_time"]
    result = []
    for item in usage.values():
        categories = item.pop("categories")
        result.append(
            {
                **item,
                "label": _format_minutes(item["minutes"]),
                "percent": round(item["minutes"] / total_minutes * 100) if total_minutes else 0,
                "top_category": categories.most_common(1)[0][0] if categories else "其他",
            }
        )
    return sorted(result, key=lambda entry: (-entry["minutes"], entry["name"]))[:20]


def _app_usage_range(day: str, period: str, start_value: Any = None, end_value: Any = None) -> dict[str, Any]:
    try:
        end = datetime.strptime(day, "%Y-%m-%d").date()
    except ValueError:
        end = date.today()
    if period == "week":
        start = end - timedelta(days=6)
    elif period == "month":
        start = end - timedelta(days=29)
    elif period == "custom":
        try:
            start = datetime.strptime(str(start_value or day), "%Y-%m-%d").date()
            custom_end = datetime.strptime(str(end_value or day), "%Y-%m-%d").date()
        except ValueError:
            start = end
            custom_end = end
        if start > custom_end:
            start, custom_end = custom_end, start
        end = custom_end
    else:
        start = end
        period = "day"
    start_day = start.strftime("%Y-%m-%d")
    end_day = end.strftime("%Y-%m-%d")
    rows = db.activities_for_day(end_day) if start_day == end_day else db.activities_between(start_day, end_day)
    items = [_row_to_dict(row) for row in rows]
    segments = timeline.build_segments(items)
    days = max(1, (end - start).days + 1)
    return {
        "period": period,
        "start_day": start_day,
        "end_day": end_day,
        "days": days,
        "app_usage": _app_usage(segments),
    }


def _format_minutes(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} 分钟"
    hours, mins = divmod(minutes, 60)
    return f"{hours} 小时 {mins} 分钟" if mins else f"{hours} 小时"


def _productivity_summary(segments: list[dict[str, Any]], work_categories: set[str] | None = None) -> dict[str, Any]:
    work_categories = work_categories or WORK_CATEGORIES
    if not segments:
        return {
            "score": 0,
            "label": "暂无数据",
            "work_minutes": 0,
            "rest_minutes": 0,
            "work_percent": 0,
            "longest_focus_minutes": 0,
            "longest_focus_label": "暂无",
            "rest_segments": 0,
            "suggestion": "开始记录后会根据当天活动给出效率洞察。",
        }
    work_minutes = 0
    rest_minutes = 0
    rest_segments = 0
    longest_focus = 0
    current_focus = 0
    for seg in segments:
        minutes = max(1, int(seg.get("duration_minutes") or 1))
        is_work = (seg.get("category") or "") in work_categories
        if is_work:
            work_minutes += minutes
            current_focus += minutes
            longest_focus = max(longest_focus, current_focus)
        else:
            rest_minutes += minutes
            rest_segments += 1
            current_focus = 0
    total_minutes = work_minutes + rest_minutes
    work_percent = round(work_minutes / total_minutes * 100) if total_minutes else 0
    focus_bonus = min(20, round(longest_focus / 30 * 20))
    rest_penalty = min(12, max(0, rest_segments - 2) * 3)
    score = max(0, min(100, round(work_percent * 0.78 + focus_bonus - rest_penalty)))
    if score >= 80:
        label = "高效专注"
        suggestion = "今天的工作占比和连续工作段都不错，适合直接沉淀成日报成果。"
    elif score >= 60:
        label = "稳定推进"
        suggestion = "整体节奏稳定，可以在报告里补充关键产出和下一步动作。"
    elif score > 0:
        label = "节奏偏散"
        suggestion = "今天记录较分散，建议补一条今日备注，明确真正完成的产出。"
    else:
        label = "暂无数据"
        suggestion = "开始记录后会根据当天活动给出效率洞察。"
    return {
        "score": score,
        "label": label,
        "work_minutes": work_minutes,
        "rest_minutes": rest_minutes,
        "work_percent": work_percent,
        "longest_focus_minutes": longest_focus,
        "longest_focus_label": _format_minutes(longest_focus) if longest_focus else "暂无",
        "rest_segments": rest_segments,
        "suggestion": suggestion,
    }


def _trend_summary(end_day: str, days: int = 30, work_categories: set[str] | None = None) -> dict[str, Any]:
    work_categories = work_categories or WORK_CATEGORIES
    try:
        end = datetime.strptime(end_day, "%Y-%m-%d").date()
    except ValueError:
        end = date.today()
    start = end - timedelta(days=max(1, days) - 1)
    rows = db.activity_trends(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    by_day: dict[str, dict[str, Any]] = {
        (start + timedelta(days=offset)).strftime("%Y-%m-%d"): {
            "day": (start + timedelta(days=offset)).strftime("%Y-%m-%d"),
            "count": 0,
            "work_count": 0,
        }
        for offset in range(days)
    }
    categories: Counter[str] = Counter()
    apps: Counter[str] = Counter()
    for row in rows:
        count = int(row["count"] or 0)
        day = by_day.setdefault(row["day"], {"day": row["day"], "count": 0, "work_count": 0})
        category = row["category"] or "其他"
        app = row["app"] or "未知应用"
        day["count"] += count
        if category in work_categories:
            day["work_count"] += count
        categories[category] += count
        apps[app] += count

    series = list(by_day.values())
    total = sum(item["count"] for item in series)
    active_days = sum(1 for item in series if item["count"])
    max_count = max((item["count"] for item in series), default=0)
    work_total = sum(item["work_count"] for item in series)
    for item in series:
        item["percent"] = round(item["count"] / max_count * 100) if max_count else 0
        item["work_percent"] = round(item["work_count"] / item["count"] * 100) if item["count"] else 0
    return {
        "start_day": start.strftime("%Y-%m-%d"),
        "end_day": end.strftime("%Y-%m-%d"),
        "days": days,
        "total": total,
        "active_days": active_days,
        "average": round(total / active_days, 1) if active_days else 0,
        "work_percent": round(work_total / total * 100) if total else 0,
        "top_category": categories.most_common(1)[0][0] if categories else "",
        "top_app": apps.most_common(1)[0][0] if apps else "",
        "series": series,
    }


def _time_heatmap(end_day: str, days: int = 3) -> dict[str, Any]:
    try:
        end = datetime.strptime(end_day, "%Y-%m-%d").date()
    except ValueError:
        end = date.today()
    start = end - timedelta(days=max(1, days) - 1)
    return _time_heatmap_for_dates(start, end)


def _time_heatmap_range(start_day: str, end_day: str, max_days: int = 31) -> dict[str, Any]:
    try:
        end = datetime.strptime(end_day, "%Y-%m-%d").date()
    except ValueError:
        end = date.today()
    try:
        start = datetime.strptime(start_day, "%Y-%m-%d").date()
    except ValueError:
        start = end - timedelta(days=6)
    if start > end:
        start, end = end, start
    days = (end - start).days + 1
    if days > max_days:
        start = end - timedelta(days=max_days - 1)
    return _time_heatmap_for_dates(start, end)


def _time_heatmap_for_dates(start: date, end: date) -> dict[str, Any]:
    days = (end - start).days + 1
    rows = db.activities_between(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    by_day: dict[str, list[dict[str, Any]]] = {}
    for offset in range(days):
        day = (start + timedelta(days=offset)).strftime("%Y-%m-%d")
        by_day[day] = [{"hour": hour, "count": 0, "top_category": ""} for hour in range(24)]
    category_counts: dict[tuple[str, int], Counter[str]] = {}
    for row in rows:
        day = row["day"]
        if day not in by_day:
            continue
        try:
            hour = datetime.fromisoformat(row["ts"]).hour
        except ValueError:
            continue
        by_day[day][hour]["count"] += 1
        key = (day, hour)
        category_counts.setdefault(key, Counter())[row["category"] or "其他"] += 1
    max_count = 0
    result_days = []
    for day, hours in by_day.items():
        total = sum(item["count"] for item in hours)
        total_minutes = total
        max_count = max(max_count, *(item["count"] for item in hours))
        for item in hours:
            categories = category_counts.get((day, item["hour"]), Counter())
            item["top_category"] = categories.most_common(1)[0][0] if categories else ""
        result_days.append(
            {
                "day": day,
                "label": _relative_day_label(day, end.strftime("%Y-%m-%d")),
                "total": total,
                "total_minutes": total_minutes,
                "hours": hours,
            }
        )
    for day in result_days:
        for item in day["hours"]:
            item["level"] = min(5, round(item["count"] / max_count * 5)) if max_count else 0
    return {"start_day": start.strftime("%Y-%m-%d"), "end_day": end.strftime("%Y-%m-%d"), "max_count": max_count, "days": result_days}


def _relative_day_label(day: str, selected_day: str) -> str:
    current = datetime.strptime(day, "%Y-%m-%d").date()
    selected = datetime.strptime(selected_day, "%Y-%m-%d").date()
    delta = (selected - current).days
    if delta == 0:
        return "今天"
    if delta == 1:
        return "昨天"
    names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return names[current.weekday()]


def _health() -> dict[str, Any]:
    perms = permissions.status()
    data_writable = _is_writable(config.DATA_DIR)
    shots_writable = _is_writable(config.SHOTS_DIR)
    model_ready = bool(config.OPENAI_BASE_URL and config.OPENAI_API_KEY)
    blockers: list[str] = []
    if not config.OPENAI_BASE_URL:
        blockers.append("缺少 OpenAI-compatible base URL")
    if not config.OPENAI_API_KEY:
        blockers.append("缺少本地网关 key")
    if not data_writable:
        blockers.append("数据目录不可写")
    if perms["screen_recording"]["state"] == "missing":
        blockers.append("缺少屏幕录制权限")
    return {
        "ok": not blockers,
        "blockers": blockers,
        "model": {
            "provider": "openai",
            "base_url": config.OPENAI_BASE_URL,
            "model": config.VISION_MODEL,
            "api_key_present": bool(config.OPENAI_API_KEY),
            "ready": model_ready,
        },
        "storage": {
            "data_dir": str(config.DATA_DIR),
            "data_writable": data_writable,
            "shots_writable": shots_writable,
        },
        "permissions": {
            "screen_recording": perms["screen_recording"]["state"],
            "accessibility": perms["accessibility"]["state"],
        },
    }


def _test_model_connection() -> dict[str, Any]:
    started = datetime.now()
    if not config.OPENAI_BASE_URL:
        raise ValueError("缺少 OpenAI-compatible base URL")
    if not config.OPENAI_API_KEY:
        raise ValueError("缺少本地网关 key")
    resp = requests.get(
        f"{config.OPENAI_BASE_URL}/models",
        headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
        timeout=8,
    )
    resp.raise_for_status()
    payload = resp.json()
    models = payload.get("data") if isinstance(payload, dict) else []
    names = [
        str(item.get("id") or item.get("name") or "")
        for item in models
        if isinstance(item, dict)
    ]
    elapsed_ms = round((datetime.now() - started).total_seconds() * 1000)
    return {
        "provider": "openai",
        "base_url": config.OPENAI_BASE_URL,
        "model": config.VISION_MODEL,
        "ok": True,
        "elapsed_ms": elapsed_ms,
        "models_count": len(names),
        "model_found": config.VISION_MODEL in names if names else None,
        "sample_models": names[:8],
    }


def _model_config() -> dict[str, Any]:
    return {
        "provider": "openai",
        "base_url": config.OPENAI_BASE_URL,
        "model": config.TEXT_MODEL,
        "api_key_present": bool(config.OPENAI_API_KEY),
        "api_key_source": config.OPENAI_API_KEY_SOURCE,
        "keychain_available": keychain.available(),
    }


def _save_model_config(body: dict[str, Any]) -> dict[str, Any]:
    provider = str(body.get("provider") or "openai").strip().lower()
    if provider != "openai":
        raise ValueError("模型后端无效")
    base_url = str(body.get("base_url") or "").strip().rstrip("/")
    model = str(body.get("model") or "").strip()
    api_key = str(body.get("api_key") or "").strip()
    base_url = base_url or config.OPENAI_BASE_URL or "http://localhost:55021/v1"
    model = model or config.TEXT_MODEL or "gpt-5.5"
    api_key = api_key or config.OPENAI_API_KEY
    if not api_key:
        raise ValueError("OpenAI-compatible key 不能为空")

    config.ensure_dirs()
    env_path = config.DATA_DIR / "env.sh"
    lines = [
        "# 书赫日报助手本地环境变量",
        "# Finder 双击 .app 或开机自启时会读取这个文件。",
        f"export RIJI_LLM_PROVIDER={shlex.quote(provider)}",
    ]
    lines.extend(
        [
            f"export RIJI_OPENAI_BASE_URL={shlex.quote(base_url)}",
            f"export RIJI_OPENAI_MODEL={shlex.quote(model)}",
            "# API key 会优先保存到 macOS 钥匙串；非 macOS 可取消下一行注释手动填写。",
            "# export RIJI_OPENAI_API_KEY=...",
        ]
    )
    env_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    env_path.chmod(0o600)

    os.environ["RIJI_LLM_PROVIDER"] = provider
    config.LLM_PROVIDER = provider
    key_saved_to_keychain = keychain.set_password(api_key)
    os.environ["RIJI_OPENAI_BASE_URL"] = base_url
    os.environ["RIJI_OPENAI_MODEL"] = model
    os.environ["RIJI_OPENAI_API_KEY"] = api_key
    config.OPENAI_BASE_URL = base_url
    config.OPENAI_API_KEY = api_key
    config.OPENAI_API_KEY_SOURCE = "keychain" if key_saved_to_keychain else "environment"
    config.TEXT_MODEL = model
    config.VISION_MODEL = model
    return _model_config()


def _is_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _activity_days() -> list[dict[str, Any]]:
    with db.connect() as conn:
        report_rows = conn.execute(
            "SELECT day, COUNT(*) AS count, MAX(created_at) AS latest_created, "
            "(SELECT kind FROM reports r2 WHERE r2.day = reports.day ORDER BY created_at DESC LIMIT 1) AS latest_kind "
            "FROM reports GROUP BY day"
        ).fetchall()
    report_by_day = {
        row["day"]: {
            "count": row["count"],
            "latest_kind": row["latest_kind"] or "",
            "latest_created": row["latest_created"] or "",
        }
        for row in report_rows
    }
    return [
        {
            "day": row["day"],
            "count": row["count"],
            "first_time": row["first_ts"][11:16] if row["first_ts"] else "",
            "last_time": row["last_ts"][11:16] if row["last_ts"] else "",
            "reports": report_by_day.get(row["day"], {"count": 0, "latest_kind": "", "latest_created": ""}),
        }
        for row in db.activity_days()
    ]


def _autostart_status() -> dict[str, Any]:
    info = autostart.status()
    launchctl = info.get("launchctl") or ""
    if len(launchctl) > 600:
        launchctl = launchctl[:600].rstrip() + "..."
    return {
        "label": info.get("label", autostart.LABEL),
        "plist": info.get("plist", str(autostart.PLIST_PATH)),
        "installed": bool(info.get("installed")),
        "loaded": bool(info.get("loaded")),
        "launchctl": launchctl,
    }


def _reports_list() -> list[dict[str, Any]]:
    return [
        {
            "id": row["id"],
            "created_at": row["created_at"],
            "day": row["day"],
            "kind": row["kind"],
            "style": row["style"],
            "title": row["title"],
            "preview": row["preview"] or "",
        }
        for row in db.reports()
    ]


def _export_report(report_id: int) -> dict[str, Any]:
    row = db.report_by_id(report_id)
    if not row:
        raise FileNotFoundError("报告不存在")
    config.ensure_dirs()
    name = _safe_filename(f"{row['day']}-{row['kind']}-{row['style']}-{row['id']}.md")
    path = config.REPORTS_DIR / name
    content = row["body"]
    if not content.startswith("#"):
        content = f"# {row['title']}\n\n{content}"
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    return {
        "id": row["id"],
        "path": str(path),
        "filename": path.name,
        "size": path.stat().st_size,
    }


def _export_all_report_markdowns() -> dict[str, Any]:
    config.ensure_dirs()
    rows = db.all_reports()
    exported: list[dict[str, Any]] = []
    for row in rows:
        name = _safe_filename(f"{row['day']}-{row['kind']}-{row['style']}-{row['id']}.md")
        path = config.REPORTS_DIR / name
        content = row["body"]
        if not content.startswith("#"):
            content = f"# {row['title']}\n\n{content}"
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
        exported.append(
            {
                "id": row["id"],
                "path": str(path),
                "filename": path.name,
                "size": path.stat().st_size,
            }
        )
    return {
        "count": len(exported),
        "dir": str(config.REPORTS_DIR),
        "files": exported,
    }


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "-", value).strip(". ")
    return cleaned or "report.md"


def _desktop_app_status() -> dict[str, Any]:
    app_path = Path.home() / "Applications" / "书赫日报助手.app"
    applications_dir = app_path.parent
    info_path = app_path / "Contents" / "Info.plist"
    info: dict[str, Any] = {}
    if info_path.exists():
        try:
            with info_path.open("rb") as file:
                loaded = plistlib.load(file)
            if isinstance(loaded, dict):
                info = loaded
        except Exception:
            info = {}
    modified = ""
    if app_path.exists():
        try:
            modified = datetime.fromtimestamp(app_path.stat().st_mtime).isoformat(timespec="seconds")
        except OSError:
            modified = ""
    lsui = info.get("LSUIElement")
    portable = bool(info.get("ShuheRijiPortable"))
    mode = "菜单栏常驻" if lsui else "桌面窗口"
    if portable:
        mode = f"{mode} · 独立版"
    return {
        "installed": app_path.exists(),
        "app_path": str(app_path),
        "applications_dir": str(applications_dir),
        "display_name": str(info.get("CFBundleDisplayName") or info.get("CFBundleName") or "书赫日报助手"),
        "bundle_id": str(info.get("CFBundleIdentifier") or "com.shuhe.riji"),
        "version": str(info.get("CFBundleShortVersionString") or info.get("CFBundleVersion") or ""),
        "mode": mode,
        "portable": portable,
        "modified": modified,
    }


def _open_local_path(kind: str) -> dict[str, str]:
    desktop_app = _desktop_app_status()
    app_path = Path(desktop_app["app_path"])
    targets = {
        "data": config.DATA_DIR,
        "reports": config.REPORTS_DIR,
        "shots": config.SHOTS_DIR,
        "logs": config.LOGS_DIR,
        "backups": config.BACKUPS_DIR,
        "exports": config.EXPORTS_DIR,
        "applications": Path(desktop_app["applications_dir"]),
        "app": app_path,
    }
    path = targets.get(kind)
    if path is None:
        raise ValueError("目录类型无效")
    if kind == "app" and not path.exists():
        raise ValueError("还没有安装书赫日报助手.app")
    config.ensure_dirs()
    _open_path(path)
    return {"kind": kind, "path": str(path)}


def _open_path(path: Path) -> None:
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["open", str(path)], check=False)
    elif system == "Windows":
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def _logs_snapshot() -> dict[str, Any]:
    config.ensure_dirs()
    files = []
    paths = sorted({*config.LOGS_DIR.glob("*.log"), *config.LOGS_DIR.glob("*.error.log")})
    for path in paths:
        try:
            stat = path.stat()
        except OSError:
            continue
        files.append(
            {
                "name": path.name,
                "path": str(path),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                "text": _tail_text(path),
            }
        )
    return {
        "dir": str(config.LOGS_DIR),
        "files": files,
    }


def _request_logs_snapshot(page: int = 1) -> dict[str, Any]:
    with REQUEST_LOGS_LOCK:
        items = list(reversed(REQUEST_LOGS))
    page_size = 20
    pages = max(1, (len(items) + page_size - 1) // page_size)
    page = min(max(1, int(page or 1)), pages)
    start = (page - 1) * page_size
    return {
        "total": len(items),
        "page": page,
        "page_size": page_size,
        "pages": pages,
        "items": items[start:start + page_size],
    }


def _clear_request_logs() -> dict[str, Any]:
    with REQUEST_LOGS_LOCK:
        count = len(REQUEST_LOGS)
        REQUEST_LOGS.clear()
    return {"cleared": count, "request_logs": _request_logs_snapshot()}


def _create_backup(include_shots: bool = True) -> dict[str, Any]:
    config.ensure_dirs()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = config.BACKUPS_DIR / f"书赫日报助手-backup-{stamp}.zip"
    storage_info = storage.stats()
    manifest = {
        "app": "书赫日报助手",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "data_dir": str(config.DATA_DIR),
        "include_shots": include_shots,
        "storage": storage_info,
        "notes": "备份包含本地数据库、设置、报告、日志，以及按选项包含截图文件；未额外导出本地网关密钥。",
    }
    with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        _zip_file_if_exists(zf, config.DB_PATH, "riji.db")
        _zip_file_if_exists(zf, settings.SETTINGS_PATH, "settings.json")
        _zip_tree(zf, config.REPORTS_DIR, "reports")
        _zip_tree(zf, config.LOGS_DIR, "logs")
        if include_shots:
            _zip_tree(zf, config.SHOTS_DIR, "shots")
    return {
        "path": str(backup_path),
        "filename": backup_path.name,
        "size": backup_path.stat().st_size,
        "size_label": _format_bytes(backup_path.stat().st_size),
        "include_shots": include_shots,
    }


def _export_activities(
    day: str | None = None,
    start_day: str | None = None,
    end_day: str | None = None,
) -> dict[str, Any]:
    config.ensure_dirs()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if start_day and end_day:
        if start_day > end_day:
            start_day, end_day = end_day, start_day
        rows = db.activities_for_day(start_day) if start_day == end_day else db.activities_between(start_day, end_day)
        label = start_day if start_day == end_day else f"{start_day}_to_{end_day}"
    else:
        rows = db.activities_for_day(day) if day else _all_activities()
        label = day or "all"
    path = config.EXPORTS_DIR / f"书赫日报助手-activities-{label}-{stamp}.csv"
    fields = ["id", "ts", "day", "category", "summary", "app", "window_title", "shot_path"]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in fields})
    return {
        "path": str(path),
        "filename": path.name,
        "size": path.stat().st_size,
        "size_label": _format_bytes(path.stat().st_size),
        "rows": len(rows),
        "day": day or "",
        "from": start_day or "",
        "to": end_day or "",
    }


def _export_reports() -> dict[str, Any]:
    config.ensure_dirs()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = config.EXPORTS_DIR / f"书赫日报助手-reports-{stamp}.json"
    reports = [_report_row_to_dict(row) for row in _all_reports()]
    payload = {
        "app": "书赫日报助手",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "reports": reports,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "path": str(path),
        "filename": path.name,
        "size": path.stat().st_size,
        "size_label": _format_bytes(path.stat().st_size),
        "rows": len(reports),
    }


def _import_json_data(payload: dict[str, Any]) -> dict[str, Any]:
    reports = payload.get("reports") if isinstance(payload, dict) else None
    activities = payload.get("activities") if isinstance(payload, dict) else None
    if reports is None and isinstance(payload, dict) and {"day", "body"}.issubset(payload):
        reports = [payload]
    if reports is None and activities is None:
        raise ValueError("JSON 中没有可导入的 reports 或 activities")

    imported_reports = 0
    imported_activities = 0
    with db.connect() as conn:
        for item in list(reports or [])[:5000]:
            if not isinstance(item, dict):
                continue
            day = str(item.get("day") or "").strip()
            body = str(item.get("body") or "").strip()
            if not day or not body:
                continue
            try:
                datetime.strptime(day, "%Y-%m-%d")
            except ValueError:
                continue
            kind = str(item.get("kind") or "日报").strip()[:40] or "日报"
            style = str(item.get("style") or "导入").strip()[:80] or "导入"
            title = str(item.get("title") or f"{day} {kind}").strip()[:120] or f"{day} {kind}"
            created_at = str(item.get("created_at") or datetime.now().isoformat(timespec="seconds")).strip()
            conn.execute(
                "INSERT INTO reports (created_at, day, kind, style, title, body) VALUES (?, ?, ?, ?, ?, ?)",
                (created_at, day, kind, style, title, body),
            )
            imported_reports += 1

        valid_categories = set(settings.load()["activity_categories"])
        for item in list(activities or [])[:5000]:
            if not isinstance(item, dict):
                continue
            summary = str(item.get("summary") or "").strip()
            ts_value = str(item.get("ts") or "").strip()
            day = str(item.get("day") or "").strip()
            if not summary or not ts_value:
                continue
            try:
                ts = datetime.fromisoformat(ts_value)
            except ValueError:
                continue
            day = day or ts.strftime("%Y-%m-%d")
            category = str(item.get("category") or "其他").strip()
            if category not in valid_categories:
                category = "其他" if "其他" in valid_categories else next(iter(valid_categories), "其他")
            conn.execute(
                "INSERT INTO activities (ts, day, category, summary, app, window_title, shot_path) VALUES (?, ?, ?, ?, ?, ?, NULL)",
                (
                    ts.isoformat(timespec="seconds"),
                    day,
                    category,
                    summary,
                    str(item.get("app") or "").strip() or None,
                    str(item.get("window_title") or "").strip() or None,
                ),
            )
            imported_activities += 1
    return {"reports": imported_reports, "activities": imported_activities}


def _clear_all_data() -> dict[str, Any]:
    with db.connect() as conn:
        counts = {
            "activities": int(conn.execute("SELECT COUNT(*) AS total FROM activities").fetchone()["total"] or 0),
            "reports": int(conn.execute("SELECT COUNT(*) AS total FROM reports").fetchone()["total"] or 0),
            "day_notes": int(conn.execute("SELECT COUNT(*) AS total FROM day_notes").fetchone()["total"] or 0),
            "chat": int(conn.execute("SELECT COUNT(*) AS total FROM chat_messages").fetchone()["total"] or 0),
        }
    shots = storage.clear_shots().get("removed", 0)
    with db.connect() as conn:
        conn.execute("DELETE FROM activities")
        conn.execute("DELETE FROM reports")
        conn.execute("DELETE FROM day_notes")
        conn.execute("DELETE FROM chat_messages")
    return {**counts, "shots": int(shots or 0)}


def _all_activities() -> list[db.sqlite3.Row]:
    with db.connect() as conn:
        return list(conn.execute("SELECT * FROM activities ORDER BY ts ASC"))


def _all_reports() -> list[db.sqlite3.Row]:
    with db.connect() as conn:
        return list(conn.execute("SELECT * FROM reports ORDER BY created_at ASC"))


def _report_row_to_dict(row: db.sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "day": row["day"],
        "kind": row["kind"],
        "style": row["style"],
        "title": row["title"],
        "body": row["body"],
    }


def _search_activities(params: dict[str, list[str]]) -> dict[str, Any]:
    query = (params.get("q") or [""])[0].strip()
    start_day = (params.get("from") or [""])[0].strip() or None
    end_day = (params.get("to") or [""])[0].strip() or None
    category = (params.get("category") or [""])[0].strip() or None
    categories = settings.load()["activity_categories"]
    if category and category not in categories:
        raise ValueError("活动分类无效")
    try:
        limit = int((params.get("limit") or ["100"])[0])
    except ValueError:
        limit = 100
    rows = db.search_activities(
        query=query,
        start_day=start_day,
        end_day=end_day,
        category=category,
        limit=limit,
    )
    return {
        "query": query,
        "from": start_day or "",
        "to": end_day or "",
        "category": category or "",
        "count": len(rows),
        "items": [_row_to_dict(row) for row in rows],
    }


def _zip_file_if_exists(zf: zipfile.ZipFile, path: Path, arcname: str) -> None:
    if path.exists() and path.is_file():
        zf.write(path, arcname)


def _zip_tree(zf: zipfile.ZipFile, root: Path, arc_root: str) -> None:
    if not root.exists():
        return
    for path in sorted(root.rglob("*")):
        if path.is_file():
            zf.write(path, f"{arc_root}/{path.relative_to(root)}")


def _format_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{int(amount)} {unit}" if unit == "B" else f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{value} B"


def _tail_text(path: Path, max_bytes: int = 16000) -> str:
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - max_bytes))
            data = handle.read(max_bytes)
    except OSError as exc:
        return f"读取失败：{exc}"
    text = data.decode("utf-8", errors="replace")
    if len(data) == max_bytes:
        text = "...\n" + text
    return text.strip()


def _activity_action(raw_path: str, action: str) -> int | None:
    prefix = "/api/activities/"
    suffix = f"/{action}"
    if not raw_path.startswith(prefix) or not raw_path.endswith(suffix):
        return None
    raw_id = raw_path.removeprefix(prefix).removesuffix(suffix)
    return int(raw_id) if raw_id.isdigit() else None


def _update_activity(activity_id: int, body: dict[str, Any]) -> dict[str, Any]:
    old = db.activity_by_id(activity_id)
    if not old:
        raise FileNotFoundError("活动记录不存在")
    category = str(body.get("category") or old["category"]).strip()
    summary = str(body.get("summary") or "").strip()
    app = str(body.get("app") or "").strip()
    window_title = str(body.get("window_title") or "").strip()
    if category not in settings.load()["activity_categories"]:
        raise ValueError("活动分类无效")
    if not summary:
        raise ValueError("摘要不能为空")
    ok = db.update_activity(
        activity_id,
        category=category,
        summary=summary,
        app=app or None,
        window_title=window_title or None,
    )
    if not ok:
        raise FileNotFoundError("活动记录不存在")
    row = db.activity_by_id(activity_id)
    return {
        "item": _row_to_dict(row) if row else None,
        "summary": _summary(old["day"]),
    }


def _create_activity(body: dict[str, Any]) -> dict[str, Any]:
    day = str(body.get("day") or date.today().strftime("%Y-%m-%d")).strip()
    time_value = str(body.get("time") or datetime.now().strftime("%H:%M")).strip()
    category = str(body.get("category") or "").strip()
    summary = str(body.get("summary") or "").strip()
    app = str(body.get("app") or "").strip()
    window_title = str(body.get("window_title") or "").strip()
    if category not in settings.load()["activity_categories"]:
        raise ValueError("活动分类无效")
    if not summary:
        raise ValueError("摘要不能为空")
    try:
        ts = datetime.fromisoformat(f"{day}T{time_value}")
    except ValueError as exc:
        raise ValueError("日期或时间格式无效") from exc
    row_id = db.add_activity(
        category=category,
        summary=summary,
        app=app or None,
        window_title=window_title or None,
        shot_path=None,
        ts=ts,
    )
    row = db.activity_by_id(row_id)
    return {
        "item": _row_to_dict(row) if row else None,
        "summary": _summary(day),
    }


def _delete_activity(activity_id: int) -> dict[str, Any]:
    old = db.activity_by_id(activity_id)
    if not old:
        raise FileNotFoundError("活动记录不存在")
    db.delete_activity(activity_id)
    return {
        "deleted": activity_id,
        "day": old["day"],
        "summary": _summary(old["day"]),
    }


def _category_color(category: str) -> str:
    palette = {
        "编码开发": "#0f766e",
        "会议沟通": "#2563eb",
        "文档写作": "#7c3aed",
        "阅读学习": "#0891b2",
        "邮件即时通讯": "#db2777",
        "设计": "#ea580c",
        "数据分析": "#4f46e5",
        "网页浏览": "#65a30d",
        "娱乐休息": "#64748b",
        "其他": "#475569",
    }
    return palette.get(category, "#475569")


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "ShuheRiji/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            query = parse_qs(parsed.query)
            if _should_serve_agent_docs_at_root(query, self.headers.get("Accept", "")):
                self._send_text(_agent_docs(), content_type="text/markdown; charset=utf-8")
            else:
                self._serve_file(STATIC_DIR / "index.html")
        elif parsed.path.startswith("/static/"):
            rel = unquote(parsed.path.removeprefix("/static/"))
            self._serve_file(STATIC_DIR / rel)
        elif parsed.path == "/api/summary":
            query = parse_qs(parsed.query)
            day = query.get("date", [date.today().strftime("%Y-%m-%d")])[0]
            heatmap_from = query.get("heatmap_from", [""])[0]
            heatmap_to = query.get("heatmap_to", [""])[0]
            self._send_json(_summary(day, heatmap_from=heatmap_from, heatmap_to=heatmap_to))
        elif parsed.path == "/api/app-usage":
            query = parse_qs(parsed.query)
            day = query.get("date", [date.today().strftime("%Y-%m-%d")])[0]
            period = query.get("period", ["day"])[0]
            start_day = query.get("from", [""])[0]
            end_day = query.get("to", [""])[0]
            self._send_json({"app_usage_summary": _app_usage_range(day, period, start_day, end_day)})
        elif parsed.path == "/api/recording/status":
            self._send_json(RECORDER.snapshot())
        elif parsed.path == "/api/settings":
            self._send_json({"settings": _summary(date.today().strftime("%Y-%m-%d"))["settings"]})
        elif parsed.path == "/api/permissions":
            self._send_json({"permissions": permissions.status()})
        elif parsed.path == "/api/storage":
            self._send_json({"storage": storage.stats()})
        elif parsed.path == "/api/logs":
            self._send_json({"logs": _logs_snapshot()})
        elif parsed.path == "/api/request-logs":
            try:
                page = int(parse_qs(parsed.query).get("page", ["1"])[0] or 1)
            except ValueError:
                page = 1
            self._send_json({"request_logs": _request_logs_snapshot(page)})
        elif parsed.path == "/api/health":
            self._send_json({"health": _health()})
        elif parsed.path == "/api/agent-docs":
            self._send_text(_agent_docs(), content_type="text/markdown; charset=utf-8")
        elif parsed.path == "/api/notifications":
            day = parse_qs(parsed.query).get("date", [date.today().strftime("%Y-%m-%d")])[0]
            self._send_json({"notifications": _notifications_snapshot(day)})
        elif parsed.path == "/api/release/check":
            self._send_json({"release_check": _release_check()})
        elif parsed.path == "/api/release/download/status":
            self._send_json({"download": _download_status()})
        elif parsed.path == "/api/model-config":
            self._send_json({"model_config": _model_config()})
        elif parsed.path == "/api/autostart":
            self._send_json({"autostart": _autostart_status()})
        elif parsed.path == "/api/days":
            self._send_json({"days": _activity_days()})
        elif parsed.path == "/api/reports":
            self._send_json({"reports": _reports_list()})
        elif parsed.path == "/api/search":
            try:
                self._send_json({"search": _search_activities(parse_qs(parsed.query))})
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=400)
        elif parsed.path.startswith("/api/reports/"):
            self._serve_report(parsed.path.removeprefix("/api/reports/"))
        elif parsed.path.startswith("/shots/"):
            self._serve_shot(parsed.path.removeprefix("/shots/"))
        elif parsed.path.startswith("/app-icons/"):
            self._serve_app_icon(parsed.path.removeprefix("/app-icons/"))
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/recording/start":
            changed = RECORDER.start()
            self._send_json({"changed": changed, **RECORDER.snapshot()})
        elif parsed.path == "/api/recording/capture-now":
            result = RECORDER.capture_once()
            if result.get("ok") or result.get("skipped"):
                day = (result.get("item") or {}).get("day") or date.today().strftime("%Y-%m-%d")
                self._send_json({**result, "summary": _summary(day)})
            else:
                self._send_json(result, status=500)
        elif parsed.path == "/api/recording/stop":
            changed = RECORDER.stop()
            self._send_json({"changed": changed, **RECORDER.snapshot()})
        elif parsed.path == "/api/report":
            body = self._read_json()
            kind = body.get("kind", "day")
            runtime = settings.load()
            style = report.normalize_style(body.get("style", "标准"), runtime["custom_report_styles"])
            instruction = str(body.get("instruction") or "").strip()
            day = body.get("date") or date.today().strftime("%Y-%m-%d")
            try:
                start_day, end_day = _normalize_report_range(day, kind, body.get("start_date"), body.get("end_date"))
                rows = db.activities_for_day(end_day) if start_day == end_day else db.activities_between(start_day, end_day)
                if not rows:
                    label = end_day if start_day == end_day else f"{start_day} ~ {end_day}"
                    report_name = {"day": "日报", "week": "周报", "month": "月报"}.get(kind, "报告")
                    self._send_json(
                        {
                            "ok": True,
                            "skipped": True,
                            "text": f"{label} 暂无活动记录，未生成{report_name}。先开始记录或补记活动后再试。",
                            "report_id": None,
                            "reports": _reports_list(),
                        }
                    )
                    return
                report_name = {"day": "日报", "week": "周报", "month": "月报"}.get(kind, "报告")
                if kind == "day" and start_day == end_day:
                    text = report.daily_report(
                        end_day,
                        style=style,
                        instruction=instruction,
                        custom_styles=runtime["custom_report_styles"],
                    )
                else:
                    text = report.range_report(
                        start_day,
                        end_day,
                        report_name,
                        style=style,
                        instruction=instruction,
                        custom_styles=runtime["custom_report_styles"],
                    )
                report_id = db.add_report(day=end_day, kind=report_name, style=style, body=text)
                self._send_json({"ok": True, "text": text, "report_id": report_id, "reports": _reports_list()})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=500)
        elif parsed.path == "/api/chat":
            body = self._read_json()
            day = str(body.get("date") or date.today().strftime("%Y-%m-%d")).strip()
            scope = str(body.get("scope") or "day").strip()
            question = str(body.get("question") or "").strip()
            try:
                datetime.strptime(day, "%Y-%m-%d")
                message = _answer_chat(day, scope, question)
                self._send_json({"ok": True, "message": message, "chat": _chat_messages(day)})
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=400)
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=500)
        elif parsed.path == "/api/settings":
            try:
                updated = settings.save(self._read_json())
                if updated["privacy_mode"]:
                    storage.clear_shots()
                styles = report.available_styles(updated["custom_report_styles"])
                self._send_json(
                    {
                        "ok": True,
                        "settings": {**updated, "settings_path": str(settings.SETTINGS_PATH)},
                        "styles": list(styles.keys()),
                        "style_descriptions": styles,
                        "storage": storage.stats(),
                        "project_context": _project_context_status(updated),
                    }
                )
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=400)
        elif parsed.path == "/api/auto-report":
            try:
                body = self._read_json()
                runtime = settings.load()
                updated = settings.save(
                    {
                        "auto_report_enabled": body.get("enabled"),
                        "auto_report_time": body.get("time"),
                        "auto_report_style": report.normalize_style(body.get("style"), runtime["custom_report_styles"]),
                    }
                )
                AUTO_REPORTER.start()
                self._send_json({"ok": True, "settings": updated, "auto_report": AUTO_REPORTER.snapshot()})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=400)
        elif parsed.path == "/api/auto-report/run-now":
            try:
                body = self._read_json()
                day = str(body.get("day") or date.today().strftime("%Y-%m-%d")).strip()
                datetime.strptime(day, "%Y-%m-%d")
                result = AUTO_REPORTER.run_now(day)
                self._send_json({**result, "summary": _summary(day)})
            except ValueError:
                self._send_json({"ok": False, "error": "日期格式无效"}, status=400)
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=500)
        elif parsed.path == "/api/day-note":
            body = self._read_json()
            day = str(body.get("day") or date.today().strftime("%Y-%m-%d")).strip()
            note = str(body.get("note") or "").strip()
            try:
                datetime.strptime(day, "%Y-%m-%d")
                db.save_day_note(day, note)
                self._send_json({"ok": True, "day_note": _day_note(day)})
            except ValueError:
                self._send_json({"ok": False, "error": "日期格式无效"}, status=400)
        elif parsed.path == "/api/permissions/open":
            body = self._read_json()
            url = permissions.open_settings(body.get("kind", "screen_recording"))
            self._send_json({"ok": True, "url": url})
        elif parsed.path == "/api/release/download":
            try:
                self._send_json({"download": _start_release_download()})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=500)
        elif parsed.path == "/api/open-path":
            try:
                opened = _open_local_path(self._read_json().get("kind", "data"))
                self._send_json({"ok": True, "opened": opened})
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=400)
        elif parsed.path == "/api/backup":
            body = self._read_json()
            try:
                backup = _create_backup(include_shots=body.get("include_shots", True) is not False)
                self._send_json({"ok": True, "backup": backup})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=500)
        elif parsed.path == "/api/export/activities":
            body = self._read_json()
            day = str(body.get("day") or "").strip() or None
            start_day = str(body.get("from") or "").strip() or None
            end_day = str(body.get("to") or "").strip() or None
            try:
                exported = _export_activities(day=day, start_day=start_day, end_day=end_day)
                self._send_json({"ok": True, "export": exported})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=500)
        elif parsed.path == "/api/export/reports":
            try:
                exported = _export_reports()
                self._send_json({"ok": True, "export": exported})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=500)
        elif parsed.path == "/api/reports/export-all":
            try:
                exported = _export_all_report_markdowns()
                self._send_json({"ok": True, "export": exported})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=500)
        elif parsed.path == "/api/model-test":
            try:
                result = _test_model_connection()
                self._send_json({"ok": True, "test": result})
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=400)
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=500)
        elif parsed.path == "/api/model-config":
            try:
                model_config = _save_model_config(self._read_json())
                self._send_json({"ok": True, "model_config": model_config, "health": _health()})
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=400)
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=500)
        elif parsed.path == "/api/autostart/install":
            try:
                autostart.install()
                self._send_json({"ok": True, "autostart": _autostart_status()})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc), "autostart": _autostart_status()}, status=500)
        elif parsed.path == "/api/autostart/uninstall":
            try:
                autostart.uninstall()
                self._send_json({"ok": True, "autostart": _autostart_status()})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc), "autostart": _autostart_status()}, status=500)
        elif parsed.path == "/api/storage/clear-shots":
            result = storage.clear_shots()
            self._send_json({"ok": True, **result})
        elif parsed.path == "/api/storage/clear-all":
            try:
                cleared = _clear_all_data()
                self._send_json({"ok": True, "cleared": cleared, "summary": _summary(date.today().strftime("%Y-%m-%d"))})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=500)
        elif parsed.path == "/api/request-logs/clear":
            self._send_json({"ok": True, **_clear_request_logs()})
        elif parsed.path == "/api/import/json":
            try:
                imported = _import_json_data(self._read_json())
                self._send_json({"ok": True, "imported": imported, "summary": _summary(date.today().strftime("%Y-%m-%d"))})
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=400)
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=500)
        elif activity_id := _activity_action(parsed.path, "update"):
            try:
                result = _update_activity(activity_id, self._read_json())
                self._send_json({"ok": True, **result})
            except FileNotFoundError as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=404)
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=400)
        elif parsed.path == "/api/activities/create":
            try:
                result = _create_activity(self._read_json())
                self._send_json({"ok": True, **result})
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=400)
        elif activity_id := _activity_action(parsed.path, "delete"):
            try:
                result = _delete_activity(activity_id)
                self._send_json({"ok": True, **result})
            except FileNotFoundError as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=404)
        elif parsed.path.startswith("/api/reports/") and parsed.path.endswith("/export"):
            raw_id = parsed.path.removeprefix("/api/reports/").removesuffix("/export")
            if not raw_id.isdigit():
                self._send_json({"ok": False, "error": "报告 ID 无效"}, status=400)
                return
            try:
                exported = _export_report(int(raw_id))
                self._send_json({"ok": True, "export": exported})
            except FileNotFoundError as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=404)
        elif parsed.path.startswith("/api/reports/") and parsed.path.endswith("/update"):
            raw_id = parsed.path.removeprefix("/api/reports/").removesuffix("/update")
            if not raw_id.isdigit():
                self._send_json({"ok": False, "error": "报告 ID 无效"}, status=400)
                return
            body = str(self._read_json().get("body") or "").strip()
            if not body:
                self._send_json({"ok": False, "error": "报告正文不能为空"}, status=400)
                return
            updated = db.update_report_body(int(raw_id), body)
            if not updated:
                self._send_json({"ok": False, "error": "报告不存在"}, status=404)
                return
            self._send_json({"ok": True, "report": {"id": int(raw_id), "body": body}, "reports": _reports_list()})
        elif parsed.path.startswith("/api/reports/") and parsed.path.endswith("/delete"):
            raw_id = parsed.path.removeprefix("/api/reports/").removesuffix("/delete")
            if not raw_id.isdigit():
                self._send_json({"ok": False, "error": "报告 ID 无效"}, status=400)
                return
            deleted = db.delete_report(int(raw_id))
            self._send_json({"ok": deleted, "reports": _reports_list()})
        elif parsed.path.startswith("/api/chat/") and parsed.path.endswith("/delete"):
            raw_id = parsed.path.removeprefix("/api/chat/").removesuffix("/delete")
            day = parse_qs(parsed.query).get("date", [date.today().strftime("%Y-%m-%d")])[0]
            if not raw_id.isdigit():
                self._send_json({"ok": False, "error": "聊天 ID 无效"}, status=400)
                return
            deleted = db.delete_chat_message(int(raw_id))
            self._send_json({"ok": deleted, "chat": _chat_messages(day)})
        else:
            self.send_error(404)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[panel] {self.address_string()} - {fmt % args}")

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send_json(self, data: dict[str, Any], status: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        self._record_request_log(status)

    def _send_text(self, text: str, status: int = 200, content_type: str = "text/plain; charset=utf-8") -> None:
        payload = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        self._record_request_log(status)

    def _record_request_log(self, status: int) -> None:
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/") or parsed.path.startswith("/api/request-logs"):
            return
        params = parse_qs(parsed.query)
        safe_params = {
            key: ["***" if any(hint in key.lower() for hint in ("key", "token", "password", "secret")) else str(value) for value in values]
            for key, values in params.items()
        }
        item = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "method": self.command,
            "path": parsed.path,
            "params": safe_params,
            "status": status,
            "source": self.client_address[0] if self.client_address else "-",
        }
        with REQUEST_LOGS_LOCK:
            REQUEST_LOGS.append(item)
            del REQUEST_LOGS[:-REQUEST_LOG_LIMIT]

    def _serve_file(self, path: Path) -> None:
        try:
            resolved = path.resolve()
            if not str(resolved).startswith(str(STATIC_DIR.resolve())):
                self.send_error(403)
                return
            payload = resolved.read_bytes()
        except FileNotFoundError:
            self.send_error(404)
            return
        content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _serve_shot(self, row_id: str) -> None:
        if not row_id.isdigit():
            self.send_error(404)
            return
        with db.connect() as conn:
            row = conn.execute("SELECT shot_path FROM activities WHERE id = ?", (int(row_id),)).fetchone()
        if not row or not row["shot_path"]:
            self.send_error(404)
            return
        path = Path(row["shot_path"]).expanduser()
        try:
            payload = path.read_bytes()
        except OSError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(str(path))[0] or "image/jpeg")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _serve_app_icon(self, filename: str) -> None:
        path = app_icons.resolve_cached(unquote(filename))
        if not path:
            self.send_error(404)
            return
        try:
            payload = path.read_bytes()
        except OSError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _serve_report(self, raw_id: str) -> None:
        if not raw_id.isdigit():
            self.send_error(404)
            return
        row = db.report_by_id(int(raw_id))
        if not row:
            self.send_error(404)
            return
        self._send_json({
            "report": {
                "id": row["id"],
                "created_at": row["created_at"],
                "day": row["day"],
                "kind": row["kind"],
                "style": row["style"],
                "title": row["title"],
                "body": row["body"],
            }
        })


def run(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    config.ensure_dirs()
    start_background_services()
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    url = f"http://{host}:{port}"
    print(f"[riji] 面板已启动：{url}")
    print(f"[riji] 数据目录：{config.DATA_DIR}")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[riji] 面板已停止。")
    finally:
        RECORDER.stop()
        AUTO_REPORTER.stop()
        server.server_close()
