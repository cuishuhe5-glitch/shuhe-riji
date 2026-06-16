"""把记录下来的活动汇总，调本地文本模型生成日报/周报/月报。"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Iterable

import requests

from . import config, db, llm, timeline

# 报告风格模板。命名尽量贴近小黑日报助手，但生成仍完全走本地模型。
STYLES = {
    "成果导向日报": "以业务成果和价值输出为核心，弱化过程记录；先写核心成果，再写关键指标变化、推进中的重点事项、风险阻塞和明日最重要三件事。",
    "会议驱动日报": "适用于管理者、产品经理、项目经理及跨部门协作场景，重点记录会议决策、行动项、负责人、截止时间和推进结果。",
    "AI工作轨迹日报": "基于全天桌面活动记录自动生成，分析工作内容、时间分配、专注情况和工作成果，还原真实工作轨迹。",
    "工作成果日报": "从全天工作记录中提炼关键成果和进展，适合向领导、客户或团队同步；按成果、价值、证据和下一步组织。",
    "三句话日报": "只输出三句话：今天完成了什么、当前最重要的进展或问题、明天第一件事。",
    "今日亮点": "只提炼当天最值得汇报的成果，突出关键突破、重要协作、可复用经验和一句话总结。",
    "老板一分钟日报": "适合向管理层快速同步，控制在一分钟内读完；突出关键成果、风险和需要支持事项。",
    "TOP3日报": "只保留今天最重要的三件事，每件事包含进展、价值和下一步。",
    "进展日报": "强调任务推进情况，按已推进、进行中、阻塞、下一步拆分，适合持续项目同步。",
    "项目推进快照": "适合研发、产品、项目团队，按项目或模块组织，突出当前进度、已完成事项、风险、依赖和下一步里程碑。",
    "AI观察日报": "从第三方观察者视角总结一天的工作轨迹，客观指出投入、产出、协作和可优化之处。",
    "效率日报": "突出时间投入与产出，分析工作占比、最长专注、切换成本、低效时段和改进建议。",
    "周会风格日报": "写成可直接发到团队群或周会材料里的版本，语言自然，重点清楚，包含进度、风险和需要协同。",
    "一句话日报": "只输出一句完整日报，包含今天最关键的工作、结果和明天方向，不超过 60 字。",
    "开发者日报": "面向前端、后端、全栈、AI、运维、测试等研发岗位，突出代码、调试、架构、测试、上线、技术债和待解决问题。",
    "产品推进日报": "面向产品经理、项目经理、PMO，突出需求推进、评审结论、排期变化、协作阻塞和下一步动作。",
    "运营增长日报": "面向运营、电商运营、新媒体运营、小红书运营，突出活动执行、用户/流量/转化反馈、素材迭代和复盘动作。",
    "设计工作日报": "面向 UI、视觉、平面和交互设计，突出方案产出、评审反馈、视觉/交互调整和后续交付。",
    "管理者日报": "面向 CEO、总经理、总监、部门负责人，突出团队推进、关键决策、资源协调、风险判断和管理动作。",
    "周会同步版": "按周会同步口径组织，包含本期进展、关键结果、风险/依赖、下期计划，适合复制到会议纪要。",
    "下班发送版": "写成下班前可直接发送的轻量日报，语气简洁自然，突出完成事项、未完事项和明日安排。",
    "摸鱼克星日报": "用轻松但不冒犯的口吻复盘当天专注与分心情况，指出低效时段、原因猜测和明日改善动作。",
    "番茄钟聚类": "非时间线报告工作类型聚类，按工作类型汇总投入、产出、切换和建议，适合复盘节奏。",
    "简洁日报": "只列出关键工作，适合快速汇报；用 3~6 条要点概括，每条一句话。",
    "技术日报": "侧重代码开发和技术问题，突出技术细节、模块、遇到的问题与解决方案，面向技术同事。",
    "项目日报": "按项目维度组织工作内容，突出每个项目的进度、风险、依赖和下一步。",
    "标准日报": "按类别归纳今日已完成的工作，分『今日工作』『进展与产出』『明日计划』三部分，条理清晰。",
    "较详细工作日报": "适用于研发、产品、运营、销售等岗位的日常工作汇报，突出工作成果、问题及计划，覆盖背景、产出、协作和风险。",
}

STYLE_META = {
    "成果导向日报": {"group": "云端预制", "audience": "管理者 / 销售 / 运营", "preview": "今日核心成果\n- 成果一\n- 成果二\n关键指标变化\n- ...\n推进中的重点事项\n- 当前进度 / 下一步动作\n风险与阻塞\n- ...\n明日最重要的三件事\n- ..."},
    "会议驱动日报": {"group": "云端预制", "audience": "管理者 / 产品 / 项目", "preview": "会议与决策\n- ...\n行动项\n- 负责人 / 截止时间\n推进结果\n- ...\n待跟进\n- ..."},
    "AI工作轨迹日报": {"group": "云端预制", "audience": "全天轨迹复盘", "preview": "工作轨迹概览\n- ...\n时间分配\n- ...\n关键产出\n- ...\n专注情况\n- ..."},
    "工作成果日报": {"group": "云端预制", "audience": "领导 / 客户 / 团队", "preview": "成果一\n- 价值：...\n- 证据：...\n成果二\n- ...\n下一步\n- ..."},
    "三句话日报": {"group": "云端预制", "audience": "下班快速发送", "preview": "1. 今天主要完成 ...\n2. 当前关键进展/问题是 ...\n3. 明天优先处理 ..."},
    "今日亮点": {"group": "云端预制", "audience": "亮点提炼", "preview": "今日亮点\n- ...\n为什么重要\n- ...\n一句话总结\n- ..."},
    "老板一分钟日报": {"group": "云端预制", "audience": "老板 / 客户", "preview": "一分钟摘要\n- ...\n关键成果\n- ...\n风险/需要支持\n- ..."},
    "TOP3日报": {"group": "云端预制", "audience": "重点同步", "preview": "TOP1 ...\nTOP2 ...\nTOP3 ..."},
    "进展日报": {"group": "云端预制", "audience": "项目持续同步", "preview": "已推进\n- ...\n进行中\n- ...\n阻塞\n- ...\n下一步\n- ..."},
    "项目推进快照": {"group": "云端预制", "audience": "研发 / 产品 / PMO", "preview": "项目 A\n- 进度：...\n- 风险：...\n项目 B\n- 下一步：..."},
    "AI观察日报": {"group": "云端预制", "audience": "第三方视角", "preview": "观察摘要\n- ...\n投入与产出\n- ...\n可优化之处\n- ..."},
    "效率日报": {"group": "云端预制", "audience": "效率复盘", "preview": "时间投入\n- ...\n产出情况\n- ...\n低效时段\n- ...\n明日建议\n- ..."},
    "周会风格日报": {"group": "云端预制", "audience": "团队周会 / 群同步", "preview": "本日进展\n- ...\n需要协同\n- ...\n风险\n- ..."},
    "一句话日报": {"group": "云端预制", "audience": "极简发送", "preview": "今天完成了 ...，当前重点是 ...，明天会优先 ...。"},
    "开发者日报": {"group": "云端预制", "audience": "前端 / 后端 / AI / 运维 / 测试", "preview": "代码与实现\n- ...\n调试/测试\n- ...\n技术风险\n- ..."},
    "产品推进日报": {"group": "云端预制", "audience": "产品经理 / 项目经理 / PMO", "preview": "需求推进\n- ...\n评审/决策\n- ...\n风险与下一步\n- ..."},
    "运营增长日报": {"group": "云端预制", "audience": "运营 / 电商 / 新媒体", "preview": "活动/内容执行\n- ...\n数据反馈\n- ...\n复盘动作\n- ..."},
    "设计工作日报": {"group": "云端预制", "audience": "UI / 视觉 / 平面", "preview": "设计产出\n- ...\n评审反馈\n- ...\n交付计划\n- ..."},
    "管理者日报": {"group": "云端预制", "audience": "CEO / 总经理 / 总监 / 负责人", "preview": "团队推进\n- ...\n关键决策\n- ...\n资源/风险\n- ..."},
    "周会同步版": {"group": "云端预制", "audience": "周会材料", "preview": "本期进展\n- ...\n关键结果\n- ...\n风险/依赖\n- ...\n下期计划\n- ..."},
    "下班发送版": {"group": "云端预制", "audience": "下班前同步", "preview": "今日完成\n- ...\n未完事项\n- ...\n明日安排\n- ..."},
    "摸鱼克星日报": {"group": "云端预制", "audience": "专注复盘", "preview": "专注时段\n- ...\n分心时段\n- ...\n明日改善动作\n- ..."},
    "番茄钟聚类": {"group": "云端预制", "audience": "工作类型聚类", "preview": "工作类型一\n- 投入 / 产出\n工作类型二\n- 切换与建议\n复盘结论\n- ..."},
    "简洁日报": {"group": "内置", "audience": "快速同步", "preview": "- 完成 ...\n- 推进 ...\n- 明日 ..."},
    "技术日报": {"group": "内置", "audience": "研发 / 技术团队", "preview": "技术进展\n- 模块：...\n问题与处理\n- ...\n下一步\n- ..."},
    "项目日报": {"group": "内置", "audience": "项目维度汇报", "preview": "项目 A\n- 今日进展：...\n- 风险：...\n项目 B\n- 下一步：..."},
    "标准日报": {"group": "内置", "audience": "通用汇报", "preview": "今日工作\n- ...\n\n进展与产出\n- ...\n\n明日计划\n- ..."},
    "较详细工作日报": {"group": "云端预制", "audience": "研发 / 产品 / 运营 / 销售", "preview": "背景\n- ...\n主要工作\n- ...\n产出\n- ...\n问题与计划\n- ..."},
}

STYLE_ALIASES = {
    "okr": "标准日报",
    "标准": "标准日报",
    "简洁": "简洁日报",
    "技术": "技术日报",
    "项目": "项目日报",
    "成果导向": "成果导向日报",
    "会议驱动": "会议驱动日报",
    "三句话": "三句话日报",
    "老板一分钟": "老板一分钟日报",
    "TOP3": "TOP3日报",
    "top3": "TOP3日报",
    "项目推进": "项目推进快照",
    "开发者": "开发者日报",
    "产品运营": "运营增长日报",
    "设计工作": "设计工作日报",
    "工作成果": "工作成果日报",
    "周会风格": "周会风格日报",
    "一句话": "一句话日报",
    "运营增长": "运营增长日报",
    "管理者": "管理者日报",
    "周会同步": "周会同步版",
    "下班发送": "下班发送版",
    "详细工作": "较详细工作日报",
}


def available_styles(custom_styles: dict[str, str] | None = None) -> dict[str, str]:
    return {**STYLES, **(custom_styles or {})}


def style_catalog(custom_styles: dict[str, str] | None = None) -> list[dict[str, str]]:
    styles = available_styles(custom_styles)
    catalog = []
    for name, prompt in styles.items():
        meta = STYLE_META.get(name, {})
        custom = name not in STYLES
        group = "自定义" if custom else meta.get("group", "内置")
        source = "自定义" if custom else ("云端" if "云端" in group else "内置")
        catalog.append(
            {
                "name": name,
                "prompt": prompt,
                "group": group,
                "audience": meta.get("audience", "自定义模板" if custom else "通用"),
                "preview": meta.get("preview", prompt),
                "source": source,
            }
        )
    return catalog


def normalize_style(style: str | None, custom_styles: dict[str, str] | None = None) -> str:
    if not style:
        return "标准日报"
    styles = available_styles(custom_styles)
    if style in styles:
        return style
    stripped = style.strip()
    alias = STYLE_ALIASES.get(stripped) or STYLE_ALIASES.get(stripped.lower())
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
    style_hint = styles.get(style, styles["标准日报"])
    instruction_hint = f"\n用户补充要求：{instruction.strip()}" if instruction.strip() else ""
    prompt = (
        f"你是用户的工作助理。下面是 ta 这段时间（{period}）的电脑活动记录，"
        f"请据此写一份{period}。要求：{style_hint}{instruction_hint}\n"
        "只输出报告正文，不要解释、不要复述原始记录。如果某类活动占比很低可合并或略写。\n\n"
        f"=== 活动记录 ===\n{context}\n=== 记录结束 ==="
    )
    return llm.openai_chat_completion(
        [{"role": "user", "content": prompt}],
        config.TEXT_MODEL,
        timeout=timeout,
        temperature=0.4,
    )


def daily_report(
    day: str | None = None,
    style: str = "标准日报",
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
    style: str = "标准日报",
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
    style: str = "标准日报",
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
    style: str = "标准日报",
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
