"""全局配置。所有路径默认落在用户主目录下的 ~/.xiaohei-riji，跨平台。"""

import os
from pathlib import Path

from . import keychain

# ---- 数据存储（纯本地）----
DATA_DIR = Path(os.environ.get("RIJI_HOME", Path.home() / ".xiaohei-riji"))
DB_PATH = DATA_DIR / "riji.db"
SHOTS_DIR = DATA_DIR / "shots"
REPORTS_DIR = DATA_DIR / "reports"
LOGS_DIR = DATA_DIR / "logs"
BACKUPS_DIR = DATA_DIR / "backups"
EXPORTS_DIR = DATA_DIR / "exports"

# ---- 截图 ----
CAPTURE_INTERVAL = int(os.environ.get("RIJI_INTERVAL", "120"))  # 抓图间隔（秒）
# 画面变化低于该阈值则跳过识别，省钱省算力。0~1，越大越"迟钝"。
CHANGE_THRESHOLD = float(os.environ.get("RIJI_CHANGE_THRESHOLD", "0.04"))
IDLE_PAUSE_AFTER = int(os.environ.get("RIJI_IDLE_PAUSE", "600"))  # 连续无变化超时则判定闲置（秒）
# 截图缩略图最长边，喂给视觉模型前压缩，省 token / 显存。
THUMB_MAX_EDGE = int(os.environ.get("RIJI_THUMB_EDGE", "1280"))
KEEP_SHOT_FILES = os.environ.get("RIJI_KEEP_SHOTS", "0") == "1"  # 是否保留截图原图

# ---- 模型后端 ----
# ollama: 调本机 Ollama /api/generate
# openai: 调 OpenAI-compatible /v1/chat/completions，例如 Hermes: http://localhost:55021/v1
LLM_PROVIDER = os.environ.get("RIJI_LLM_PROVIDER", "").strip().lower()
OPENAI_BASE_URL = os.environ.get(
    "RIJI_OPENAI_BASE_URL",
    os.environ.get("OPENAI_BASE_URL", ""),
).rstrip("/")
OPENAI_API_KEY = os.environ.get(
    "RIJI_OPENAI_API_KEY",
    os.environ.get("OPENAI_API_KEY", ""),
)
OPENAI_API_KEY_SOURCE = "environment" if OPENAI_API_KEY else ""
if not OPENAI_API_KEY:
    OPENAI_API_KEY = keychain.get_password()
    OPENAI_API_KEY_SOURCE = "keychain" if OPENAI_API_KEY else ""

if not LLM_PROVIDER:
    LLM_PROVIDER = "openai" if OPENAI_BASE_URL else "ollama"

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")

_OPENAI_DEFAULT_MODEL = os.environ.get("RIJI_OPENAI_MODEL", "gpt-5.5")
if LLM_PROVIDER == "openai":
    VISION_MODEL = os.environ.get("RIJI_VISION_MODEL", _OPENAI_DEFAULT_MODEL)
    TEXT_MODEL = os.environ.get("RIJI_TEXT_MODEL", _OPENAI_DEFAULT_MODEL)
else:
    VISION_MODEL = os.environ.get("RIJI_VISION_MODEL", "qwen2.5vl:7b")  # 识别截图的多模态模型
    TEXT_MODEL = os.environ.get("RIJI_TEXT_MODEL", "qwen2.5:7b")        # 生成报告的文本模型

# 活动分类（识别时让模型从中择一，保证可统计）
CATEGORIES = [
    "编码开发",
    "会议沟通",
    "文档写作",
    "阅读学习",
    "邮件即时通讯",
    "设计",
    "数据分析",
    "网页浏览",
    "娱乐休息",
    "其他",
]


def ensure_dirs() -> None:
    """首次运行时建好数据目录。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
