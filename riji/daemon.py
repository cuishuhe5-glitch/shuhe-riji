"""后台采集循环：定时截图 → 变化检测 → 闲置暂停 → 本地识别 → 存库。"""

import time
from datetime import datetime

from . import capture, config, db, recognize, settings, storage, window


def run() -> None:
    config.ensure_dirs()
    initial = settings.load()
    scope_label = "全部显示器" if initial["capture_scope"] == "all" else "主显示器"
    print(f"[riji] 开始记录，每 {initial['capture_interval']}s 抓一次（{scope_label}）。Ctrl+C 停止。")
    print(f"[riji] 数据目录：{config.DATA_DIR}")
    prev = None
    idle_since = None

    while True:
        try:
            now = datetime.now()
            runtime = settings.load()
            win = window.frontmost()
            ignored, reason = settings.should_ignore(win.app, win.title, runtime)
            if ignored:
                print(f"[{now:%H:%M:%S}] {reason}，跳过")
                time.sleep(runtime["capture_interval"])
                continue

            img = capture.grab(runtime["capture_scope"])
            ratio = capture.diff_ratio(prev, img)
            prev = img

            # 画面几乎没变 → 可能闲置，跳过识别省算力
            if ratio < config.CHANGE_THRESHOLD:
                idle_since = idle_since or now
                idle_secs = (now - idle_since).total_seconds()
                if idle_secs >= runtime["idle_pause_after"]:
                    print(f"[{now:%H:%M:%S}] 闲置中（画面无变化 {int(idle_secs)}s），跳过")
                else:
                    print(f"[{now:%H:%M:%S}] 变化很小（{ratio:.1%}），跳过识别")
                time.sleep(runtime["capture_interval"])
                continue

            idle_since = None
            shot_path = capture.save_shot(img, now, keep=runtime["keep_shots"])
            rec = recognize.recognize(capture.to_jpeg_bytes(img), categories=runtime["activity_categories"])
            app_name = win.app or rec["app"]
            db.add_activity(
                category=rec["category"], summary=rec["summary"],
                app=app_name, window_title=win.title, shot_path=shot_path, ts=now,
            )
            if runtime["keep_shots"]:
                storage.prune_old_shots(runtime["shot_retention_days"])
            app = f"[{app_name}] " if app_name else ""
            print(f"[{now:%H:%M:%S}] {rec['category']} {app}→ {rec['summary']}")

        except KeyboardInterrupt:
            print("\n[riji] 已停止记录。")
            break
        except Exception as e:  # 单次失败不该让整个采集挂掉
            print(f"[riji] 本轮出错（已跳过）：{e}")

        time.sleep(settings.load()["capture_interval"])
