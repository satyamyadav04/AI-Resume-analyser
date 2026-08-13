"""
backend/repositories/settings_repo.py — User Settings Persistence
"""
from __future__ import annotations

import json
from typing import Any

from backend.database.db import get_db

_DEFAULTS = {
    "theme": "light",
    "language": "English (US)",
    "notifications": {"email": True, "weekly": True, "reminders": False},
    "analysis_mode": "Balanced",
    "ai_model": "Resume-Analyzer v3 (Recommended)",
    "default_jd_id": None,
}


def get_settings(user_id: int) -> dict[str, Any]:
    """Return settings for a user, inserting defaults if none exist."""
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM settings WHERE user_id = ? LIMIT 1", (user_id,)
        ).fetchone()

    if not row:
        _insert_defaults(user_id)
        return dict(_DEFAULTS)

    result = dict(row)
    try:
        result["notifications"] = json.loads(result.get("notifications", "{}"))
    except (json.JSONDecodeError, TypeError):
        result["notifications"] = _DEFAULTS["notifications"]
    return result


def save_settings(user_id: int, settings: dict[str, Any]) -> None:
    """Upsert settings for a user."""
    notif = settings.get("notifications", _DEFAULTS["notifications"])
    if isinstance(notif, dict):
        notif = json.dumps(notif)

    with get_db() as db:
        db.execute(
            """INSERT INTO settings (user_id, theme, language, notifications, analysis_mode, ai_model, default_jd_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
               theme = excluded.theme,
               language = excluded.language,
               notifications = excluded.notifications,
               analysis_mode = excluded.analysis_mode,
               ai_model = excluded.ai_model,
               default_jd_id = excluded.default_jd_id,
               updated_at = datetime('now')""",
            (
                user_id,
                settings.get("theme", "light"),
                settings.get("language", "English (US)"),
                notif,
                settings.get("analysis_mode", "Balanced"),
                settings.get("ai_model", "Resume-Analyzer v3 (Recommended)"),
                settings.get("default_jd_id"),
            ),
        )


def _insert_defaults(user_id: int) -> None:
    with get_db() as db:
        db.execute(
            """INSERT OR IGNORE INTO settings (user_id, theme, language, notifications, analysis_mode, ai_model)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                _DEFAULTS["theme"],
                _DEFAULTS["language"],
                json.dumps(_DEFAULTS["notifications"]),
                _DEFAULTS["analysis_mode"],
                _DEFAULTS["ai_model"],
            ),
        )
