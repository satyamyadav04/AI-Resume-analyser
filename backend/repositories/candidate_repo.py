"""
backend/repositories/candidate_repo.py — Candidate CRUD + Pipeline + Notes + Timeline
PostgreSQL compatible version.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from backend.database.db import get_db


# Valid recruitment pipeline stages in order
PIPELINE_STAGES = [
    "NEW",
    "AI_ANALYZED",
    "SHORTLISTED",
    "INTERVIEW_SCHEDULED",
    "TECHNICAL_ROUND",
    "HR_ROUND",
    "OFFER_SENT",
    "HIRED",
    "REJECTED",
]


# ---------------------------------------------------------------------------
# PostgreSQL row helpers
# ---------------------------------------------------------------------------

def _row_to_dict(cursor, row) -> dict[str, Any]:
    """Convert a PostgreSQL tuple row into a dictionary."""
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))


def _rows_to_dict(cursor, rows) -> list[dict[str, Any]]:
    """Convert PostgreSQL rows into dictionaries."""
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


# ---------------------------------------------------------------------------
# Candidate
# ---------------------------------------------------------------------------

def save_candidate(
    company_id: int,
    jd_id: int,
    upload_id: Optional[int],
    candidate_dict: dict[str, Any],
) -> int:
    """Insert core candidate record. Returns new candidate DB id."""

    profile = candidate_dict.get("profile", {}) or {}

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO candidates
                (
                    company_id,
                    jd_id,
                    upload_id,
                    candidate_uid,
                    name,
                    email,
                    phone,
                    location,
                    current_title,
                    experience_years,
                    summary,
                    github,
                    linkedin,
                    pipeline_stage
                )
                VALUES
                (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, 'AI_ANALYZED'
                )
                RETURNING id
                """,
                (
                    company_id,
                    jd_id,
                    upload_id,
                    candidate_dict.get("candidate_id", ""),
                    candidate_dict.get("name", "Unknown"),
                    candidate_dict.get("email", profile.get("email", "")),
                    candidate_dict.get("phone", profile.get("phone", "")),
                    candidate_dict.get("location", profile.get("location", "")),
                    profile.get("current_title", ""),
                    float(candidate_dict.get("experience_years", 0.0)),
                    profile.get("summary", ""),
                    profile.get("github", ""),
                    profile.get("linkedin", ""),
                ),
            )

            row = cur.fetchone()
            candidate_db_id = int(row[0])

    # Save related data
    skills = candidate_dict.get("skills", []) or []
    _save_skills(candidate_db_id, skills)

    experience = candidate_dict.get("experience", []) or []
    _save_experience(candidate_db_id, experience)

    education = candidate_dict.get("education", []) or []
    _save_education(candidate_db_id, education)

    projects = candidate_dict.get("projects", []) or []
    _save_projects(candidate_db_id, projects)

    certs = candidate_dict.get("certifications", []) or []
    _save_certificates(candidate_db_id, certs)

    return candidate_db_id


def get_candidate(candidate_db_id: int) -> Optional[dict[str, Any]]:
    """Return full candidate dict including related data, or None."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM candidates
                WHERE id = %s
                LIMIT 1
                """,
                (candidate_db_id,),
            )

            row = cur.fetchone()

            if not row:
                return None

            candidate = _row_to_dict(cur, row)

    candidate["skills"] = get_candidate_skills(candidate_db_id)
    candidate["experience"] = get_candidate_experience(candidate_db_id)
    candidate["education"] = get_candidate_education(candidate_db_id)
    candidate["projects"] = get_candidate_projects(candidate_db_id)
    candidate["certificates"] = get_candidate_certificates(candidate_db_id)
    candidate["analysis"] = get_candidate_analysis(candidate_db_id)

    return candidate


def list_candidates(
    company_id: int,
    jd_id: Optional[int] = None,
    search: str = "",
    stage_filter: Optional[str] = None,
    score_filter: Optional[str] = None,
    sort_by: str = "score_desc",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    """Return paginated candidates with analysis scores."""

    params: list[Any] = [company_id]

    where_clauses = [
        "c.company_id = %s"
    ]

    if jd_id:
        where_clauses.append("c.jd_id = %s")
        params.append(jd_id)

    if search:
        where_clauses.append(
            """
            (
                c.name ILIKE %s
                OR c.email ILIKE %s
                OR c.current_title ILIKE %s
            )
            """
        )

        s = f"%{search}%"
        params.extend([s, s, s])

    if stage_filter and stage_filter != "All Stages":
        where_clauses.append("c.pipeline_stage = %s")
        params.append(stage_filter)

    if score_filter == "80%+":
        where_clauses.append(
            "COALESCE(ar.overall_score, 0) >= 0.80"
        )

    elif score_filter == "60–79%":
        where_clauses.append(
            "COALESCE(ar.overall_score, 0) BETWEEN 0.60 AND 0.799"
        )

    elif score_filter == "Below 60%":
        where_clauses.append(
            "COALESCE(ar.overall_score, 0) < 0.60"
        )

    where_sql = " AND ".join(where_clauses)

    order_map = {
        "score_desc": "COALESCE(ar.overall_score, 0) DESC",
        "score_asc": "COALESCE(ar.overall_score, 0) ASC",
        "newest": "c.created_at DESC",
        "name_asc": "c.name ASC",
    }

    order_sql = order_map.get(
        sort_by,
        "COALESCE(ar.overall_score, 0) DESC",
    )

    base_query = f"""
        FROM candidates c
        LEFT JOIN analysis_results ar
            ON ar.candidate_id = c.id
        WHERE {where_sql}
    """

    with get_db() as db:
        with db.cursor() as cur:

            # Total count
            cur.execute(
                f"""
                SELECT COUNT(*)
                {base_query}
                """,
                params,
            )

            total_row = cur.fetchone()
            total = int(total_row[0])

            # Pagination
            offset = (page - 1) * page_size

            cur.execute(
                f"""
                SELECT
                    c.*,
                    ar.overall_score,
                    ar.skill_match,
                    ar.semantic_match,
                    ar.experience_score,
                    ar.recommendation,
                    ar.missing_skills,
                    ar.reasoning,
                    ar.status AS analysis_status,
                    ar.rank_position
                {base_query}
                ORDER BY {order_sql}
                LIMIT %s OFFSET %s
                """,
                params + [page_size, offset],
            )

            rows = cur.fetchall()

            result = _rows_to_dict(cur, rows)

    return result, total


def get_candidates_by_stage(
    company_id: int,
    jd_id: Optional[int],
    stage: str,
) -> list[dict[str, Any]]:
    """Return all candidates in a given pipeline stage."""

    rows, _ = list_candidates(
        company_id,
        jd_id=jd_id,
        stage_filter=stage,
        page_size=500,
    )

    return rows


def update_pipeline_stage(
    candidate_db_id: int,
    stage: str,
) -> None:
    """Update candidate pipeline stage."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                UPDATE candidates
                SET
                    pipeline_stage = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (stage, candidate_db_id),
            )


def shortlist_candidate(
    candidate_db_id: int,
    company_id: int,
    jd_id: int,
    user_id: int,
) -> None:
    """Mark candidate as shortlisted."""

    with get_db() as db:
        with db.cursor() as cur:

            cur.execute(
                """
                UPDATE candidates
                SET
                    is_shortlisted = TRUE,
                    pipeline_stage = 'SHORTLISTED',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (candidate_db_id,),
            )

            # SQLite INSERT OR REPLACE equivalent.
            # Delete existing record first, then insert.
            cur.execute(
                """
                DELETE FROM shortlisted_candidates
                WHERE candidate_id = %s
                """,
                (candidate_db_id,),
            )

            cur.execute(
                """
                INSERT INTO shortlisted_candidates
                (
                    candidate_id,
                    company_id,
                    jd_id,
                    shortlisted_by
                )
                VALUES
                (%s, %s, %s, %s)
                """,
                (
                    candidate_db_id,
                    company_id,
                    jd_id,
                    user_id,
                ),
            )


def reject_candidate(candidate_db_id: int) -> None:
    """Mark candidate as rejected."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                UPDATE candidates
                SET
                    is_rejected = TRUE,
                    pipeline_stage = 'REJECTED',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (candidate_db_id,),
            )


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

def add_note(
    candidate_db_id: int,
    user_id: int,
    note_text: str,
) -> int:
    """Add recruiter note. Returns note id."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO candidate_notes
                    (candidate_id, user_id, note_text)
                VALUES
                    (%s, %s, %s)
                RETURNING id
                """,
                (
                    candidate_db_id,
                    user_id,
                    note_text,
                ),
            )

            row = cur.fetchone()
            return int(row[0])


def get_notes(
    candidate_db_id: int,
) -> list[dict[str, Any]]:
    """Return all notes for candidate, newest first."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT
                    n.*,
                    u.name AS author_name
                FROM candidate_notes n
                LEFT JOIN users u
                    ON n.user_id = u.id
                WHERE n.candidate_id = %s
                ORDER BY n.created_at DESC
                """,
                (candidate_db_id,),
            )

            rows = cur.fetchall()

            return _rows_to_dict(cur, rows)


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

def add_timeline_event(
    candidate_db_id: int,
    event_type: str,
    detail: str = "",
    user_id: Optional[int] = None,
) -> None:
    """Append a timeline event."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO candidate_timeline
                    (
                        candidate_id,
                        user_id,
                        event_type,
                        event_detail
                    )
                VALUES
                    (%s, %s, %s, %s)
                """,
                (
                    candidate_db_id,
                    user_id,
                    event_type,
                    detail,
                ),
            )


def get_timeline(
    candidate_db_id: int,
) -> list[dict[str, Any]]:
    """Return timeline events for candidate, oldest first."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT
                    t.*,
                    u.name AS actor_name
                FROM candidate_timeline t
                LEFT JOIN users u
                    ON t.user_id = u.id
                WHERE t.candidate_id = %s
                ORDER BY t.created_at ASC
                """,
                (candidate_db_id,),
            )

            rows = cur.fetchall()

            return _rows_to_dict(cur, rows)


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def get_candidate_analysis(
    candidate_db_id: int,
) -> Optional[dict[str, Any]]:
    """Return latest analysis result for candidate."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM analysis_results
                WHERE candidate_id = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (candidate_db_id,),
            )

            row = cur.fetchone()

            if not row:
                return None

            result = _row_to_dict(cur, row)

    for field in [
        "strengths",
        "weaknesses",
        "missing_skills",
    ]:
        try:
            value = result.get(field)

            if isinstance(value, str):
                result[field] = json.loads(value)

            elif value is None:
                result[field] = []

        except (json.JSONDecodeError, TypeError):
            result[field] = []

    return result


# ---------------------------------------------------------------------------
# Resume upload
# ---------------------------------------------------------------------------

def candidate_exists_by_hash(
    company_id: int,
    jd_id: int,
    file_hash: str,
) -> bool:
    """Check if resume with file hash already exists."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM resume_uploads
                WHERE company_id = %s
                  AND jd_id = %s
                  AND file_hash = %s
                LIMIT 1
                """,
                (
                    company_id,
                    jd_id,
                    file_hash,
                ),
            )

            return cur.fetchone() is not None


def schedule_interview(
    candidate_db_id: int,
    company_id: int,
    jd_id: int,
    user_id: int,
    interview_data: dict,
) -> int:
    """Upsert interview record for candidate."""

    with get_db() as db:
        with db.cursor() as cur:

            cur.execute(
                """
                SELECT id
                FROM recruitment_pipeline
                WHERE candidate_id = %s
                LIMIT 1
                """,
                (candidate_db_id,),
            )

            existing = cur.fetchone()

            if existing:

                cur.execute(
                    """
                    UPDATE recruitment_pipeline
                    SET
                        interview_date = %s,
                        interview_time = %s,
                        round_name = %s,
                        interviewer = %s,
                        meeting_link = %s,
                        updated_by = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE candidate_id = %s
                    """,
                    (
                        interview_data.get("date", ""),
                        interview_data.get("time", ""),
                        interview_data.get("round", ""),
                        interview_data.get("interviewer", ""),
                        interview_data.get("link", ""),
                        user_id,
                        candidate_db_id,
                    ),
                )

                return int(existing[0])

            cur.execute(
                """
                INSERT INTO recruitment_pipeline
                (
                    candidate_id,
                    company_id,
                    jd_id,
                    stage,
                    interview_date,
                    interview_time,
                    round_name,
                    interviewer,
                    meeting_link,
                    updated_by
                )
                VALUES
                (
                    %s, %s, %s,
                    'INTERVIEW_SCHEDULED',
                    %s, %s, %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    candidate_db_id,
                    company_id,
                    jd_id,
                    interview_data.get("date", ""),
                    interview_data.get("time", ""),
                    interview_data.get("round", ""),
                    interview_data.get("interviewer", ""),
                    interview_data.get("link", ""),
                    user_id,
                ),
            )

            row = cur.fetchone()

            return int(row[0])


def get_interview(
    candidate_db_id: int,
) -> Optional[dict[str, Any]]:
    """Return interview record for candidate."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM recruitment_pipeline
                WHERE candidate_id = %s
                LIMIT 1
                """,
                (candidate_db_id,),
            )

            row = cur.fetchone()

            if not row:
                return None

            return _row_to_dict(cur, row)


# ---------------------------------------------------------------------------
# Upload records
# ---------------------------------------------------------------------------

def save_upload_record(
    company_id: int,
    jd_id: int,
    uploaded_by: int,
    filename: str,
    file_path: str,
    file_size: int,
    file_hash: str,
    status: str = "uploaded",
) -> int:
    """Save resume upload record. Returns upload id."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO resume_uploads
                (
                    company_id,
                    jd_id,
                    uploaded_by,
                    filename,
                    file_path,
                    file_size,
                    file_hash,
                    status
                )
                VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    company_id,
                    jd_id,
                    uploaded_by,
                    filename,
                    file_path,
                    file_size,
                    file_hash,
                    status,
                ),
            )

            row = cur.fetchone()

            return int(row[0])


def update_upload_status(
    upload_id: int,
    status: str,
    error_message: str = "",
) -> None:

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                UPDATE resume_uploads
                SET
                    status = %s,
                    error_message = %s
                WHERE id = %s
                """,
                (
                    status,
                    error_message,
                    upload_id,
                ),
            )


def get_recent_uploads(
    company_id: int,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return most recent upload records."""

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT
                    ru.*,
                    u.name AS uploader_name
                FROM resume_uploads ru
                LEFT JOIN users u
                    ON ru.uploaded_by = u.id
                WHERE ru.company_id = %s
                ORDER BY ru.created_at DESC
                LIMIT %s
                """,
                (
                    company_id,
                    limit,
                ),
            )

            rows = cur.fetchall()

            return _rows_to_dict(cur, rows)


def delete_upload_record(
    upload_id: int,
    company_id: int,
) -> Optional[str]:
    """
    Delete upload record and linked candidate records.

    Returns original file path so caller can remove stored resume file.
    """

    from backend.repositories import jd_repo

    with get_db() as db:
        with db.cursor() as cur:

            cur.execute(
                """
                SELECT
                    id,
                    company_id,
                    jd_id,
                    file_path,
                    status
                FROM resume_uploads
                WHERE id = %s
                  AND company_id = %s
                LIMIT 1
                """,
                (
                    upload_id,
                    company_id,
                ),
            )

            upload_row = cur.fetchone()

            if not upload_row:
                return None

            upload_columns = [
                desc[0]
                for desc in cur.description
            ]

            upload = dict(
                zip(upload_columns, upload_row)
            )

            cur.execute(
                """
                SELECT id
                FROM candidates
                WHERE company_id = %s
                  AND jd_id = %s
                  AND upload_id = %s
                """,
                (
                    company_id,
                    upload["jd_id"],
                    upload_id,
                ),
            )

            candidate_rows = cur.fetchall()

            for candidate_row in candidate_rows:

                candidate_id = int(candidate_row[0])

                cur.execute(
                    "DELETE FROM candidate_skills WHERE candidate_id = %s",
                    (candidate_id,),
                )

                cur.execute(
                    "DELETE FROM candidate_experience WHERE candidate_id = %s",
                    (candidate_id,),
                )

                cur.execute(
                    "DELETE FROM candidate_education WHERE candidate_id = %s",
                    (candidate_id,),
                )

                cur.execute(
                    "DELETE FROM candidate_projects WHERE candidate_id = %s",
                    (candidate_id,),
                )

                cur.execute(
                    "DELETE FROM candidate_certificates WHERE candidate_id = %s",
                    (candidate_id,),
                )

                cur.execute(
                    "DELETE FROM candidate_notes WHERE candidate_id = %s",
                    (candidate_id,),
                )

                cur.execute(
                    "DELETE FROM candidate_timeline WHERE candidate_id = %s",
                    (candidate_id,),
                )

                cur.execute(
                    "DELETE FROM recruitment_pipeline WHERE candidate_id = %s",
                    (candidate_id,),
                )

                cur.execute(
                    "DELETE FROM shortlisted_candidates WHERE candidate_id = %s",
                    (candidate_id,),
                )

                cur.execute(
                    "DELETE FROM analysis_results WHERE candidate_id = %s",
                    (candidate_id,),
                )

                cur.execute(
                    "DELETE FROM candidates WHERE id = %s",
                    (candidate_id,),
                )

            cur.execute(
                """
                DELETE FROM resume_uploads
                WHERE id = %s
                  AND company_id = %s
                """,
                (
                    upload_id,
                    company_id,
                ),
            )

            if upload["status"] == "completed":
                # We are inside the same transaction here.
                # Decrement directly instead of opening another connection.
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
                    (upload["jd_id"],),
                )

            return upload["file_path"]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _save_skills(
    candidate_db_id: int,
    skills: list,
) -> None:

    with get_db() as db:
        with db.cursor() as cur:

            for skill in skills:

                if isinstance(skill, dict):

                    cur.execute(
                        """
                        INSERT INTO candidate_skills
                        (
                            candidate_id,
                            name,
                            proficiency,
                            duration_months
                        )
                        VALUES
                        (%s, %s, %s, %s)
                        """,
                        (
                            candidate_db_id,
                            skill.get("name", ""),
                            skill.get(
                                "proficiency",
                                "intermediate",
                            ),
                            skill.get(
                                "duration_months",
                                0,
                            ),
                        ),
                    )

                elif isinstance(skill, str):

                    cur.execute(
                        """
                        INSERT INTO candidate_skills
                            (candidate_id, name)
                        VALUES
                            (%s, %s)
                        """,
                        (
                            candidate_db_id,
                            skill,
                        ),
                    )


def _save_experience(
    candidate_db_id: int,
    experience: list,
) -> None:

    with get_db() as db:
        with db.cursor() as cur:

            for exp in experience:

                if isinstance(exp, dict):

                    cur.execute(
                        """
                        INSERT INTO candidate_experience
                        (
                            candidate_id,
                            company,
                            title,
                            duration_months,
                            description
                        )
                        VALUES
                        (%s, %s, %s, %s, %s)
                        """,
                        (
                            candidate_db_id,
                            exp.get("company", ""),
                            exp.get("title", ""),
                            exp.get("duration_months", 0),
                            exp.get("description", ""),
                        ),
                    )


def _save_education(
    candidate_db_id: int,
    education: list,
) -> None:

    with get_db() as db:
        with db.cursor() as cur:

            for edu in education:

                if isinstance(edu, str):

                    cur.execute(
                        """
                        INSERT INTO candidate_education
                            (candidate_id, degree)
                        VALUES
                            (%s, %s)
                        """,
                        (
                            candidate_db_id,
                            edu,
                        ),
                    )

                elif isinstance(edu, dict):

                    cur.execute(
                        """
                        INSERT INTO candidate_education
                        (
                            candidate_id,
                            degree,
                            institution,
                            year
                        )
                        VALUES
                        (%s, %s, %s, %s)
                        """,
                        (
                            candidate_db_id,
                            edu.get("degree", ""),
                            edu.get("institution", ""),
                            edu.get("year", ""),
                        ),
                    )


def _save_projects(
    candidate_db_id: int,
    projects: list,
) -> None:

    with get_db() as db:
        with db.cursor() as cur:

            for project in projects:

                if isinstance(project, str):

                    cur.execute(
                        """
                        INSERT INTO candidate_projects
                            (candidate_id, name)
                        VALUES
                            (%s, %s)
                        """,
                        (
                            candidate_db_id,
                            project[:200],
                        ),
                    )

                elif isinstance(project, dict):

                    cur.execute(
                        """
                        INSERT INTO candidate_projects
                        (
                            candidate_id,
                            name,
                            description,
                            technologies
                        )
                        VALUES
                        (%s, %s, %s, %s)
                        """,
                        (
                            candidate_db_id,
                            project.get("name", ""),
                            project.get("description", ""),
                            project.get("technologies", ""),
                        ),
                    )


def _save_certificates(
    candidate_db_id: int,
    certs: list,
) -> None:

    with get_db() as db:
        with db.cursor() as cur:

            for cert in certs:

                if isinstance(cert, str):

                    cur.execute(
                        """
                        INSERT INTO candidate_certificates
                            (candidate_id, name)
                        VALUES
                            (%s, %s)
                        """,
                        (
                            candidate_db_id,
                            cert[:200],
                        ),
                    )

                elif isinstance(cert, dict):

                    cur.execute(
                        """
                        INSERT INTO candidate_certificates
                        (
                            candidate_id,
                            name,
                            issuer,
                            year
                        )
                        VALUES
                        (%s, %s, %s, %s)
                        """,
                        (
                            candidate_db_id,
                            cert.get("name", ""),
                            cert.get("issuer", ""),
                            cert.get("year", ""),
                        ),
                    )


# ---------------------------------------------------------------------------
# Related data getters
# ---------------------------------------------------------------------------

def get_candidate_skills(
    candidate_db_id: int,
) -> list[dict[str, Any]]:

    with get_db() as db:
        with db.cursor() as cur:

            cur.execute(
                """
                SELECT *
                FROM candidate_skills
                WHERE candidate_id = %s
                ORDER BY duration_months DESC
                """,
                (candidate_db_id,),
            )

            rows = cur.fetchall()

            return _rows_to_dict(cur, rows)


def get_candidate_experience(
    candidate_db_id: int,
) -> list[dict[str, Any]]:

    with get_db() as db:
        with db.cursor() as cur:

            cur.execute(
                """
                SELECT *
                FROM candidate_experience
                WHERE candidate_id = %s
                """,
                (candidate_db_id,),
            )

            rows = cur.fetchall()

            return _rows_to_dict(cur, rows)


def get_candidate_education(
    candidate_db_id: int,
) -> list[dict[str, Any]]:

    with get_db() as db:
        with db.cursor() as cur:

            cur.execute(
                """
                SELECT *
                FROM candidate_education
                WHERE candidate_id = %s
                """,
                (candidate_db_id,),
            )

            rows = cur.fetchall()

            return _rows_to_dict(cur, rows)


def get_candidate_projects(
    candidate_db_id: int,
) -> list[dict[str, Any]]:

    with get_db() as db:
        with db.cursor() as cur:

            cur.execute(
                """
                SELECT *
                FROM candidate_projects
                WHERE candidate_id = %s
                """,
                (candidate_db_id,),
            )

            rows = cur.fetchall()

            return _rows_to_dict(cur, rows)


def get_candidate_certificates(
    candidate_db_id: int,
) -> list[dict[str, Any]]:

    with get_db() as db:
        with db.cursor() as cur:

            cur.execute(
                """
                SELECT *
                FROM candidate_certificates
                WHERE candidate_id = %s
                """,
                (candidate_db_id,),
            )

            rows = cur.fetchall()

            return _rows_to_dict(cur, rows)