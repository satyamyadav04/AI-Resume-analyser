from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Generator

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")


def _get_connection():
    """Create a PostgreSQL database connection."""
    return psycopg2.connect(DATABASE_URL)


@contextmanager
def get_db() -> Generator:
    """Context manager for PostgreSQL connections."""
    conn = _get_connection()

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create all database tables and indexes."""
    from backend.database.models import ALL_DDL

    conn = _get_connection()

    try:
        with conn.cursor() as cursor:
            for ddl in ALL_DDL:
                cursor.execute(ddl)

        conn.commit()

        logger.info("PostgreSQL database initialized successfully.")

    except Exception as exc:
        conn.rollback()
        logger.exception("Failed to initialize PostgreSQL database: %s", exc)
        raise

    finally:
        conn.close()


def get_db_path() -> str:
    """Return database URL."""
    return DATABASE_URL


def get_project_root():
    from pathlib import Path
    return Path(__file__).resolve().parents[2]