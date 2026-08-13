"""
backend/repositories/user_repo.py — User CRUD
"""
from __future__ import annotations

import sqlite3
from typing import Any, Optional

from backend.database.db import get_db


def create_user(company_id: int, name: str, email: str, password_hash: str, role: str = "hr_manager") -> int:
    """Insert a new user. Returns the new user id."""
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO users (company_id, name, email, password_hash, role, avatar_initials)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (company_id, name, email, password_hash, role, _initials(name)),
        )
        return cur.lastrowid


def get_user_by_email(email: str) -> Optional[dict[str, Any]]:
    """Return user row dict by email, or None."""
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM users WHERE email = ? LIMIT 1", (email,)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[dict[str, Any]]:
    """Return user row dict by id, or None."""
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM users WHERE id = ? LIMIT 1", (user_id,)
        ).fetchone()
        return dict(row) if row else None


def update_user(user_id: int, **fields) -> None:
    """Update arbitrary user fields."""
    if not fields:
        return
    if "name" in fields:
        fields["avatar_initials"] = _initials(fields["name"])
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [user_id]
    with get_db() as db:
        db.execute(
            f"UPDATE users SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
            values,
        )


def email_exists(email: str) -> bool:
    """Return True if the email is already registered."""
    with get_db() as db:
        row = db.execute(
            "SELECT 1 FROM users WHERE email = ? LIMIT 1", (email,)
        ).fetchone()
        return row is not None


def _initials(name: str) -> str:
    parts = name.strip().split()
    return "".join(p[0].upper() for p in parts[:2]) if parts else "??"
