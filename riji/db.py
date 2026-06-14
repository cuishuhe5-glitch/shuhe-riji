"""SQLite 存储层。一条 activity = 一张被识别的截图对应的工作活动。"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, Optional

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS activities (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL,          -- ISO8601 本地时间
    day        TEXT NOT NULL,          -- YYYY-MM-DD，方便按天查
    category   TEXT NOT NULL,          -- 见 config.CATEGORIES
    summary    TEXT NOT NULL,          -- 一句话：当时在干嘛
    app        TEXT,                   -- 前台应用/窗口（如果拿得到）
    window_title TEXT,                 -- 前台窗口标题（如果拿得到）
    shot_path  TEXT                    -- 截图文件路径（可为空）
);
CREATE INDEX IF NOT EXISTS idx_activities_day ON activities(day);

CREATE TABLE IF NOT EXISTS reports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    day         TEXT NOT NULL,
    kind        TEXT NOT NULL,
    style       TEXT NOT NULL,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reports_day ON reports(day);
CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at);

CREATE TABLE IF NOT EXISTS day_notes (
    day        TEXT PRIMARY KEY,
    note       TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    day         TEXT NOT NULL,
    scope       TEXT NOT NULL,
    question    TEXT NOT NULL,
    answer      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_day ON chat_messages(day);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    config.ensure_dirs()
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
        _migrate(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(activities)")}
    if "window_title" not in columns:
        conn.execute("ALTER TABLE activities ADD COLUMN window_title TEXT")


def add_activity(
    category: str,
    summary: str,
    app: Optional[str] = None,
    window_title: Optional[str] = None,
    shot_path: Optional[str] = None,
    ts: Optional[datetime] = None,
) -> int:
    ts = ts or datetime.now()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO activities (ts, day, category, summary, app, window_title, shot_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ts.isoformat(timespec="seconds"), ts.strftime("%Y-%m-%d"),
             category, summary, app, window_title, shot_path),
        )
        return cur.lastrowid


def activities_for_day(day: str) -> list[sqlite3.Row]:
    """day: 'YYYY-MM-DD'。按时间升序返回当天所有活动。"""
    with connect() as conn:
        return list(conn.execute(
            "SELECT * FROM activities WHERE day = ? ORDER BY ts ASC", (day,)
        ))


def activity_by_id(activity_id: int) -> Optional[sqlite3.Row]:
    with connect() as conn:
        return conn.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)).fetchone()


def update_activity(
    activity_id: int,
    *,
    category: str,
    summary: str,
    app: Optional[str] = None,
    window_title: Optional[str] = None,
) -> bool:
    with connect() as conn:
        cur = conn.execute(
            "UPDATE activities SET category = ?, summary = ?, app = ?, window_title = ? WHERE id = ?",
            (category, summary, app, window_title, activity_id),
        )
        return cur.rowcount > 0


def delete_activity(activity_id: int) -> Optional[str]:
    with connect() as conn:
        row = conn.execute("SELECT shot_path FROM activities WHERE id = ?", (activity_id,)).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM activities WHERE id = ?", (activity_id,))
        return row["shot_path"]


def activities_between(start_day: str, end_day: str) -> list[sqlite3.Row]:
    """闭区间 [start_day, end_day]，用于周报/月报。"""
    with connect() as conn:
        return list(conn.execute(
            "SELECT * FROM activities WHERE day BETWEEN ? AND ? ORDER BY ts ASC",
            (start_day, end_day),
        ))


def search_activities(
    *,
    query: str = "",
    start_day: Optional[str] = None,
    end_day: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100,
) -> list[sqlite3.Row]:
    """按关键词、日期范围和分类搜索活动记录。"""
    clauses: list[str] = []
    params: list[object] = []
    query = query.strip()
    if query:
        clauses.append(
            "(summary LIKE ? OR app LIKE ? OR window_title LIKE ? OR category LIKE ?)"
        )
        like = f"%{query}%"
        params.extend([like, like, like, like])
    if start_day:
        clauses.append("day >= ?")
        params.append(start_day)
    if end_day:
        clauses.append("day <= ?")
        params.append(end_day)
    if category:
        clauses.append("category = ?")
        params.append(category)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    limit = max(1, min(int(limit or 100), 500))
    params.append(limit)
    with connect() as conn:
        return list(conn.execute(
            f"SELECT * FROM activities {where} ORDER BY ts DESC LIMIT ?",
            params,
        ))


def activity_days(limit: int = 45) -> list[sqlite3.Row]:
    with connect() as conn:
        return list(conn.execute(
            "SELECT day, count(*) AS count, min(ts) AS first_ts, max(ts) AS last_ts "
            "FROM activities GROUP BY day ORDER BY day DESC LIMIT ?",
            (limit,),
        ))


def activity_trends(start_day: str, end_day: str) -> list[sqlite3.Row]:
    with connect() as conn:
        return list(conn.execute(
            "SELECT day, category, app, count(*) AS count "
            "FROM activities WHERE day BETWEEN ? AND ? "
            "GROUP BY day, category, app ORDER BY day ASC",
            (start_day, end_day),
        ))


def day_note(day: str) -> Optional[sqlite3.Row]:
    with connect() as conn:
        return conn.execute("SELECT * FROM day_notes WHERE day = ?", (day,)).fetchone()


def save_day_note(day: str, note: str, ts: Optional[datetime] = None) -> None:
    ts = ts or datetime.now()
    with connect() as conn:
        if note.strip():
            conn.execute(
                "INSERT INTO day_notes (day, note, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(day) DO UPDATE SET note = excluded.note, updated_at = excluded.updated_at",
                (day, note.strip(), ts.isoformat(timespec="seconds")),
            )
        else:
            conn.execute("DELETE FROM day_notes WHERE day = ?", (day,))


def add_report(day: str, kind: str, style: str, body: str, ts: Optional[datetime] = None) -> int:
    ts = ts or datetime.now()
    title = f"{day} {kind}"
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO reports (created_at, day, kind, style, title, body) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ts.isoformat(timespec="seconds"), day, kind, style, title, body),
        )
        return cur.lastrowid


def reports(limit: int = 30) -> list[sqlite3.Row]:
    with connect() as conn:
        return list(conn.execute(
            "SELECT id, created_at, day, kind, style, title, substr(body, 1, 180) AS preview "
            "FROM reports ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ))


def all_reports() -> list[sqlite3.Row]:
    with connect() as conn:
        return list(conn.execute("SELECT * FROM reports ORDER BY created_at DESC"))


def report_by_id(report_id: int) -> Optional[sqlite3.Row]:
    with connect() as conn:
        return conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()


def update_report_body(report_id: int, body: str) -> bool:
    with connect() as conn:
        cur = conn.execute("UPDATE reports SET body = ? WHERE id = ?", (body, report_id))
        return cur.rowcount > 0


def delete_report(report_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
        return cur.rowcount > 0


def add_chat_message(
    *,
    day: str,
    scope: str,
    question: str,
    answer: str,
    ts: Optional[datetime] = None,
) -> int:
    ts = ts or datetime.now()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO chat_messages (created_at, day, scope, question, answer) "
            "VALUES (?, ?, ?, ?, ?)",
            (ts.isoformat(timespec="seconds"), day, scope, question, answer),
        )
        return cur.lastrowid


def chat_messages(day: str, limit: int = 12) -> list[sqlite3.Row]:
    limit = max(1, min(int(limit or 12), 50))
    with connect() as conn:
        return list(conn.execute(
            "SELECT * FROM chat_messages WHERE day = ? ORDER BY created_at DESC LIMIT ?",
            (day, limit),
        ))


def delete_chat_message(message_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM chat_messages WHERE id = ?", (message_id,))
        return cur.rowcount > 0
