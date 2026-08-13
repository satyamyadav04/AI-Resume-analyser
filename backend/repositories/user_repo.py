"""
backend/repositories/user_repo.py — User CRUD
PostgreSQL compatible version.
"""
from __future__ import annotations

from typing import Any, Optional

from backend.database.db import get_db


def create_user(
    company_id: int,
    name: str,
    email: str,
    password_hash: str,
    role: str = "hr_manager",
) -> int:
    """Insert a new user and return the new user id."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users
                    (company_id, name, email, password_hash, role, avatar_initials)
                VALUES
                    (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    company_id,
                    name,
                    email,
                    password_hash,
                    role,
                    _initials(name),
                ),
            )

            row = cur.fetchone()
            return int(row[0])


def get_user_by_email(email: str) -> Optional[dict[str, Any]]:
    """Return user row dict by email, or None."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM users
                WHERE email = %s
                LIMIT 1
                """,
                (email,),
            )

            row = cur.fetchone()

            if not row:
                return None

            columns = [desc[0] for desc in cur.description]
            return dict(zip(columns, row))


def get_user_by_id(user_id: int) -> Optional[dict[str, Any]]:
    """Return user row dict by id, or None."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM users
                WHERE id = %s
                LIMIT 1
                """,
                (user_id,),
            )

            row = cur.fetchone()

            if not row:
                return None

            columns = [desc[0] for desc in cur.description]
            return dict(zip(columns, row))


def update_user(user_id: int, **fields) -> None:
    """Update arbitrary user fields."""

    if not fields:
        return

    if "name" in fields:
        fields["avatar_initials"] = _initials(fields["name"])

    set_clause = ", ".join(f"{key} = %s" for key in fields)

    values = list(fields.values()) + [user_id]

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                f"""
                UPDATE users
                SET {set_clause},
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                values,
            )


def email_exists(email: str) -> bool:
    """Return True if the email is already registered."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM users
                WHERE email = %s
                LIMIT 1
                """,
                (email,),
            )

            return cur.fetchone() is not None


def _initials(name: str) -> str:
    parts = name.strip().split()

    return (
        "".join(p[0].upper() for p in parts[:2])
        if parts
        else "??"
    )