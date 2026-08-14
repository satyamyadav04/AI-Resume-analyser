"""
backend/repositories/jd_repo.py — Job Description CRUD
PostgreSQL compatible version.
"""

from __future__ import annotations

from typing import Any, Optional

from backend.database.db import get_db


def _row_to_dict(cursor, row) -> dict[str, Any]:
    """Convert PostgreSQL tuple row into dictionary."""
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))


def create_jd(
    company_id: int,
    created_by: int,
    title: str,
    description: str,
    requirements: str = "",
) -> int:
    """Insert a new job description. Returns new jd_id."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO job_descriptions
                    (company_id, created_by, title, description, requirements)
                VALUES
                    (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    company_id,
                    created_by,
                    title,
                    description,
                    requirements,
                ),
            )

            row = cur.fetchone()
            return int(row[0])


def count_jds(company_id: int) -> int:
    """Return total number of JDs for a company."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM job_descriptions
                WHERE company_id = %s
                """,
                (company_id,),
            )

            row = cur.fetchone()
            return int(row[0] if row else 0)


def get_jd(jd_id: int) -> Optional[dict[str, Any]]:
    """Return a single JD dict or None."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM job_descriptions
                WHERE id = %s
                LIMIT 1
                """,
                (jd_id,),
            )

            row = cur.fetchone()

            if not row:
                return None

            return _row_to_dict(cur, row)


def list_jds(company_id: int) -> list[dict[str, Any]]:
    """Return all JDs for a company, active first then newest."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT
                    jd.*,
                    u.name AS creator_name
                FROM job_descriptions jd
                LEFT JOIN users u
                    ON jd.created_by = u.id
                WHERE jd.company_id = %s
                ORDER BY
                    jd.is_active DESC,
                    jd.created_at DESC,
                    jd.id DESC
                """,
                (company_id,),
            )

            rows = cur.fetchall()

            return [
                _row_to_dict(cur, row)
                for row in rows
            ]


def get_active_jd(company_id: int) -> Optional[dict[str, Any]]:
    """Return currently active JD or None."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM job_descriptions
                WHERE company_id = %s
                  AND is_active = TRUE
                ORDER BY
                    updated_at DESC,
                    created_at DESC,
                    id DESC
                LIMIT 1
                """,
                (company_id,),
            )

            row = cur.fetchone()

            if not row:
                return None

            return _row_to_dict(cur, row)


def set_active_jd(company_id: int, jd_id: int) -> None:
    """Deactivate all JDs and activate selected one."""

    with get_db() as db:
        with db.cursor() as cur:

            cur.execute(
                """
                SELECT id
                FROM job_descriptions
                WHERE id = %s
                  AND company_id = %s
                LIMIT 1
                """,
                (jd_id, company_id),
            )

            target = cur.fetchone()

            if not target:
                raise ValueError(
                    f"Job description #{jd_id} not found."
                )

            cur.execute(
                """
                UPDATE job_descriptions
                SET
                    is_active = FALSE,
                    updated_at = CURRENT_TIMESTAMP
                WHERE company_id = %s
                """,
                (company_id,),
            )

            cur.execute(
                """
                UPDATE job_descriptions
                SET
                    is_active = TRUE,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                  AND company_id = %s
                """,
                (jd_id, company_id),
            )


def update_jd(jd_id: int, **fields) -> None:
    """Update arbitrary JD fields."""

    if not fields:
        return

    set_clause = ", ".join(
        f"{key} = %s"
        for key in fields
    )

    values = list(fields.values()) + [jd_id]

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                f"""
                UPDATE job_descriptions
                SET
                    {set_clause},
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                values,
            )


def delete_jd(jd_id: int) -> None:
    """
    Delete a Job Description and dependent records.
    """

    with get_db() as db:
        with db.cursor() as cur:

            # Analysis Results
            cur.execute(
                """
                DELETE FROM analysis_results
                WHERE jd_id = %s
                """,
                (jd_id,),
            )

            # Recruitment Pipeline
            cur.execute(
                """
                DELETE FROM recruitment_pipeline
                WHERE jd_id = %s
                """,
                (jd_id,),
            )

            # Shortlisted Candidates
            cur.execute(
                """
                DELETE FROM shortlisted_candidates
                WHERE jd_id = %s
                """,
                (jd_id,),
            )

            # Reports
            cur.execute(
                """
                DELETE FROM reports
                WHERE jd_id = %s
                """,
                (jd_id,),
            )

            # Find candidates
            cur.execute(
                """
                SELECT id
                FROM candidates
                WHERE jd_id = %s
                """,
                (jd_id,),
            )

            candidate_rows = cur.fetchall()

            for row in candidate_rows:
                candidate_id = row[0]

                cur.execute(
                    """
                    DELETE FROM candidate_skills
                    WHERE candidate_id = %s
                    """,
                    (candidate_id,),
                )

                cur.execute(
                    """
                    DELETE FROM candidate_experience
                    WHERE candidate_id = %s
                    """,
                    (candidate_id,),
                )

                cur.execute(
                    """
                    DELETE FROM candidate_education
                    WHERE candidate_id = %s
                    """,
                    (candidate_id,),
                )

                cur.execute(
                    """
                    DELETE FROM candidate_projects
                    WHERE candidate_id = %s
                    """,
                    (candidate_id,),
                )

                cur.execute(
                    """
                    DELETE FROM candidate_certificates
                    WHERE candidate_id = %s
                    """,
                    (candidate_id,),
                )

                cur.execute(
                    """
                    DELETE FROM candidate_notes
                    WHERE candidate_id = %s
                    """,
                    (candidate_id,),
                )

                cur.execute(
                    """
                    DELETE FROM candidate_timeline
                    WHERE candidate_id = %s
                    """,
                    (candidate_id,),
                )

                cur.execute(
                    """
                    DELETE FROM analysis_results
                    WHERE candidate_id = %s
                    """,
                    (candidate_id,),
                )

            # Candidates
            cur.execute(
                """
                DELETE FROM candidates
                WHERE jd_id = %s
                """,
                (jd_id,),
            )

            # Resume uploads
            cur.execute(
                """
                DELETE FROM resume_uploads
                WHERE jd_id = %s
                """,
                (jd_id,),
            )

            # Finally delete JD
            cur.execute(
                """
                DELETE FROM job_descriptions
                WHERE id = %s
                """,
                (jd_id,),
            )


def increment_resume_count(jd_id: int) -> None:
    """Increment resume count."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                UPDATE job_descriptions
                SET resume_count = resume_count + 1
                WHERE id = %s
                """,
                (jd_id,),
            )


def decrement_resume_count(jd_id: int) -> None:
    """Decrement resume count without going below zero."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                UPDATE job_descriptions
                SET resume_count =
                    CASE
                        WHEN resume_count > 0
                        THEN resume_count - 1
                        ELSE 0
                    END
                WHERE id = %s
                """,
                (jd_id,),
            )