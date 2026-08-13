"""
backend/repositories/jd_repo.py — Job Description CRUD
"""
from __future__ import annotations

from typing import Any, Optional

from backend.database.db import get_db


def create_jd(
    company_id: int,
    created_by: int,
    title: str,
    description: str,
    requirements: str = "",
) -> int:
    """Insert a new job description. Returns new jd_id."""
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO job_descriptions (company_id, created_by, title, description, requirements)
               VALUES (?, ?, ?, ?, ?)""",
            (company_id, created_by, title, description, requirements),
        )
        return cur.lastrowid


def count_jds(company_id: int) -> int:
    """Return the total number of JDs for a company."""
    with get_db() as db:
        row = db.execute(
            "SELECT COUNT(*) FROM job_descriptions WHERE company_id = ?",
            (company_id,),
        ).fetchone()
        return int(row[0] if row else 0)


def get_jd(jd_id: int) -> Optional[dict[str, Any]]:
    """Return a single JD dict or None."""
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM job_descriptions WHERE id = ? LIMIT 1",
            (jd_id,),
        ).fetchone()
        return dict(row) if row else None


def list_jds(company_id: int) -> list[dict[str, Any]]:
    """Return all JDs for a company, active first then newest."""
    with get_db() as db:
        rows = db.execute(
            """
            SELECT jd.*, u.name AS creator_name
            FROM job_descriptions jd
            LEFT JOIN users u ON jd.created_by = u.id
            WHERE jd.company_id = ?
            ORDER BY jd.is_active DESC, jd.created_at DESC, jd.id DESC
            """,
            (company_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_active_jd(company_id: int) -> Optional[dict[str, Any]]:
    """Return the currently active JD or None."""
    with get_db() as db:
        row = db.execute(
            """
            SELECT *
            FROM job_descriptions
            WHERE company_id = ? AND is_active = 1
            ORDER BY updated_at DESC, created_at DESC, id DESC
            LIMIT 1
            """,
            (company_id,),
        ).fetchone()
        return dict(row) if row else None


def set_active_jd(company_id: int, jd_id: int) -> None:
    """Deactivate all JDs and activate the selected one."""
    with get_db() as db:
        target = db.execute(
            """
            SELECT id
            FROM job_descriptions
            WHERE id = ? AND company_id = ?
            LIMIT 1
            """,
            (jd_id, company_id),
        ).fetchone()
        if not target:
            raise ValueError(f"Job description #{jd_id} not found.")

        db.execute(
            """
            UPDATE job_descriptions
            SET is_active = 0,
                updated_at = datetime('now')
            WHERE company_id = ?
            """,
            (company_id,),
        )

        db.execute(
            """
            UPDATE job_descriptions
            SET is_active = 1,
                updated_at = datetime('now')
            WHERE id = ? AND company_id = ?
            """,
            (jd_id, company_id),
        )


def update_jd(jd_id: int, **fields) -> None:
    """Update arbitrary JD fields."""
    if not fields:
        return

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [jd_id]

    with get_db() as db:
        db.execute(
            f"""
            UPDATE job_descriptions
            SET {set_clause},
                updated_at = datetime('now')
            WHERE id = ?
            """,
            values,
        )


def delete_jd(jd_id: int) -> None:
    """
    Delete a Job Description and all dependent records
    to avoid FOREIGN KEY constraint errors.
    """
    with get_db() as db:

        # Analysis Results
        db.execute(
            "DELETE FROM analysis_results WHERE jd_id = ?",
            (jd_id,),
        )

        # Recruitment Pipeline
        db.execute(
            "DELETE FROM recruitment_pipeline WHERE jd_id = ?",
            (jd_id,),
        )

        # Shortlisted Candidates
        db.execute(
            "DELETE FROM shortlisted_candidates WHERE jd_id = ?",
            (jd_id,),
        )

        # Reports
        db.execute(
            "DELETE FROM reports WHERE jd_id = ?",
            (jd_id,),
        )

        # Candidate child tables
        candidate_rows = db.execute(
            "SELECT id FROM candidates WHERE jd_id = ?",
            (jd_id,),
        ).fetchall()

        for row in candidate_rows:
            candidate_id = row["id"]

            db.execute(
                "DELETE FROM candidate_skills WHERE candidate_id=?",
                (candidate_id,),
            )

            db.execute(
                "DELETE FROM candidate_experience WHERE candidate_id=?",
                (candidate_id,),
            )

            db.execute(
                "DELETE FROM candidate_education WHERE candidate_id=?",
                (candidate_id,),
            )

            db.execute(
                "DELETE FROM candidate_projects WHERE candidate_id=?",
                (candidate_id,),
            )

            db.execute(
                "DELETE FROM candidate_certificates WHERE candidate_id=?",
                (candidate_id,),
            )

            db.execute(
                "DELETE FROM candidate_notes WHERE candidate_id=?",
                (candidate_id,),
            )

            db.execute(
                "DELETE FROM candidate_timeline WHERE candidate_id=?",
                (candidate_id,),
            )

            db.execute(
                "DELETE FROM analysis_results WHERE candidate_id=?",
                (candidate_id,),
            )

        # Candidates
        db.execute(
            "DELETE FROM candidates WHERE jd_id=?",
            (jd_id,),
        )

        # Resume Uploads
        db.execute(
            "DELETE FROM resume_uploads WHERE jd_id=?",
            (jd_id,),
        )

        # Finally delete JD
        db.execute(
            "DELETE FROM job_descriptions WHERE id=?",
            (jd_id,),
        )


def increment_resume_count(jd_id: int) -> None:
    """Increment resume count."""
    with get_db() as db:
        db.execute(
            """
            UPDATE job_descriptions
            SET resume_count = resume_count + 1
            WHERE id = ?
            """,
            (jd_id,),
        )


def decrement_resume_count(jd_id: int) -> None:
    """Decrement resume count without going below zero."""
    with get_db() as db:
        db.execute(
            """
            UPDATE job_descriptions
            SET resume_count = CASE
                WHEN resume_count > 0 THEN resume_count - 1
                ELSE 0
            END
            WHERE id = ?
            """,
            (jd_id,),
        )
