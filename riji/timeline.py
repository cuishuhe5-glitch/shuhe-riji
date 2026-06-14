"""Timeline grouping helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def build_segments(items: list[dict[str, Any]], gap_minutes: int = 8) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    gap = timedelta(minutes=gap_minutes)

    for item in items:
        ts = _parse_ts(item["ts"])
        if current is None or not _same_segment(current, item, ts, gap):
            current = _new_segment(item, ts)
            segments.append(current)
            continue
        current["end_ts"] = item["ts"]
        current["end_time"] = item["time"]
        current["count"] += 1
        current["items"].append(item)
        current["summaries"].append(item["summary"])
        current["latest_shot_url"] = item.get("shot_url") or current["latest_shot_url"]
        current["duration_minutes"] = max(1, round((_parse_ts(current["end_ts"]) - _parse_ts(current["start_ts"])).total_seconds() / 60))
    return segments


def _same_segment(current: dict[str, Any], item: dict[str, Any], ts: datetime, gap: timedelta) -> bool:
    last_ts = _parse_ts(current["end_ts"])
    return (
        item.get("app", "") == current.get("app", "")
        and item.get("category", "") == current.get("category", "")
        and ts - last_ts <= gap
    )


def _new_segment(item: dict[str, Any], ts: datetime) -> dict[str, Any]:
    return {
        "id": f"seg-{item['id']}",
        "start_ts": item["ts"],
        "end_ts": item["ts"],
        "start_time": item["time"],
        "end_time": item["time"],
        "day": item["day"],
        "category": item["category"],
        "app": item.get("app", ""),
        "window_title": item.get("window_title", ""),
        "summary": item["summary"],
        "summaries": [item["summary"]],
        "count": 1,
        "duration_minutes": 1,
        "latest_shot_url": item.get("shot_url", ""),
        "items": [item],
    }


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value)
