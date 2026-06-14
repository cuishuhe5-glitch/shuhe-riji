"""Runtime settings stored next to the local database."""

from __future__ import annotations

import json
from typing import Any

from . import config

SETTINGS_PATH = config.DATA_DIR / "settings.json"

DEFAULTS: dict[str, Any] = {
    "privacy_mode": True,
    "keep_shots": config.KEEP_SHOT_FILES,
    "shot_retention_days": 7,
    "capture_interval": config.CAPTURE_INTERVAL,
    "idle_pause_after": config.IDLE_PAUSE_AFTER,
    "capture_scope": "primary",
    "auto_record_enabled": False,
    "auto_report_enabled": False,
    "auto_report_time": "18:30",
    "auto_report_style": "标准",
    "auto_report_last_day": "",
    "activity_categories": config.CATEGORIES,
    "work_categories": config.CATEGORIES[:8],
    "custom_report_styles": {},
    "project_paths": [],
    "ignore_apps": ["1Password", "Keychain Access", "钥匙串访问"],
    "ignore_keywords": ["密码", "验证码", "银行", "支付", "身份证"],
}


def load() -> dict[str, Any]:
    config.ensure_dirs()
    data: dict[str, Any] = {}
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    merged = {**DEFAULTS, **data}
    merged["shot_retention_days"] = _non_negative_int(merged.get("shot_retention_days"), 7)
    merged["capture_interval"] = _positive_int(merged.get("capture_interval"), config.CAPTURE_INTERVAL)
    merged["idle_pause_after"] = _positive_int(merged.get("idle_pause_after"), config.IDLE_PAUSE_AFTER)
    merged["privacy_mode"] = bool(merged.get("privacy_mode", True))
    merged["keep_shots"] = False if merged["privacy_mode"] else bool(merged.get("keep_shots"))
    merged["capture_scope"] = _capture_scope(merged.get("capture_scope"))
    merged["auto_record_enabled"] = bool(merged.get("auto_record_enabled"))
    merged["auto_report_enabled"] = bool(merged.get("auto_report_enabled"))
    merged["auto_report_time"] = _time_value(merged.get("auto_report_time"), "18:30")
    merged["auto_report_style"] = _text_value(merged.get("auto_report_style"), "标准")
    merged["auto_report_last_day"] = _text_value(merged.get("auto_report_last_day"), "")
    merged["activity_categories"] = _categories(merged.get("activity_categories"))
    merged["work_categories"] = _work_categories(merged.get("work_categories"), merged["activity_categories"])
    merged["custom_report_styles"] = _style_map(merged.get("custom_report_styles"))
    merged["project_paths"] = _project_paths(merged.get("project_paths"))
    merged["ignore_apps"] = _clean_list(merged.get("ignore_apps"))
    merged["ignore_keywords"] = _clean_list(merged.get("ignore_keywords"))
    return merged


def save(patch: dict[str, Any]) -> dict[str, Any]:
    current = load()
    allowed = {
        "privacy_mode",
        "keep_shots",
        "shot_retention_days",
        "capture_interval",
        "idle_pause_after",
        "capture_scope",
        "auto_record_enabled",
        "auto_report_enabled",
        "auto_report_time",
        "auto_report_style",
        "auto_report_last_day",
        "activity_categories",
        "work_categories",
        "custom_report_styles",
        "project_paths",
        "ignore_apps",
        "ignore_keywords",
    }
    for key in allowed:
        if key in patch:
            current[key] = patch[key]
    current["shot_retention_days"] = _non_negative_int(current.get("shot_retention_days"), 7)
    current["capture_interval"] = _positive_int(current.get("capture_interval"), config.CAPTURE_INTERVAL)
    current["idle_pause_after"] = _positive_int(current.get("idle_pause_after"), config.IDLE_PAUSE_AFTER)
    current["privacy_mode"] = bool(current.get("privacy_mode", True))
    current["keep_shots"] = False if current["privacy_mode"] else bool(current.get("keep_shots"))
    current["capture_scope"] = _capture_scope(current.get("capture_scope"))
    current["auto_record_enabled"] = bool(current.get("auto_record_enabled"))
    current["auto_report_enabled"] = bool(current.get("auto_report_enabled"))
    current["auto_report_time"] = _time_value(current.get("auto_report_time"), "18:30")
    current["auto_report_style"] = _text_value(current.get("auto_report_style"), "标准")
    current["auto_report_last_day"] = _text_value(current.get("auto_report_last_day"), "")
    current["activity_categories"] = _categories(current.get("activity_categories"))
    current["work_categories"] = _work_categories(current.get("work_categories"), current["activity_categories"])
    current["custom_report_styles"] = _style_map(current.get("custom_report_styles"))
    current["project_paths"] = _project_paths(current.get("project_paths"))
    current["ignore_apps"] = _clean_list(current.get("ignore_apps"))
    current["ignore_keywords"] = _clean_list(current.get("ignore_keywords"))
    config.ensure_dirs()
    SETTINGS_PATH.write_text(
        json.dumps(current, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return current


def should_ignore(app: str | None, title: str | None, runtime: dict[str, Any] | None = None) -> tuple[bool, str]:
    runtime = runtime or load()
    app_text = (app or "").casefold()
    title_text = (title or "").casefold()
    for item in runtime["ignore_apps"]:
        if item.casefold() and item.casefold() in app_text:
            return True, f"已跳过敏感应用：{item}"
    for item in runtime["ignore_keywords"]:
        needle = item.casefold()
        if needle and (needle in app_text or needle in title_text):
            return True, f"已跳过敏感窗口：{item}"
    return False, ""


def _clean_list(value: Any) -> list[str]:
    if isinstance(value, str):
        raw = value.replace("，", ",").split(",")
    elif isinstance(value, list):
        raw = value
    else:
        raw = []
    return [str(item).strip() for item in raw if str(item).strip()]


def _categories(value: Any) -> list[str]:
    items = []
    seen = set()
    for item in _clean_list(value) or config.CATEGORIES:
        name = str(item).strip()
        if not name or name in seen:
            continue
        items.append(name)
        seen.add(name)
    if "其他" not in seen:
        items.append("其他")
    return items[:30]


def _work_categories(value: Any, categories: list[str]) -> list[str]:
    allowed = set(categories)
    items = [item for item in _clean_list(value) if item in allowed]
    if items:
        return items
    fallback = [item for item in config.CATEGORIES[:8] if item in allowed]
    return fallback or [item for item in categories if item != "其他"] or categories[:1]


def _style_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for key, raw in value.items():
        name = str(key or "").strip()
        text = str(raw or "").strip()
        if name and text:
            result[name[:24]] = text[:800]
    return result


def _project_paths(value: Any) -> list[str]:
    result: list[str] = []
    for item in _clean_list(value):
        cleaned = item.rstrip("/")
        if cleaned and cleaned not in result:
            result.append(cleaned)
        if len(result) >= 5:
            break
    return result


def _positive_int(value: Any, fallback: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(5, min(number, 3600))


def _non_negative_int(value: Any, fallback: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(0, min(number, 3650))


def _capture_scope(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text == "all":
        return "all"
    if text.startswith("display:"):
        try:
            idx = int(text.split(":", 1)[1])
        except ValueError:
            return "primary"
        if idx == 1:
            return "primary"
        return f"display:{idx}" if idx >= 1 else "primary"
    return "primary"


def _time_value(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    parts = text.split(":")
    if len(parts) != 2:
        return fallback
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return fallback
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"
    return fallback


def _text_value(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    return text if text else fallback
