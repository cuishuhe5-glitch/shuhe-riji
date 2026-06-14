"""截图 + 变化检测。跨平台：mss 抓全屏，Pillow 压缩并算帧间差异。"""

import io
from datetime import datetime
from pathlib import Path
from typing import Optional

import mss
from PIL import Image, ImageChops

from . import config


def grab(mode: str = "primary") -> Image.Image:
    """抓屏幕，mode=primary 抓主屏；mode=all 抓全部显示器拼合图。"""
    with mss.mss() as sct:
        mon = _monitor_for_mode(sct.monitors, mode)
        raw = sct.grab(mon)
        img = Image.frombytes("RGB", raw.size, raw.rgb)
    img.thumbnail((config.THUMB_MAX_EDGE, config.THUMB_MAX_EDGE))
    return img


def grab_primary() -> Image.Image:
    """抓主显示器，返回压缩后的 RGB 图。"""
    return grab("primary")


def displays() -> list[dict[str, object]]:
    """Return connected monitor metadata. Index 0 is the virtual all-displays monitor."""
    with mss.mss() as sct:
        result = []
        for idx, mon in enumerate(sct.monitors):
            result.append(
                {
                    "index": idx,
                    "scope": "all" if idx == 0 else ("primary" if idx == 1 else f"display:{idx}"),
                    "name": "全部显示器" if idx == 0 else ("主显示器" if idx == 1 else f"显示器 {idx}"),
                    "width": int(mon.get("width", 0)),
                    "height": int(mon.get("height", 0)),
                    "left": int(mon.get("left", 0)),
                    "top": int(mon.get("top", 0)),
                    "primary": idx == 1,
                }
            )
        return result


def _monitor_for_mode(monitors: list[dict[str, int]], mode: str) -> dict[str, int]:
    if mode == "all":
        return monitors[0]
    if mode.startswith("display:"):
        try:
            idx = int(mode.split(":", 1)[1])
        except ValueError:
            idx = 1
        if 1 <= idx < len(monitors):
            return monitors[idx]
    return monitors[1]


def diff_ratio(a: Optional[Image.Image], b: Image.Image) -> float:
    """两帧差异比例 0~1。a 为空（首帧）时返回 1.0 强制识别。"""
    if a is None:
        return 1.0
    if a.size != b.size:
        a = a.resize(b.size)
    # 转灰度算逐像素差，归一化到 0~1
    diff = ImageChops.difference(a.convert("L"), b.convert("L"))
    hist = diff.histogram()
    total = sum(hist)
    if total == 0:
        return 0.0
    # 把"亮度差 > 24 的像素占比"作为变化度，抗噪点
    changed = sum(hist[25:])
    return changed / total


def save_shot(img: Image.Image, ts: Optional[datetime] = None, keep: Optional[bool] = None) -> Optional[str]:
    """保存截图到本地，返回路径；KEEP_SHOT_FILES 关闭时返回 None。"""
    if keep is None:
        keep = config.KEEP_SHOT_FILES
    if not keep:
        return None
    ts = ts or datetime.now()
    config.ensure_dirs()
    path = config.SHOTS_DIR / f"{ts.strftime('%Y%m%d-%H%M%S')}.jpg"
    img.save(path, "JPEG", quality=70)
    return str(path)


def to_jpeg_bytes(img: Image.Image) -> bytes:
    """编码成 JPEG 字节，喂给视觉模型用。"""
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return buf.getvalue()
