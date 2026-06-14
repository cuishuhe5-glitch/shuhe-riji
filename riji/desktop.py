"""macOS native desktop shell for the local dashboard."""

from __future__ import annotations

import threading
from http.server import ThreadingHTTPServer
from typing import Any

from . import config, web


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    try:
        import objc
        from Cocoa import (
            NSApplication,
            NSApplicationActivationPolicyRegular,
            NSBackingStoreBuffered,
            NSMakeRect,
            NSMakeSize,
            NSObject,
            NSURL,
            NSURLRequest,
            NSWindow,
            NSWindowStyleMaskClosable,
            NSWindowStyleMaskMiniaturizable,
            NSWindowStyleMaskResizable,
            NSWindowStyleMaskTitled,
        )
        from WebKit import WKWebView, WKWebViewConfiguration
    except ImportError as exc:
        raise SystemExit("桌面窗口模式需要 WebKit：请先运行 `pip install -r requirements.txt`") from exc

    url = f"http://{host}:{port}"
    server = _start_server(host, port)

    class AppDelegate(NSObject):
        window: Any = objc.ivar()
        web_view: Any = objc.ivar()
        owned_server: Any = objc.ivar()

        def initWithServer_(self, owned_server: ThreadingHTTPServer | None) -> Any:
            self = objc.super(AppDelegate, self).init()
            if self is None:
                return None
            self.owned_server = owned_server
            return self

        def applicationDidFinishLaunching_(self, _notification: Any) -> None:
            rect = NSMakeRect(0, 0, 1180, 780)
            style = (
                NSWindowStyleMaskTitled
                | NSWindowStyleMaskClosable
                | NSWindowStyleMaskMiniaturizable
                | NSWindowStyleMaskResizable
            )
            self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                rect,
                style,
                NSBackingStoreBuffered,
                False,
            )
            self.window.setTitle_("书赫日报助手")
            self.window.setMinSize_(NSMakeSize(960, 620))
            self.window.center()

            configuration = WKWebViewConfiguration.alloc().init()
            self.web_view = WKWebView.alloc().initWithFrame_configuration_(rect, configuration)
            request = NSURLRequest.requestWithURL_(NSURL.URLWithString_(url))
            self.web_view.loadRequest_(request)
            self.window.setContentView_(self.web_view)
            self.window.makeKeyAndOrderFront_(None)

        def applicationShouldTerminateAfterLastWindowClosed_(self, _sender: Any) -> bool:
            return True

        def applicationWillTerminate_(self, _notification: Any) -> None:
            web.RECORDER.stop()
            web.AUTO_REPORTER.stop()
            if self.owned_server is not None:
                self.owned_server.shutdown()
                self.owned_server.server_close()

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    delegate = AppDelegate.alloc().initWithServer_(server)
    app.setDelegate_(delegate)
    app.activateIgnoringOtherApps_(True)
    app.run()


def _start_server(host: str, port: int) -> ThreadingHTTPServer | None:
    config.ensure_dirs()
    web.start_background_services()
    try:
        server = ThreadingHTTPServer((host, port), web.DashboardHandler)
    except OSError:
        return None
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
