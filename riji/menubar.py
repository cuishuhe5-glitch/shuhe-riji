"""macOS menu bar app for Shuhe Riji."""

from __future__ import annotations

import threading
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from . import config, web


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    try:
        import rumps
    except ImportError as exc:
        raise SystemExit("菜单栏模式需要 rumps：请先运行 `pip install -r requirements.txt`") from exc

    app = ShuheMenuBarApp(host=host, port=port, rumps_module=rumps)
    app.run()


class ShuheMenuBarApp:
    def __init__(self, host: str, port: int, rumps_module: Any) -> None:
        self.host = host
        self.port = port
        self.url = f"http://{host}:{port}"
        self.rumps = rumps_module
        self.server: ThreadingHTTPServer | None = None
        self.server_thread: threading.Thread | None = None

        self.app = self.rumps.App("书赫", title="书赫", quit_button=None)
        self.status_item = self.rumps.MenuItem("状态：准备中")
        self.toggle_item = self.rumps.MenuItem("开始记录", callback=self.toggle_recording)
        self.capture_item = self.rumps.MenuItem("立即记录当前屏幕", callback=self.capture_now)
        self.open_item = self.rumps.MenuItem("打开面板", callback=self.open_panel)
        self.open_reports_item = self.rumps.MenuItem("打开报告目录", callback=self.open_reports_dir)
        self.open_data_item = self.rumps.MenuItem("打开数据目录", callback=self.open_data_dir)
        self.refresh_item = self.rumps.MenuItem("刷新状态", callback=self.refresh_status)
        self.quit_item = self.rumps.MenuItem("退出书赫日报助手", callback=self.quit)

        self.app.menu = [
            self.status_item,
            None,
            self.open_item,
            self.open_reports_item,
            self.open_data_item,
            None,
            self.toggle_item,
            self.capture_item,
            self.refresh_item,
            None,
            self.quit_item,
        ]
        self._start_server()
        self.refresh_status(None)

    def run(self) -> None:
        self.app.run()

    def _start_server(self) -> None:
        config.ensure_dirs()
        web.start_background_services()
        try:
            self.server = ThreadingHTTPServer((self.host, self.port), web.DashboardHandler)
        except OSError:
            self.server = None
            self.status_item.title = "状态：面板端口已被占用"
            return
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

    def open_panel(self, _sender: Any) -> None:
        webbrowser.open(self.url)

    def open_reports_dir(self, _sender: Any) -> None:
        self._open_path(config.REPORTS_DIR)

    def open_data_dir(self, _sender: Any) -> None:
        self._open_path(config.DATA_DIR)

    def capture_now(self, _sender: Any) -> None:
        self.capture_item.title = "记录中..."
        result = web.RECORDER.capture_once()
        if result.get("ok"):
            message = "已记录当前屏幕"
        elif result.get("skipped"):
            message = result.get("message") or "本次已跳过"
        else:
            message = result.get("error") or "立即记录失败"
        self._notify(message)
        self.refresh_status(None)

    def toggle_recording(self, _sender: Any) -> None:
        if web.RECORDER.running:
            web.RECORDER.stop()
        else:
            web.RECORDER.start()
        self.refresh_status(None)

    def refresh_status(self, _sender: Any) -> None:
        snapshot = web.RECORDER.snapshot()
        if snapshot["stopping"]:
            status = "正在暂停"
        elif snapshot["running"]:
            status = "正在记录"
        else:
            status = "已暂停"
        self.status_item.title = f"状态：{status} / {snapshot['message']}"
        self.toggle_item.title = "暂停记录" if snapshot["running"] else "开始记录"
        self.capture_item.title = "立即记录当前屏幕"
        self.app.title = "● 书赫" if snapshot["running"] else "书赫"

    def _open_path(self, path: Path) -> None:
        config.ensure_dirs()
        webbrowser.open(path.expanduser().resolve().as_uri())

    def _notify(self, message: str) -> None:
        try:
            self.rumps.notification("书赫日报助手", "", message)
        except Exception:
            pass

    def quit(self, _sender: Any) -> None:
        web.RECORDER.stop()
        web.AUTO_REPORTER.stop()
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        self.rumps.quit_application()
