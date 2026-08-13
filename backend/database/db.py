"""
backend/database/db.py — SQLite Connection Manager & Schema Initializer
========================================================================
Provides thread-safe SQLite connections with WAL mode enabled.
Automatically creates all ATS tables on first run.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database path — stored at project root
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DB_PATH = str(_PROJECT_ROOT / "ats.db")

# Thread-local storage for connections
_local = threading.local()


def _get_connection() -> sqlite3.Connection:
    """Return (or create) a thread-local SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
        _local.conn.execute("PRAGMA synchronous=NORMAL")
    return _local.conn


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager that yields a SQLite connection.

    Commits on success, rolls back on exception.
    """
    conn = _get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db() -> None:
    """Create all tables if they don't exist, and seed storage directories."""
    from backend.database.models import ALL_DDL

    conn = _get_connection()
    try:
        for ddl in ALL_DDL:
            conn.execute(ddl)
        _normalize_active_jds(conn)
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_jd_one_active_per_company
            ON job_descriptions(company_id)
            WHERE is_active = 1
            """
        )
        conn.commit()
        logger.info("Database initialized at: %s", _DB_PATH)
    except Exception as exc:
        conn.rollback()
        logger.exception("Failed to initialize database: %s", exc)
        raise

    # Create storage directories
    storage_dirs = [
        _PROJECT_ROOT / "storage" / "resumes",
        _PROJECT_ROOT / "storage" / "job_descriptions",
        _PROJECT_ROOT / "storage" / "reports",
        _PROJECT_ROOT / "storage" / "cache",
    ]
    for d in storage_dirs:
        d.mkdir(parents=True, exist_ok=True)
    logger.info("Storage directories initialized.")


def get_db_path() -> str:
    """Return the absolute path to the SQLite database file."""
    return _DB_PATH


def get_project_root() -> Path:
    """Return the project root Path."""
    return _PROJECT_ROOT


def _normalize_active_jds(conn: sqlite3.Connection) -> None:
    """Keep only one active JD per company before enforcing the unique index."""
    duplicates = conn.execute(
        """
        SELECT company_id
        FROM job_descriptions
        WHERE is_active = 1
        GROUP BY company_id
        HAVING COUNT(*) > 1
        """
    ).fetchall()

    for row in duplicates:
        company_id = row[0]
        active_rows = conn.execute(
            """
            SELECT id
            FROM job_descriptions
            WHERE company_id = ? AND is_active = 1
            ORDER BY updated_at DESC, created_at DESC, id DESC
            """,
            (company_id,),
        ).fetchall()
        keep_id = active_rows[0][0]
        conn.execute(
            """
            UPDATE job_descriptions
            SET is_active = 0,
                updated_at = datetime('now')
            WHERE company_id = ? AND is_active = 1 AND id != ?
            """,
            (company_id, keep_id),
        )
