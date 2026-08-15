"""Small presentation helpers shared by Streamlit pages."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any


def format_timestamp(value: Any, length: int = 16) -> str:
    """Return a short display-safe timestamp from PostgreSQL or SQLite values."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")[:length]
    if isinstance(value, date):
        return value.isoformat()[:length]
    return str(value)[:length]
