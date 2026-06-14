"""Storage statistics and cleanup helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from . import config, db


def stats() -> dict[str, Any]:
    shot_files = _shot_files()
    total_bytes = sum(path.stat().st_size for path in shot_files if path.exists())
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT COUNT(*) AS total, SUM(CASE WHEN shot_path IS NOT NULL AND shot_path != '' THEN 1 ELSE 0 END) AS with_shots FROM activities"
        ).fetchone()
    return {
        "data_dir": str(config.DATA_DIR),
        "shots_dir": str(config.SHOTS_DIR),
        "shot_files": len(shot_files),
        "shot_bytes": total_bytes,
        "shot_size": _format_bytes(total_bytes),
        "activities": int(rows["total"] or 0),
        "activities_with_shots": int(rows["with_shots"] or 0),
    }


def clear_shots() -> dict[str, Any]:
    files = _shot_files()
    result = _remove_shot_files(files)
    with db.connect() as conn:
        conn.execute("UPDATE activities SET shot_path = NULL WHERE shot_path IS NOT NULL")
    return {
        **result,
        "storage": stats(),
    }


def prune_old_shots(retention_days: int) -> dict[str, Any]:
    """Delete screenshots older than retention_days. 0 disables automatic pruning."""
    retention_days = max(0, int(retention_days or 0))
    if retention_days <= 0:
        return {
            "removed": 0,
            "bytes_removed": 0,
            "size_removed": _format_bytes(0),
            "storage": stats(),
        }
    cutoff = datetime.now() - timedelta(days=retention_days)
    files = [
        path
        for path in _shot_files()
        if datetime.fromtimestamp(path.stat().st_mtime) < cutoff
    ]
    result = _remove_shot_files(files)
    return {
        **result,
        "retention_days": retention_days,
        "storage": stats(),
    }


def _remove_shot_files(files: list[Path]) -> dict[str, Any]:
    removed = 0
    bytes_removed = 0
    deleted_paths: list[str] = []
    for path in files:
        try:
            size = path.stat().st_size
            path.unlink()
            removed += 1
            bytes_removed += size
            deleted_paths.append(str(path))
        except OSError:
            continue
    if deleted_paths:
        with db.connect() as conn:
            conn.executemany(
                "UPDATE activities SET shot_path = NULL WHERE shot_path = ?",
                [(path,) for path in deleted_paths],
            )
    return {
        "removed": removed,
        "bytes_removed": bytes_removed,
        "size_removed": _format_bytes(bytes_removed),
    }


def _shot_files() -> list[Path]:
    if not config.SHOTS_DIR.exists():
        return []
    return sorted(
        path
        for path in config.SHOTS_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )


def _format_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(amount)} {unit}"
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{value} B"
