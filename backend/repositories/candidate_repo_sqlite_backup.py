"""
backend/repositories/candidate_repo.py — Candidate CRUD + Pipeline + Notes + Timeline
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


def save_candidate(
    company_id: int,
    jd_id: int,
    upload_id: Optional[int],
    candidate_dict: dict[str, Any],python -c "from backend.repositories.jd_repo import get_active_jd; print(get_active_jd(3))"python -c "import psycopg2; print('psycopg2 OK')"
) -> int:
    """Insert core candidate record. Returns new candidate DB id."""
    profile = candidate_dict.get("profile", {}) or {}
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO candidates
               (company_id, jd_id, upload_id, candidate_uid, name, email, phone,
                location, current_title, experience_years, summary, github, linkedin,
                pipeline_stage)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'AI_ANALYZED')""",
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
        candidate_db_id = cur.lastrowid

    # Save skills
    skills = candidate_dict.get("skills", []) or []
    _save_skills(candidate_db_id, skills)

    # Save experience
    experience = candidate_dict.get("experience", []) or []
    _save_experience(candidate_db_id, experience)

    # Save education
    education = candidate_dict.get("education", []) or []
    _save_education(candidate_db_id, education)

    # Save projects
    projects = candidate_dict.get("projects", []) or []
    _save_projects(candidate_db_id, projects)

    # Save certifications
    certs = candidate_dict.get("certifications", []) or []
    _save_certificates(candidate_db_id, certs)

    return candidate_db_id


def get_candidate(candidate_db_id: int) -> Optional[dict[str, Any]]:
    """Return full candidate dict including related data, or None."""
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM candidates WHERE id = ? LIMIT 1", (candidate_db_id,)
        ).fetchone()
        if not row:
            return None
        candidate = dict(row)

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
    """Return paginated candidates with their analysis scores. Returns (rows, total_count)."""
    params: list[Any] = [company_id]
    where_clauses = ["c.company_id = ?"]

    if jd_id:
        where_clauses.append("c.jd_id = ?")
        params.append(jd_id)

    if search:
        where_clauses.append("(c.name LIKE ? OR c.email LIKE ? OR c.current_title LIKE ?)")
        s = f"%{search}%"
        params += [s, s, s]

    if stage_filter and stage_filter != "All Stages":
        where_clauses.append("c.pipeline_stage = ?")
        params.append(stage_filter)

    if score_filter == "80%+":
        where_clauses.append("COALESCE(ar.overall_score, 0) >= 0.80")
    elif score_filter == "60–79%":
        where_clauses.append("COALESCE(ar.overall_score, 0) BETWEEN 0.60 AND 0.799")
    elif score_filter == "Below 60%":
        where_clauses.append("COALESCE(ar.overall_score, 0) < 0.60")

    where_sql = " AND ".join(where_clauses)

    order_map = {
        "score_desc": "COALESCE(ar.overall_score, 0) DESC",
        "score_asc": "COALESCE(ar.overall_score, 0) ASC",
        "newest": "c.created_at DESC",
        "name_asc": "c.name ASC",
    }
    order_sql = order_map.get(sort_by, "COALESCE(ar.overall_score, 0) DESC")

    base_query = f"""
        FROM candidates c
        LEFT JOIN analysis_results ar ON ar.candidate_id = c.id
        WHERE {where_sql}
    """

    with get_db() as db:
        total = db.execute(
            f"SELECT COUNT(*) {base_query}", params
        ).fetchone()[0]

        offset = (page - 1) * page_size
        rows = db.execute(
            f"""SELECT c.*, ar.overall_score, ar.skill_match, ar.semantic_match,
                       ar.experience_score, ar.recommendation, ar.missing_skills,
                       ar.reasoning, ar.status as analysis_status, ar.rank_position
                {base_query}
                ORDER BY {order_sql}
                LIMIT ? OFFSET ?""",
            params + [page_size, offset],
        ).fetchall()

    return [dict(r) for r in rows], total


def get_candidates_by_stage(company_id: int, jd_id: Optional[int], stage: str) -> list[dict[str, Any]]:
    """Return all candidates in a given pipeline stage."""
    rows, _ = list_candidates(company_id, jd_id=jd_id, stage_filter=stage, page_size=500)
    return rows


def update_pipeline_stage(candidate_db_id: int, stage: str) -> None:
    """Update a candidate's pipeline stage."""
    with get_db() as db:
        db.execute(
            "UPDATE candidates SET pipeline_stage = ?, updated_at = datetime('now') WHERE id = ?",
            (stage, candidate_db_id),
        )


def shortlist_candidate(candidate_db_id: int, company_id: int, jd_id: int, user_id: int) -> None:
    """Mark candidate as shortlisted and insert shortlisted_candidates record."""
    with get_db() as db:
        db.execute(
            "UPDATE candidates SET is_shortlisted = 1, pipeline_stage = 'SHORTLISTED', updated_at = datetime('now') WHERE id = ?",
            (candidate_db_id,),
        )
        db.execute(
            """INSERT OR REPLACE INTO shortlisted_candidates
               (candidate_id, company_id, jd_id, shortlisted_by)
               VALUES (?, ?, ?, ?)""",
            (candidate_db_id, company_id, jd_id, user_id),
        )


def reject_candidate(candidate_db_id: int) -> None:
    """Mark candidate as rejected."""
    with get_db() as db:
        db.execute(
            "UPDATE candidates SET is_rejected = 1, pipeline_stage = 'REJECTED', updated_at = datetime('now') WHERE id = ?",
            (candidate_db_id,),
        )


def add_note(candidate_db_id: int, user_id: int, note_text: str) -> int:
    """Add a recruiter note. Returns note id."""
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO candidate_notes (candidate_id, user_id, note_text) VALUES (?, ?, ?)",
            (candidate_db_id, user_id, note_text),
        )
        return cur.lastrowid


def get_notes(candidate_db_id: int) -> list[dict[str, Any]]:
    """Return all notes for a candidate, newest first."""
    with get_db() as db:
        rows = db.execute(
            """SELECT n.*, u.name as author_name
               FROM candidate_notes n
               LEFT JOIN users u ON n.user_id = u.id
               WHERE n.candidate_id = ?
               ORDER BY n.created_at DESC""",
            (candidate_db_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def add_timeline_event(candidate_db_id: int, event_type: str, detail: str = "", user_id: Optional[int] = None) -> None:
    """Append a timeline event."""
    with get_db() as db:
        db.execute(
            "INSERT INTO candidate_timeline (candidate_id, user_id, event_type, event_detail) VALUES (?, ?, ?, ?)",
            (candidate_db_id, user_id, event_type, detail),
        )


def get_timeline(candidate_db_id: int) -> list[dict[str, Any]]:
    """Return timeline events for a candidate, oldest first."""
    with get_db() as db:
        rows = db.execute(
            """SELECT t.*, u.name as actor_name
               FROM candidate_timeline t
               LEFT JOIN users u ON t.user_id = u.id
               WHERE t.candidate_id = ?
               ORDER BY t.created_at ASC""",
            (candidate_db_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_candidate_analysis(candidate_db_id: int) -> Optional[dict[str, Any]]:
    """Return the analysis result for a candidate."""
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM analysis_results WHERE candidate_id = ? ORDER BY id DESC LIMIT 1",
            (candidate_db_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        for field in ["strengths", "weaknesses", "missing_skills"]:
            try:
                result[field] = json.loads(result.get(field, "[]"))
            except (json.JSONDecodeError, TypeError):
                result[field] = []
        return result


def candidate_exists_by_hash(company_id: int, jd_id: int, file_hash: str) -> bool:
    """Check if a resume with this file hash was already uploaded."""
    with get_db() as db:
        row = db.execute(
            "SELECT 1 FROM resume_uploads WHERE company_id = ? AND jd_id = ? AND file_hash = ? LIMIT 1",
            (company_id, jd_id, file_hash),
        ).fetchone()
        return row is not None


def schedule_interview(candidate_db_id: int, company_id: int, jd_id: int, user_id: int, interview_data: dict) -> int:
    """Upsert an interview record for a candidate."""
    with get_db() as db:
        # Check if pipeline record exists
        existing = db.execute(
            "SELECT id FROM recruitment_pipeline WHERE candidate_id = ? LIMIT 1",
            (candidate_db_id,),
        ).fetchone()

        if existing:
            db.execute(
                """UPDATE recruitment_pipeline SET
                   interview_date = ?, interview_time = ?, round_name = ?,
                   interviewer = ?, meeting_link = ?, updated_by = ?,
                   updated_at = datetime('now')
                   WHERE candidate_id = ?""",
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
            return existing["id"]
        else:
            cur = db.execute(
                """INSERT INTO recruitment_pipeline
                   (candidate_id, company_id, jd_id, stage, interview_date, interview_time,
                    round_name, interviewer, meeting_link, updated_by)
                   VALUES (?, ?, ?, 'INTERVIEW_SCHEDULED', ?, ?, ?, ?, ?, ?)""",
                (
                    candidate_db_id, company_id, jd_id,
                    interview_data.get("date", ""),
                    interview_data.get("time", ""),
                    interview_data.get("round", ""),
                    interview_data.get("interviewer", ""),
                    interview_data.get("link", ""),
                    user_id,
                ),
            )
            return cur.lastrowid


def get_interview(candidate_db_id: int) -> Optional[dict[str, Any]]:
    """Return interview record for a candidate."""
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM recruitment_pipeline WHERE candidate_id = ? LIMIT 1",
            (candidate_db_id,),
        ).fetchone()
        return dict(row) if row else None


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
    """Save a resume upload record. Returns upload_id."""
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO resume_uploads
               (company_id, jd_id, uploaded_by, filename, file_path, file_size, file_hash, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (company_id, jd_id, uploaded_by, filename, file_path, file_size, file_hash, status),
        )
        return cur.lastrowid


def update_upload_status(upload_id: int, status: str, error_message: str = "") -> None:
    with get_db() as db:
        db.execute(
            "UPDATE resume_uploads SET status = ?, error_message = ? WHERE id = ?",
            (status, error_message, upload_id),
        )


def get_recent_uploads(company_id: int, limit: int = 10) -> list[dict[str, Any]]:
    """Return most recent upload records."""
    with get_db() as db:
        rows = db.execute(
            """SELECT ru.*, u.name as uploader_name
               FROM resume_uploads ru
               LEFT JOIN users u ON ru.uploaded_by = u.id
               WHERE ru.company_id = ?
               ORDER BY ru.created_at DESC LIMIT ?""",
            (company_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_upload_record(upload_id: int, company_id: int) -> Optional[str]:
    """Delete an upload record and any linked candidate analysis records.

    Returns the original file path so the caller can remove the stored resume file.
    """
    from backend.repositories import jd_repo

    with get_db() as db:
        upload_row = db.execute(
            """SELECT id, company_id, jd_id, file_path, status
               FROM resume_uploads
               WHERE id = ? AND company_id = ?
               LIMIT 1""",
            (upload_id, company_id),
        ).fetchone()
        if not upload_row:
            return None

        candidate_rows = db.execute(
            """SELECT id FROM candidates
               WHERE company_id = ? AND jd_id = ? AND upload_id = ?""",
            (company_id, upload_row["jd_id"], upload_id),
        ).fetchall()

        for candidate_row in candidate_rows:
            candidate_id = int(candidate_row["id"])

            db.execute("DELETE FROM candidate_skills WHERE candidate_id = ?", (candidate_id,))
            db.execute("DELETE FROM candidate_experience WHERE candidate_id = ?", (candidate_id,))
            db.execute("DELETE FROM candidate_education WHERE candidate_id = ?", (candidate_id,))
            db.execute("DELETE FROM candidate_projects WHERE candidate_id = ?", (candidate_id,))
            db.execute("DELETE FROM candidate_certificates WHERE candidate_id = ?", (candidate_id,))
            db.execute("DELETE FROM candidate_notes WHERE candidate_id = ?", (candidate_id,))
            db.execute("DELETE FROM candidate_timeline WHERE candidate_id = ?", (candidate_id,))
            db.execute("DELETE FROM recruitment_pipeline WHERE candidate_id = ?", (candidate_id,))
            db.execute("DELETE FROM shortlisted_candidates WHERE candidate_id = ?", (candidate_id,))
            db.execute("DELETE FROM analysis_results WHERE candidate_id = ?", (candidate_id,))
            db.execute("DELETE FROM candidates WHERE id = ?", (candidate_id,))

        db.execute(
            "DELETE FROM resume_uploads WHERE id = ? AND company_id = ?",
            (upload_id, company_id),
        )

        if upload_row["status"] == "completed":
            jd_repo.decrement_resume_count(upload_row["jd_id"])

        return upload_row["file_path"]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _save_skills(candidate_db_id: int, skills: list) -> None:
    with get_db() as db:
        for s in skills:
            if isinstance(s, dict):
                db.execute(
                    """INSERT INTO candidate_skills (candidate_id, name, proficiency, duration_months)
                       VALUES (?, ?, ?, ?)""",
                    (
                        candidate_db_id,
                        s.get("name", ""),
                        s.get("proficiency", "intermediate"),
                        s.get("duration_months", 0),
                    ),
                )
            elif isinstance(s, str):
                db.execute(
                    "INSERT INTO candidate_skills (candidate_id, name) VALUES (?, ?)",
                    (candidate_db_id, s),
                )


def _save_experience(candidate_db_id: int, experience: list) -> None:
    with get_db() as db:
        for exp in experience:
            if isinstance(exp, dict):
                db.execute(
                    """INSERT INTO candidate_experience
                       (candidate_id, company, title, duration_months, description)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        candidate_db_id,
                        exp.get("company", ""),
                        exp.get("title", ""),
                        exp.get("duration_months", 0),
                        exp.get("description", ""),
                    ),
                )


def _save_education(candidate_db_id: int, education: list) -> None:
    with get_db() as db:
        for edu in education:
            if isinstance(edu, str):
                db.execute(
                    "INSERT INTO candidate_education (candidate_id, degree) VALUES (?, ?)",
                    (candidate_db_id, edu),
                )
            elif isinstance(edu, dict):
                db.execute(
                    """INSERT INTO candidate_education (candidate_id, degree, institution, year)
                       VALUES (?, ?, ?, ?)""",
                    (
                        candidate_db_id,
                        edu.get("degree", ""),
                        edu.get("institution", ""),
                        edu.get("year", ""),
                    ),
                )


def _save_projects(candidate_db_id: int, projects: list) -> None:
    with get_db() as db:
        for proj in projects:
            if isinstance(proj, str):
                db.execute(
                    "INSERT INTO candidate_projects (candidate_id, name) VALUES (?, ?)",
                    (candidate_db_id, proj[:200]),
                )
            elif isinstance(proj, dict):
                db.execute(
                    """INSERT INTO candidate_projects (candidate_id, name, description, technologies)
                       VALUES (?, ?, ?, ?)""",
                    (
                        candidate_db_id,
                        proj.get("name", ""),
                        proj.get("description", ""),
                        proj.get("technologies", ""),
                    ),
                )


def _save_certificates(candidate_db_id: int, certs: list) -> None:
    with get_db() as db:
        for cert in certs:
            if isinstance(cert, str):
                db.execute(
                    "INSERT INTO candidate_certificates (candidate_id, name) VALUES (?, ?)",
                    (candidate_db_id, cert[:200]),
                )
            elif isinstance(cert, dict):
                db.execute(
                    """INSERT INTO candidate_certificates (candidate_id, name, issuer, year)
                       VALUES (?, ?, ?, ?)""",
                    (
                        candidate_db_id,
                        cert.get("name", ""),
                        cert.get("issuer", ""),
                        cert.get("year", ""),
                    ),
                )


def get_candidate_skills(candidate_db_id: int) -> list[dict[str, Any]]:
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM candidate_skills WHERE candidate_id = ? ORDER BY duration_months DESC",
            (candidate_db_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_candidate_experience(candidate_db_id: int) -> list[dict[str, Any]]:
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM candidate_experience WHERE candidate_id = ?",
            (candidate_db_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_candidate_education(candidate_db_id: int) -> list[dict[str, Any]]:
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM candidate_education WHERE candidate_id = ?",
            (candidate_db_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_candidate_projects(candidate_db_id: int) -> list[dict[str, Any]]:
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM candidate_projects WHERE candidate_id = ?",
            (candidate_db_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_candidate_certificates(candidate_db_id: int) -> list[dict[str, Any]]:
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM candidate_certificates WHERE candidate_id = ?",
            (candidate_db_id,),
        ).fetchall()
        return [dict(r) for r in rows]
