"""
backend/repositories/settings_repo.py — User Settings Persistence
PostgreSQL compatible version.
"""

from __future__ import annotations

import json
from typing import Any

from backend.database.db import get_db


_DEFAULTS = {
    "theme": "light",
    "language": "English (US)",
    "notifications": {
        "email": True,
        "weekly": True,
        "reminders": False,
    },
    "analysis_mode": "Balanced",
    "ai_model": "Resume-Analyzer v3 (Recommended)",
    "default_jd_id": None,
}


def _row_to_dict(cursor, row) -> dict[str, Any]:
    """Convert PostgreSQL tuple row into a dictionary."""
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))


def get_settings(user_id: int) -> dict[str, Any]:
    """Return settings for a user, inserting defaults if none exist."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM settings
                WHERE user_id = %s
                LIMIT 1
                """,
                (user_id,),
            )

            row = cur.fetchone()

            if not row:
                _insert_defaults(user_id)
                return dict(_DEFAULTS)

            result = _row_to_dict(cur, row)

    try:
        notifications = result.get("notifications", "{}")

        if isinstance(notifications, str):
            result["notifications"] = json.loads(notifications)
        elif isinstance(notifications, dict):
            result["notifications"] = notifications
        else:
            result["notifications"] = _DEFAULTS["notifications"]

    except (json.JSONDecodeError, TypeError):
        result["notifications"] = _DEFAULTS["notifications"]

    return result


def save_settings(user_id: int, settings: dict[str, Any]) -> None:
    """Upsert settings for a user."""

    notif = settings.get(
        "notifications",
        _DEFAULTS["notifications"],
    )

    if isinstance(notif, dict):
        notif = json.dumps(notif)

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO settings (
                    user_id,
                    theme,
                    language,
                    notifications,
                    analysis_mode,
                    ai_model,
                    default_jd_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)

                ON CONFLICT (user_id)
                DO UPDATE SET
                    theme = EXCLUDED.theme,
                    language = EXCLUDED.language,
                    notifications = EXCLUDED.notifications,
                    analysis_mode = EXCLUDED.analysis_mode,
                    ai_model = EXCLUDED.ai_model,
                    default_jd_id = EXCLUDED.default_jd_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    user_id,
                    settings.get("theme", _DEFAULTS["theme"]),
                    settings.get("language", _DEFAULTS["language"]),
                    notif,
                    settings.get(
                        "analysis_mode",
                        _DEFAULTS["analysis_mode"],
                    ),
                    settings.get(
                        "ai_model",
                        _DEFAULTS["ai_model"],
                    ),
                    settings.get("default_jd_id"),
                ),
            )


def _insert_defaults(user_id: int) -> None:
    """Insert default settings for a user."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO settings (
                    user_id,
                    theme,
                    language,
                    notifications,
                    analysis_mode,
                    ai_model
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO NOTHING
                """,
                (
                    user_id,
                    _DEFAULTS["theme"],
                    _DEFAULTS["language"],
                    json.dumps(_DEFAULTS["notifications"]),
                    _DEFAULTS["analysis_mode"],
                    _DEFAULTS["ai_model"],
                ),
            )