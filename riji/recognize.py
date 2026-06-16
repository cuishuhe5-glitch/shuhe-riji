"""调用本地模型网关，识别一张截图里"用户在干嘛"。

输出结构化结果 {category, summary, app}，全程本地，截图不出门。
"""

from __future__ import annotations

import base64
import json
import re
from typing import Optional, TypedDict

import requests

from . import config, llm


class Recognition(TypedDict):
    category: str
    summary: str
    app: Optional[str]


_PROMPT = (
    "你是一个工作记录助手。下面是用户某一刻的电脑屏幕截图。"
    "请判断用户当时在做什么工作，只关注屏幕主要内容，忽略壁纸、状态栏等无关元素。\n"
    "必须严格返回 JSON，不要任何额外文字，格式：\n"
    '{{"category": "<从给定分类里选一个>", "summary": "<不超过30字的一句话描述>", "app": "<主要应用名，看不出填null>"}}\n'
    "可选分类（category 只能是其中之一）：{cats}"
)


def _extract_json(text: str) -> dict:
    """模型偶尔会带点废话，宽松地抠出第一个 JSON 对象。"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {}


def recognize(jpeg_bytes: bytes, timeout: int = 120, categories: list[str] | None = None) -> Recognition:
    """把截图丢给本地视觉模型，返回识别结果。失败则归到'其他'。"""
    categories = categories or config.CATEGORIES
    b64 = base64.b64encode(jpeg_bytes).decode()
    prompt = _PROMPT.format(cats="、".join(categories))
    try:
        text = llm.openai_chat_completion(
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64}",
                                "detail": "low",
                            },
                        },
                    ],
                }
            ],
            config.VISION_MODEL,
            timeout=timeout,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        data = _extract_json(text)
    except (requests.RequestException, ValueError) as e:
        return {"category": "其他", "summary": f"识别失败：{e}", "app": None}
    except RuntimeError as e:
        return {"category": "其他", "summary": f"识别失败：{e}", "app": None}

    category = data.get("category", "其他")
    if category not in categories:
        category = "其他"
    summary = (data.get("summary") or "").strip() or "（无描述）"
    app = data.get("app")
    if app in ("null", "None", ""):
        app = None
    return {"category": category, "summary": summary, "app": app}
