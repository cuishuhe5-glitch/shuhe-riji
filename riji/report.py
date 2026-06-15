"""把记录下来的活动汇总，调本地文本模型生成日报/周报/月报。"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Iterable

import requests

from . import config, db, llm, timeline

# 报告风格模板（标准/简洁/技术/OKR/复盘/管理汇报等）
STYLES = {
    "标准": "分『今日工作』『进展与产出』『明日计划』三部分，条理清晰，书面但不啰嗦。",
    "简洁": "用 3~6 条要点概括，每条一句话，不展开。",
    "技术": "突出技术细节、模块、遇到的问题与解决方案，面向技术同事。",
    "OKR": "按 Objective / Key Results 组织，量化产出，对齐目标。",
    "复盘": "按『事实』『判断』『问题/风险』『下一步』组织，突出可复用经验和阻塞。",
    "管理汇报": "面向上级，突出产出、进度、风险、需要支持事项，语气正式克制。",
    "成果导向": "以业务成果和价值输出为核心，弱化流水账；先写结果，再写支撑动作、指标变化、风险和明日最重要事项。",
    "会议驱动": "围绕会议、决策、行动项和跨部门协作展开，明确谁负责、下一步动作、截止时间和需要跟进的阻塞。",
    "三句话": "只输出三句话：今天完成了什么、当前最重要的进展/问题、明天第一件事。",
    "老板一分钟": "面向管理者快速阅读，控制在一分钟内读完；突出关键成果、风险、需要支持事项。",
    "TOP3": "只保留今天最重要的三件事，每件事包含进展、价值和下一步。",
    "项目推进": "按项目/模块组织，突出当前进度、已完成事项、风险、依赖和下一步里程碑。",
    "开发者": "面向研发日报，突出代码、调试、架构、测试、上线、技术债和待解决问题。",
    "产品运营": "面向产品/运营/增长岗位，突出用户反馈、需求推进、数据变化、活动执行和复盘结论。",
    "设计工作": "面向设计工作汇报，突出方案产出、评审反馈、视觉/交互调整和后续交付。",
    "工作成果": "从全天记录中提炼可对外同步的成果，按成果、价值、证据和下一步组织，减少过程流水账。",
    "今日亮点": "只提炼当天最值得被看见的亮点，突出关键突破、重要协作、可复用经验和一句话总结。",
    "进展日报": "强调任务推进状态，按已推进、进行中、阻塞、下一步拆分，适合持续项目同步。",
    "周会风格": "写成可直接发到团队群或周会材料里的版本，语言自然，重点清楚，包含进度、风险和需要协同。",
    "一句话": "只输出一句完整日报，包含今天最关键的工作、结果和明天方向，不超过 60 字。",
    "运营增长": "面向运营、增长和内容团队，突出活动执行、用户/流量/转化反馈、素材迭代和复盘动作。",
    "管理者": "面向团队负责人，突出团队推进、关键决策、资源协调、风险判断和管理动作。",
    "周会同步": "按周会同步口径组织，包含本期进展、关键结果、风险/依赖、下期计划，适合复制到会议纪要。",
    "下班发送": "写成下班前可直接发送的轻量日报，语气简洁自然，突出完成事项、未完事项和明日安排。",
    "详细工作": "生成较完整的工作日报，覆盖背景、主要工作、产出、问题、协作、风险和明日计划。",
}

STYLE_META = {
    "标准": {"group": "内置", "audience": "通用汇报", "preview": "今日工作\n- ...\n\n进展与产出\n- ...\n\n明日计划\n- ..."},
    "简洁": {"group": "内置", "audience": "快速同步", "preview": "- 完成 ...\n- 推进 ...\n- 明日 ..."},
    "技术": {"group": "岗位", "audience": "研发 / 技术团队", "preview": "技术进展\n- 模块：...\n问题与处理\n- ...\n下一步\n- ..."},
    "OKR": {"group": "管理", "audience": "目标复盘", "preview": "Objective\n- ...\nKey Results\n- KR1: ...\n风险\n- ..."},
    "复盘": {"group": "管理", "audience": "问题复盘", "preview": "事实\n- ...\n判断\n- ...\n问题/风险\n- ...\n下一步\n- ..."},
    "管理汇报": {"group": "管理", "audience": "上级 / 管理层", "preview": "核心产出\n- ...\n风险与支持\n- ...\n明日重点\n- ..."},
    "成果导向": {"group": "场景", "audience": "管理者 / 销售 / 运营", "preview": "今日核心成果\n- 成果一：...\n关键指标变化\n- ...\n风险与阻塞\n- ..."},
    "会议驱动": {"group": "场景", "audience": "项目 / 产品 / 协作", "preview": "会议与决策\n- ...\n行动项\n- 负责人 / 截止时间\n待跟进\n- ..."},
    "三句话": {"group": "极简", "audience": "下班快速发送", "preview": "1. 今天主要完成 ...\n2. 当前关键进展/问题是 ...\n3. 明天优先处理 ..."},
    "老板一分钟": {"group": "极简", "audience": "老板 / 客户", "preview": "一句话总结：...\n关键成果：...\n风险/需要支持：..."},
    "TOP3": {"group": "极简", "audience": "重点同步", "preview": "TOP1 ...\nTOP2 ...\nTOP3 ..."},
    "项目推进": {"group": "场景", "audience": "研发 / 产品 / PMO", "preview": "项目 A\n- 进度：...\n- 风险：...\n项目 B\n- 下一步：..."},
    "开发者": {"group": "岗位", "audience": "前端 / 后端 / AI / 运维", "preview": "代码与实现\n- ...\n调试/测试\n- ...\n技术风险\n- ..."},
    "产品运营": {"group": "岗位", "audience": "产品 / 运营 / 增长", "preview": "需求/活动推进\n- ...\n数据与反馈\n- ...\n明日动作\n- ..."},
    "设计工作": {"group": "岗位", "audience": "UI / 视觉 / 交互", "preview": "设计产出\n- ...\n评审反馈\n- ...\n交付计划\n- ..."},
    "工作成果": {"group": "场景", "audience": "领导 / 客户 / 团队", "preview": "成果一\n- 价值：...\n- 证据：...\n下一步\n- ..."},
    "今日亮点": {"group": "极简", "audience": "亮点提炼", "preview": "今日亮点\n- ...\n为什么重要\n- ...\n一句话总结\n- ..."},
    "进展日报": {"group": "场景", "audience": "项目持续同步", "preview": "已推进\n- ...\n进行中\n- ...\n阻塞\n- ...\n下一步\n- ..."},
    "周会风格": {"group": "场景", "audience": "团队周会 / 群同步", "preview": "本日进展\n- ...\n需要协同\n- ...\n风险\n- ..."},
    "一句话": {"group": "极简", "audience": "极简发送", "preview": "今天完成了 ...，当前重点是 ...，明天会优先 ...。"},
    "运营增长": {"group": "岗位", "audience": "运营 / 内容 / 增长", "preview": "活动/内容执行\n- ...\n数据反馈\n- ...\n复盘动作\n- ..."},
    "管理者": {"group": "岗位", "audience": "负责人 / 总监", "preview": "团队推进\n- ...\n关键决策\n- ...\n资源/风险\n- ..."},
    "周会同步": {"group": "场景", "audience": "周会材料", "preview": "本期进展\n- ...\n关键结果\n- ...\n风险/依赖\n- ...\n下期计划\n- ..."},
    "下班发送": {"group": "极简", "audience": "下班前同步", "preview": "今日完成\n- ...\n未完事项\n- ...\n明日安排\n- ..."},
    "详细工作": {"group": "场景", "audience": "完整工作日报", "preview": "背景\n- ...\n主要工作\n- ...\n产出\n- ...\n问题与计划\n- ..."},
}

STYLE_ALIASES = {
    "okr": "OKR",
}


def available_styles(custom_styles: dict[str, str] | None = None) -> dict[str, str]:
    return {**STYLES, **(custom_styles or {})}


def style_catalog(custom_styles: dict[str, str] | None = None) -> list[dict[str, str]]:
    styles = available_styles(custom_styles)
    catalog = []
    for name, prompt in styles.items():
        meta = STYLE_META.get(name, {})
        custom = name not in STYLES
        catalog.append(
            {
                "name": name,
                "prompt": prompt,
                "group": "自定义" if custom else meta.get("group", "内置"),
                "audience": meta.get("audience", "自定义模板" if custom else "通用"),
                "preview": meta.get("preview", prompt),
                "source": "自定义" if custom else "内置",
            }
        )
    return catalog


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
