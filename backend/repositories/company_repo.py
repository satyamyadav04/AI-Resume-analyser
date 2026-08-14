"""
backend/repositories/company_repo.py — Company CRUD
PostgreSQL compatible version.
"""

from __future__ import annotations

from typing import Any, Optional

from backend.database.db import get_db


def create_company(name: str) -> int:
    """Insert a new company. Returns the new company id."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO companies (name)
                VALUES (%s)
                RETURNING id
                """,
                (name,),
            )

            row = cur.fetchone()
            return int(row[0])


def get_company(company_id: int) -> Optional[dict[str, Any]]:
    """Return company dict or None."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM companies
                WHERE id = %s
                LIMIT 1
                """,
                (company_id,),
            )

            row = cur.fetchone()

            if not row:
                return None

            columns = [desc[0] for desc in cur.description]
            return dict(zip(columns, row))


def update_company(company_id: int, name: str) -> None:
    """Update company name."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                UPDATE companies
                SET name = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (name, company_id),
            )