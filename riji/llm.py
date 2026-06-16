"""Small model-client helpers for OpenAI-compatible endpoints."""

from __future__ import annotations

from typing import Any

import requests

from . import config


def openai_chat_completion(
    messages: list[dict[str, Any]],
    model: str,
    *,
    timeout: int,
    temperature: float | None = None,
    response_format: dict[str, str] | None = None,
) -> str:
    if not config.OPENAI_BASE_URL:
        raise RuntimeError("OPENAI_BASE_URL 或 RIJI_OPENAI_BASE_URL 未设置")
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY 或 RIJI_OPENAI_API_KEY 未设置")

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if response_format is not None:
        payload["response_format"] = response_format

    resp = requests.post(
        f"{config.OPENAI_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    choices = resp.json().get("choices") or []
    if not choices:
        return ""
    return (choices[0].get("message") or {}).get("content", "").strip()
