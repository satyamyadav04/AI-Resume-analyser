"""
backend/repositories/company_repo.py — Company CRUD
"""
from __future__ import annotations

from typing import Any, Optional

from backend.database.db import get_db


def create_company(name: str) -> int:
    """Insert a new company. Returns the new company id."""
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO companies (name) VALUES (?)", (name,)
        )
        return cur.lastrowid


def get_company(company_id: int) -> Optional[dict[str, Any]]:
    """Return company dict or None."""
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM companies WHERE id = ? LIMIT 1", (company_id,)
        ).fetchone()
        return dict(row) if row else None


def update_company(company_id: int, name: str) -> None:
    with get_db() as db:
        db.execute(
            "UPDATE companies SET name = ?, updated_at = datetime('now') WHERE id = ?",
            (name, company_id),
        )
