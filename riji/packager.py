"""Create a lightweight macOS .app wrapper for Shuhe Riji."""

from __future__ import annotations

import os
import plistlib
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path
from textwrap import dedent

from PIL import Image, ImageDraw, ImageFont

from . import __version__, keychain

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
    launcher_script = resources / "launcher.zsh"
    if portable:
        _copy_portable_payload(root, resources)
    launcher_script.write_text(_launcher_script(root, mode, portable=portable), encoding="utf-8")
    launcher_script.chmod(launcher_script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    _write_native_launcher(launcher)

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
        "CFBundleShortVersionString": __version__,
        "CFBundleVersion": __version__,
        "LSMinimumSystemVersion": "11.0",
        "LSUIElement": mode == "menubar",
        "NSHighResolutionCapable": True,
        "ShuheRijiPortable": portable,
    }
    (contents / "Info.plist").write_bytes(plistlib.dumps(info, sort_keys=False))
    _sign_app(app)
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


def build_dmg(output_dir: str | Path | None = None, mode: str = "desktop", portable: bool = True) -> Path:
    if shutil.which("hdiutil") is None:
        raise RuntimeError("当前系统缺少 hdiutil，无法生成 macOS DMG。")
    out = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    app = build(output_dir=out, mode=mode, portable=portable)
    dmg_path = out / "shuhe-riji-macos.dmg"
    if dmg_path.exists():
        dmg_path.unlink()
    subprocess.run(
        [
            "hdiutil",
            "create",
            "-volname",
            APP_NAME,
            "-srcfolder",
            str(app),
            "-ov",
            "-format",
            "UDZO",
            str(dmg_path),
        ],
        check=True,
    )
    return dmg_path


def build_windows_portable(output_dir: str | Path | None = None) -> Path:
    root = Path(__file__).resolve().parents[1]
    out = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    package_dir = out / "shuhe-riji-windows-portable"
    zip_path = out / "shuhe-riji-windows-portable.zip"
    app_dir = package_dir / "app"
    if package_dir.exists():
        shutil.rmtree(package_dir)
    if zip_path.exists():
        zip_path.unlink()
    app_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(root / "riji", app_dir / "riji", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for filename in ["requirements.txt", "README.md"]:
        source = root / filename
        if source.exists():
            shutil.copy2(source, app_dir / filename)
    (package_dir / "start-shuhe-riji.cmd").write_text(_windows_launcher_script(), encoding="utf-8")
    (package_dir / "configure-model.cmd").write_text(_windows_env_script(), encoding="utf-8")
    (package_dir / "README-Windows.txt").write_text(_windows_readme(), encoding="utf-8")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in package_dir.rglob("*"):
            archive.write(path, path.relative_to(out))
    return zip_path


def write_env_template(
    path: str | Path | None = None,
    *,
    api_key: str | None = None,
    base_url: str = "http://localhost:55021/v1",
    model: str = "gpt-5.5",
    provider: str = "openai",
    overwrite: bool = False,
) -> Path:
    target = Path(path) if path else Path.home() / ".shuhe-riji" / "env.sh"
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


def _windows_launcher_script() -> str:
    return dedent(
        r"""\
        @echo off
        chcp 65001 >nul
        setlocal
        cd /d "%~dp0app"
        if not exist ".venv\Scripts\python.exe" (
          echo [书赫日报助手] 首次启动，正在创建本地 Python 环境...
          py -3 -m venv .venv
          if errorlevel 1 (
            echo 未找到 Python。请先安装 Python 3.11+，并勾选 Add python.exe to PATH。
            pause
            exit /b 1
          )
          ".venv\Scripts\python.exe" -m pip install --upgrade pip
          ".venv\Scripts\python.exe" -m pip install -r requirements.txt
          if errorlevel 1 (
            echo 依赖安装失败，请检查网络或手动运行 pip install -r requirements.txt。
            pause
            exit /b 1
          )
        )
        if exist "%USERPROFILE%\.shuhe-riji\env.cmd" call "%USERPROFILE%\.shuhe-riji\env.cmd"
        start "书赫日报助手" http://127.0.0.1:8765/
        ".venv\Scripts\python.exe" -m riji panel --host 127.0.0.1 --port 8765 --no-open
        endlocal
        """
    )


def _windows_env_script() -> str:
    return dedent(
        r"""\
        @echo off
        chcp 65001 >nul
        setlocal
        set CONFIG_DIR=%USERPROFILE%\.shuhe-riji
        if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"
        echo 正在写入 %CONFIG_DIR%\env.cmd
        > "%CONFIG_DIR%\env.cmd" echo @echo off
        >> "%CONFIG_DIR%\env.cmd" echo set RIJI_LLM_PROVIDER=openai
        >> "%CONFIG_DIR%\env.cmd" echo set RIJI_OPENAI_BASE_URL=http://localhost:55021/v1
        >> "%CONFIG_DIR%\env.cmd" echo set RIJI_OPENAI_MODEL=gpt-5.5
        >> "%CONFIG_DIR%\env.cmd" echo rem set RIJI_OPENAI_API_KEY=请在这里填写你的 key
        echo 已生成。请用记事本打开并填写 RIJI_OPENAI_API_KEY。
        notepad "%CONFIG_DIR%\env.cmd"
        endlocal
        """
    )


def _windows_readme() -> str:
    return dedent(
        """\
        书赫日报助手 Windows 便携版

        1. 先安装 Python 3.11 或更新版本，并勾选 Add python.exe to PATH。
        2. 双击 configure-model.cmd，填写 RIJI_OPENAI_API_KEY。
        3. 双击 start-shuhe-riji.cmd。
        4. 浏览器会打开 http://127.0.0.1:8765/。

        数据默认保存在：%USERPROFILE%\\.shuhe-riji
        截图采集使用 mss，前台窗口标题通过 Windows API 获取。
        """
    )


def _shell_quote(value: str) -> str:
    return "'" + str(value).replace("'", "'\"'\"'") + "'"


def _write_native_launcher(target: Path) -> None:
    compiler = shutil.which("clang") or shutil.which("cc")
    if compiler is None:
        raise RuntimeError("当前系统缺少 clang/cc，无法生成可双击启动的 macOS 应用。")
    source = target.with_suffix(".m")
    source.write_text(
        dedent(
            r"""\
            #import <Cocoa/Cocoa.h>
            #import <WebKit/WebKit.h>

            @interface AppDelegate : NSObject <NSApplicationDelegate, NSWindowDelegate>
            @property(nonatomic, strong) NSTask *serverTask;
            @property(nonatomic, strong) NSWindow *window;
            @property(nonatomic, strong) WKWebView *webView;
            @end

            @implementation AppDelegate

            - (void)applicationDidFinishLaunching:(NSNotification *)notification {
                [self startServer];
                [self createWindow];
                [NSApp activateIgnoringOtherApps:YES];
                [self performSelector:@selector(loadDashboard) withObject:nil afterDelay:1.0];
            }

            - (void)startServer {
                NSString *scriptPath = [[[NSBundle mainBundle] resourcePath] stringByAppendingPathComponent:@"launcher.zsh"];
                NSMutableDictionary *environment = [[[NSProcessInfo processInfo] environment] mutableCopy];
                environment[@"SHUHE_RIJI_NATIVE_SHELL"] = @"1";
                self.serverTask = [[NSTask alloc] init];
                self.serverTask.launchPath = @"/bin/zsh";
                self.serverTask.arguments = @[scriptPath];
                self.serverTask.environment = environment;
                NSError *error = nil;
                if (![self.serverTask launchAndReturnError:&error]) {
                    NSLog(@"Failed to start Shuhe Riji service: %@", error);
                }
            }

            - (void)createWindow {
                NSRect rect = NSMakeRect(0, 0, 1180, 780);
                NSUInteger style = NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskMiniaturizable | NSWindowStyleMaskResizable;
                self.window = [[NSWindow alloc] initWithContentRect:rect styleMask:style backing:NSBackingStoreBuffered defer:NO];
                self.window.title = @"书赫日报助手";
                self.window.minSize = NSMakeSize(960, 620);
                self.window.delegate = self;
                [self.window center];

                WKWebViewConfiguration *configuration = [[WKWebViewConfiguration alloc] init];
                self.webView = [[WKWebView alloc] initWithFrame:rect configuration:configuration];
                self.window.contentView = self.webView;
                [self.window makeKeyAndOrderFront:nil];
            }

            - (void)loadDashboard {
                NSURL *url = [NSURL URLWithString:@"http://127.0.0.1:8765/"];
                [self.webView loadRequest:[NSURLRequest requestWithURL:url]];
            }

            - (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)sender {
                return YES;
            }

            - (void)applicationWillTerminate:(NSNotification *)notification {
                if (self.serverTask && self.serverTask.isRunning) {
                    [self.serverTask terminate];
                    [self.serverTask waitUntilExit];
                }
            }

            @end

            int main(int argc, const char * argv[]) {
                @autoreleasepool {
                    NSApplication *app = [NSApplication sharedApplication];
                    AppDelegate *delegate = [[AppDelegate alloc] init];
                    app.delegate = delegate;
                    [app setActivationPolicy:NSApplicationActivationPolicyRegular];
                    [app run];
                }
                return 0;
            }
            """
        ),
        encoding="utf-8",
    )
    subprocess.run(
        [compiler, "-fobjc-arc", str(source), "-o", str(target), "-framework", "Cocoa", "-framework", "WebKit"],
        check=True,
    )
    source.unlink(missing_ok=True)
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _sign_app(app: Path) -> None:
    if shutil.which("codesign") is None:
        return
    subprocess.run(
        [
            "codesign",
            "--force",
            "--deep",
            "--sign",
            "-",
            "--identifier",
            BUNDLE_ID,
            str(app),
        ],
        check=True,
    )


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
            export PYTHONEXECUTABLE="$APP_ROOT/MacOS/shuhe-riji"
            export RIJI_LLM_PROVIDER="${{RIJI_LLM_PROVIDER:-openai}}"
            export RIJI_OPENAI_BASE_URL="${{RIJI_OPENAI_BASE_URL:-http://localhost:55021/v1}}"
            export RIJI_OPENAI_MODEL="${{RIJI_OPENAI_MODEL:-gpt-5.5}}"
            if [ -f "$HOME/.shuhe-riji/env.sh" ]; then
              source "$HOME/.shuhe-riji/env.sh"
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
            RIJI_COMMAND=({command})
            if [ "$SHUHE_RIJI_NATIVE_SHELL" = "1" ]; then
              RIJI_COMMAND=(panel --no-open)
            fi
            if [ -x "$RESOURCES/venv/bin/python" ]; then
              exec "$RESOURCES/venv/bin/python" -m riji "${{RIJI_COMMAND[@]}}"
            fi
            exec /usr/bin/python3 -m riji "${{RIJI_COMMAND[@]}}"
            """
        )
    return dedent(
        f"""\
        #!/bin/zsh
        set -e
        APP_ROOT="${{0:A:h:h}}"
        export PYTHONEXECUTABLE="$APP_ROOT/MacOS/shuhe-riji"
        export RIJI_LLM_PROVIDER="${{RIJI_LLM_PROVIDER:-openai}}"
        export RIJI_OPENAI_BASE_URL="${{RIJI_OPENAI_BASE_URL:-http://localhost:55021/v1}}"
        export RIJI_OPENAI_MODEL="${{RIJI_OPENAI_MODEL:-gpt-5.5}}"
        if [ -f "$HOME/.shuhe-riji/env.sh" ]; then
          source "$HOME/.shuhe-riji/env.sh"
        fi
        if [ -z "$RIJI_OPENAI_API_KEY" ] && command -v security >/dev/null 2>&1; then
          RIJI_KEYCHAIN_KEY="$(security find-generic-password -s "书赫日报助手" -a "RIJI_OPENAI_API_KEY" -w 2>/dev/null || true)"
          if [ -n "$RIJI_KEYCHAIN_KEY" ]; then
            export RIJI_OPENAI_API_KEY="$RIJI_KEYCHAIN_KEY"
          fi
          unset RIJI_KEYCHAIN_KEY
        fi
        cd "{root}"
        RIJI_COMMAND=({command})
        if [ "$SHUHE_RIJI_NATIVE_SHELL" = "1" ]; then
          RIJI_COMMAND=(panel --no-open)
        fi
        exec "{python}" -m riji "${{RIJI_COMMAND[@]}}"
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
