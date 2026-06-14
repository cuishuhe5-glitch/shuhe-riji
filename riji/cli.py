"""命令行入口。用法见 README，或 `python -m riji --help`。"""

import argparse
import platform
from datetime import date

from . import __version__, config, daemon, report


def _cmd_watch(_args: argparse.Namespace) -> None:
    daemon.run()


def _cmd_report(args: argparse.Namespace) -> None:
    from . import settings
    runtime = settings.load()
    custom_styles = runtime["custom_report_styles"]
    if args.kind == "day":
        text = report.daily_report(args.date, style=args.style, custom_styles=custom_styles)
    elif args.kind == "week":
        text = report.weekly_report(args.date, style=args.style, custom_styles=custom_styles)
    else:
        text = report.monthly_report(args.date, style=args.style, custom_styles=custom_styles)
    print(text)


def _cmd_stats(args: argparse.Namespace) -> None:
    from collections import Counter
    from . import db
    day = args.date or date.today().strftime("%Y-%m-%d")
    rows = db.activities_for_day(day)
    if not rows:
        print(f"{day} 暂无记录。")
        return
    cats = Counter(r["category"] for r in rows)
    total = sum(cats.values())
    print(f"📊 {day} 共 {total} 条活动：")
    for cat, n in cats.most_common():
        bar = "█" * round(n / total * 20)
        print(f"  {cat:<8} {n:>3}  {bar} {n/total*100:.0f}%")


def _cmd_panel(args: argparse.Namespace) -> None:
    from . import web
    web.run(host=args.host, port=args.port, open_browser=not args.no_open)


def _cmd_menubar(args: argparse.Namespace) -> None:
    from . import menubar
    menubar.run(host=args.host, port=args.port)


def _cmd_desktop(args: argparse.Namespace) -> None:
    if platform.system() != "Darwin":
        from . import web
        web.run(host=args.host, port=args.port, open_browser=True)
        return
    from . import desktop
    desktop.run(host=args.host, port=args.port)


def _cmd_autostart(args: argparse.Namespace) -> None:
    from . import autostart
    if args.action == "install":
        path = autostart.install(host=args.host, port=args.port)
        print(f"已安装开机自启：{path}")
    elif args.action == "uninstall":
        path = autostart.uninstall()
        print(f"已卸载开机自启：{path}")
    else:
        info = autostart.status()
        print(f"Label: {info['label']}")
        print(f"Plist: {info['plist']}")
        print(f"Installed: {info['installed']}")
        print(f"Loaded: {info['loaded']}")


def _cmd_package_app(args: argparse.Namespace) -> None:
    from . import packager
    if args.write_env:
        env_path = packager.write_env_template()
        print(f"环境变量模板：{env_path}")
    app_path = packager.build(output_dir=args.output, mode=args.mode, portable=args.portable)
    print(f"已生成应用：{app_path}")


def _cmd_install_app(args: argparse.Namespace) -> None:
    from . import packager
    if args.write_env:
        env_path = packager.write_env_template()
        print(f"环境变量模板：{env_path}")
    app_path = packager.install_app(
        source=args.source,
        target_dir=args.target,
        mode=args.mode,
        portable=args.portable,
        replace=not args.no_replace,
    )
    print(f"已安装应用：{app_path}")


def _cmd_package_windows(args: argparse.Namespace) -> None:
    from . import packager
    zip_path = packager.build_windows_portable(output_dir=args.output)
    print(f"已生成 Windows 便携包：{zip_path}")


def _cmd_write_env(_args: argparse.Namespace) -> None:
    from . import packager
    path = packager.write_env_template(
        api_key=_args.api_key,
        base_url=_args.base_url,
        model=_args.model,
        provider=_args.provider,
        overwrite=_args.force,
    )
    print(f"环境变量模板：{path}")


def main() -> None:
    p = argparse.ArgumentParser(prog="riji", description="书赫日报助手")
    p.add_argument("--version", action="version", version=f"riji {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("watch", help="启动后台记录（截图+识别）").set_defaults(func=_cmd_watch)

    pp = sub.add_parser("panel", help="启动本地可视化面板")
    pp.add_argument("--host", default="127.0.0.1")
    pp.add_argument("--port", type=int, default=8765)
    pp.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    pp.set_defaults(func=_cmd_panel)

    mp = sub.add_parser("menubar", help="启动 macOS 菜单栏常驻助手")
    mp.add_argument("--host", default="127.0.0.1")
    mp.add_argument("--port", type=int, default=8765)
    mp.set_defaults(func=_cmd_menubar)

    dp = sub.add_parser("desktop", help="启动 macOS 原生桌面窗口")
    dp.add_argument("--host", default="127.0.0.1")
    dp.add_argument("--port", type=int, default=8765)
    dp.set_defaults(func=_cmd_desktop)

    ap = sub.add_parser("autostart", help="管理 macOS 开机自启")
    ap.add_argument("action", choices=["install", "uninstall", "status"])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.set_defaults(func=_cmd_autostart)

    bp = sub.add_parser("package-app", help="生成可双击打开的 macOS .app")
    bp.add_argument("--output", default="/Users/shuhe/临时文件")
    bp.add_argument("--mode", choices=["desktop", "menubar", "panel"], default="desktop")
    bp.add_argument("--portable", action="store_true", help="把源码和当前依赖打进 .app，便于拷到其他 Mac")
    bp.add_argument("--write-env", action="store_true", help="同时生成 ~/.xiaohei-riji/env.sh 模板")
    bp.set_defaults(func=_cmd_package_app)

    ip = sub.add_parser("install-app", help="安装 macOS .app 到应用目录")
    ip.add_argument("--source", help="已有 .app 路径；不填则先生成再安装")
    ip.add_argument("--target", default="~/Applications", help="安装目录，默认 ~/Applications")
    ip.add_argument("--mode", choices=["desktop", "menubar", "panel"], default="desktop")
    ip.add_argument("--portable", action="store_true", help="未指定 --source 时生成独立版 .app")
    ip.add_argument("--no-replace", action="store_true", help="目标存在时不覆盖")
    ip.add_argument("--write-env", action="store_true", help="同时生成 ~/.xiaohei-riji/env.sh 模板")
    ip.set_defaults(func=_cmd_install_app)

    wp = sub.add_parser("package-windows", help="生成 Windows 便携 zip 包")
    wp.add_argument("--output", default="/Users/shuhe/临时文件")
    wp.set_defaults(func=_cmd_package_windows)

    ep = sub.add_parser("write-env", help="生成 Finder/自启使用的本地环境变量文件")
    ep.add_argument("--api-key", help="保存到 macOS 钥匙串；非 macOS 可手动写入 env.sh")
    ep.add_argument("--base-url", default="http://localhost:55021/v1", help="OpenAI-compatible base URL")
    ep.add_argument("--model", default="gpt-5.5", help="OpenAI-compatible 模型名")
    ep.add_argument("--provider", default="openai", choices=["openai", "ollama"], help="模型后端")
    ep.add_argument("--force", action="store_true", help="覆盖已有 env.sh")
    ep.set_defaults(func=_cmd_write_env)

    rp = sub.add_parser("report", help="生成日报/周报/月报")
    rp.add_argument("kind", choices=["day", "week", "month"])
    rp.add_argument("--date", help="YYYY-MM-DD，默认今天（周/月报为结束日）")
    rp.add_argument("--style", default="标准", help="报告风格，可使用面板里的自定义报告模板名")
    rp.set_defaults(func=_cmd_report)

    sp = sub.add_parser("stats", help="看某天的活动分布")
    sp.add_argument("--date", help="YYYY-MM-DD，默认今天")
    sp.set_defaults(func=_cmd_stats)

    args = p.parse_args()
    config.ensure_dirs()
    args.func(args)


if __name__ == "__main__":
    main()
