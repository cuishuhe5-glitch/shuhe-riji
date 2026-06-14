"""把记录下来的活动汇总，调本地文本模型生成日报/周报/月报。"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Iterable

import requests

from . import config, db, llm, timeline

# 报告风格模板（标准/简洁/技术/OKR/复盘/管理汇报）
STYLES = {
    "标准": "分『今日工作』『进展与产出』『明日计划』三部分，条理清晰，书面但不啰嗦。",
    "简洁": "用 3~6 条要点概括，每条一句话，不展开。",
    "技术": "突出技术细节、模块、遇到的问题与解决方案，面向技术同事。",
    "OKR": "按 Objective / Key Results 组织，量化产出，对齐目标。",
    "复盘": "按『事实』『判断』『问题/风险』『下一步』组织，突出可复用经验和阻塞。",
    "管理汇报": "面向上级，突出产出、进度、风险、需要支持事项，语气正式克制。",
}

STYLE_ALIASES = {
    "okr": "OKR",
}


def available_styles(custom_styles: dict[str, str] | None = None) -> dict[str, str]:
    return {**STYLES, **(custom_styles or {})}


def normalize_style(style: str | None, custom_styles: dict[str, str] | None = None) -> str:
    if not style:
        return "标准"
    styles = available_styles(custom_styles)
    if style in styles:
        return style
    alias = STYLE_ALIASES.get(style.strip().lower())
    return alias if alias in styles else style


def _stats(rows: Iterable[db.sqlite3.Row]) -> tuple[Counter, int]:
    """统计各分类条数（≈时长占比）和总条数。"""
    cats = Counter(r["category"] for r in rows)
    return cats, sum(cats.values())


def _build_context(rows: list, period_label: str) -> str:
    """把活动条目压成喂给文本模型的素材。"""
    cats, total = _stats(rows)
    if total == 0:
        return ""
    items = [_row_to_item(row) for row in rows]
    segments = timeline.build_segments(items)
    lines = [f"统计周期：{period_label}", f"共记录 {total} 条工作活动。", "", "分类分布："]
    for cat, n in cats.most_common():
        lines.append(f"  - {cat}: {n} 次（约 {n / total * 100:.0f}%）")
    lines.append("\n应用用时估算：")
    for app in _app_usage(segments):
        lines.append(
            f"  - {app['name']}: {app['label']}（约 {app['percent']}%，{app['count']} 条，主要为 {app['top_category']}）"
        )
    lines.append("\n连续工作段落：")
    for seg in segments:
        title = f"《{seg['window_title']}》" if seg.get("window_title") else ""
        app = seg.get("app") or "未知应用"
        lines.append(
            f"  - {seg['start_time']}-{seg['end_time']} [{app}{title}] "
            f"{seg['category']}，约 {seg['duration_minutes']} 分钟：{seg['summary']}"
        )
    lines.append("\n时间线明细：")
    for r in rows:
        t = r["ts"][11:16]  # 取 HH:MM
        title = ""
        if "window_title" in r.keys() and r["window_title"]:
            title = f"《{r['window_title']}》"
        app = f"[{r['app']}{title}] " if r["app"] else (f"[{title}] " if title else "")
        lines.append(f"  {t} {app}{r['category']}：{r['summary']}")
    return "\n".join(lines)


def _notes_context(start_day: str, end_day: str | None = None) -> str:
    end_day = end_day or start_day
    notes: list[str] = []
    if start_day == end_day:
        row = db.day_note(start_day)
        if row and row["note"]:
            notes.append(f"  - {start_day}: {row['note']}")
    else:
        current = datetime.strptime(start_day, "%Y-%m-%d").date()
        end = datetime.strptime(end_day, "%Y-%m-%d").date()
        while current <= end:
            day = current.strftime("%Y-%m-%d")
            row = db.day_note(day)
            if row and row["note"]:
                notes.append(f"  - {day}: {row['note']}")
            current += timedelta(days=1)
    if not notes:
        return ""
    return "\n用户备注 / 计划：\n" + "\n".join(notes)


def _row_to_item(row: db.sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "ts": row["ts"],
        "time": row["ts"][11:16],
        "day": row["day"],
        "category": row["category"],
        "summary": row["summary"],
        "app": row["app"] or "",
        "window_title": row["window_title"] if "window_title" in row.keys() and row["window_title"] else "",
        "shot_url": "",
    }


def _app_usage(segments: list[dict]) -> list[dict]:
    usage: dict[str, dict] = {}
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
            },
        )
        item["minutes"] += minutes
        item["count"] += int(seg.get("count") or 1)
        item["categories"][seg.get("category") or "其他"] += minutes
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
    return sorted(result, key=lambda entry: (-entry["minutes"], entry["name"]))[:10]


def _format_minutes(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} 分钟"
    hours, mins = divmod(minutes, 60)
    return f"{hours} 小时 {mins} 分钟" if mins else f"{hours} 小时"


def _generate(
    context: str,
    period: str,
    style: str,
    instruction: str = "",
    timeout: int = 180,
    custom_styles: dict[str, str] | None = None,
) -> str:
    styles = available_styles(custom_styles)
    style = normalize_style(style, custom_styles)
    style_hint = styles.get(style, styles["标准"])
    instruction_hint = f"\n用户补充要求：{instruction.strip()}" if instruction.strip() else ""
    prompt = (
        f"你是用户的工作助理。下面是 ta 这段时间（{period}）的电脑活动记录，"
        f"请据此写一份{period}。要求：{style_hint}{instruction_hint}\n"
        "只输出报告正文，不要解释、不要复述原始记录。如果某类活动占比很低可合并或略写。\n\n"
        f"=== 活动记录 ===\n{context}\n=== 记录结束 ==="
    )
    if config.LLM_PROVIDER == "openai":
        return llm.openai_chat_completion(
            [{"role": "user", "content": prompt}],
            config.TEXT_MODEL,
            timeout=timeout,
            temperature=0.4,
        )

    payload = {
        "model": config.TEXT_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.4},
    }
    resp = requests.post(
        f"{config.OLLAMA_HOST}/api/generate", json=payload, timeout=timeout
    )
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


def daily_report(
    day: str | None = None,
    style: str = "标准",
    instruction: str = "",
    custom_styles: dict[str, str] | None = None,
) -> str:
    day = day or date.today().strftime("%Y-%m-%d")
    rows = db.activities_for_day(day)
    ctx = _build_context(rows, f"{day} 当天")
    if not ctx:
        return f"{day} 没有记录到任何活动，写不了日报哦。"
    notes = _notes_context(day)
    if notes:
        ctx = f"{ctx}\n{notes}"
    return _generate(ctx, "日报", style, instruction=instruction, custom_styles=custom_styles)


def range_report(
    start_day: str,
    end_day: str,
    kind: str,
    style: str = "标准",
    instruction: str = "",
    custom_styles: dict[str, str] | None = None,
) -> str:
    rows = db.activities_between(start_day, end_day)
    ctx = _build_context(rows, f"{start_day} ~ {end_day}")
    if not ctx:
        return f"{start_day} ~ {end_day} 没有记录，写不了{kind}。"
    notes = _notes_context(start_day, end_day)
    if notes:
        ctx = f"{ctx}\n{notes}"
    return _generate(ctx, kind, style, instruction=instruction, custom_styles=custom_styles)


def weekly_report(
    end_day: str | None = None,
    style: str = "标准",
    instruction: str = "",
    custom_styles: dict[str, str] | None = None,
) -> str:
    end = datetime.strptime(end_day, "%Y-%m-%d").date() if end_day else date.today()
    start = end - timedelta(days=6)
    return range_report(
        start.strftime("%Y-%m-%d"),
        end.strftime("%Y-%m-%d"),
        "周报",
        style,
        instruction=instruction,
        custom_styles=custom_styles,
    )


def monthly_report(
    end_day: str | None = None,
    style: str = "标准",
    instruction: str = "",
    custom_styles: dict[str, str] | None = None,
) -> str:
    end = datetime.strptime(end_day, "%Y-%m-%d").date() if end_day else date.today()
    start = end - timedelta(days=29)
    return range_report(
        start.strftime("%Y-%m-%d"),
        end.strftime("%Y-%m-%d"),
        "月报",
        style,
        instruction=instruction,
        custom_styles=custom_styles,
    )
