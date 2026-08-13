"""
backend/services/candidate_service.py - Candidate business logic
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from backend.repositories import candidate_repo, company_repo, jd_repo, user_repo
from backend.repositories.candidate_repo import PIPELINE_STAGES
from backend.services.notification_service import send_interview_schedule_email

logger = logging.getLogger(__name__)

STAGE_LABELS = {
    "NEW": ("New", "primary"),
    "AI_ANALYZED": ("AI Analyzed", "primary"),
    "SHORTLISTED": ("Shortlisted", "success"),
    "INTERVIEW_SCHEDULED": ("Interview", "warning"),
    "TECHNICAL_ROUND": ("Technical", "warning"),
    "HR_ROUND": ("HR Round", "warning"),
    "OFFER_SENT": ("Offer Sent", "success"),
    "HIRED": ("Hired", "success"),
    "REJECTED": ("Rejected", "danger"),
}


def get_ranked_candidates(
    company_id: int,
    jd_id: Optional[int] = None,
    search: str = "",
    stage_filter: Optional[str] = None,
    score_filter: Optional[str] = None,
    sort_by: str = "score_desc",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    """Return ranked candidates with their analysis scores and total count."""
    rows, total = candidate_repo.list_candidates(
        company_id=company_id,
        jd_id=jd_id,
        search=search,
        stage_filter=stage_filter,
        score_filter=score_filter,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )
    for i, row in enumerate(rows):
        row["rank"] = (page - 1) * page_size + i + 1
        row["score_pct"] = int(float(row.get("overall_score", 0.0)) * 100)
        row["skill_match_pct"] = int(float(row.get("skill_match", 0.0)) * 100)
        row["experience_match_pct"] = int(min(float(row.get("experience_years", 0.0)) / 10.0, 1.0) * 100)
        row["stage_label"], row["stage_cls"] = STAGE_LABELS.get(
            row.get("pipeline_stage", "NEW"),
            ("New", "primary"),
        )
        row["skills"] = get_candidate_skills_list(row["id"])
    return rows, total


def get_candidate_profile(candidate_db_id: int) -> Optional[dict[str, Any]]:
    """Return full candidate profile including analysis, skills, experience, etc."""
    candidate = candidate_repo.get_candidate(candidate_db_id)
    if not candidate:
        return None

    analysis = candidate.get("analysis") or {}
    candidate["score_pct"] = int(float(analysis.get("overall_score", 0.0)) * 100)
    candidate["skill_match_pct"] = int(float(analysis.get("skill_match", 0.0)) * 100)
    candidate["semantic_match_pct"] = int(float(analysis.get("semantic_match", 0.0)) * 100)
    candidate["experience_match_pct"] = int(
        min(float(candidate.get("experience_years", 0.0)) / 10.0, 1.0) * 100
    )
    candidate["education_match_pct"] = int(float(analysis.get("education_score", 0.5)) * 100)
    candidate["project_match_pct"] = int(float(analysis.get("project_score", 0.2)) * 100)
    candidate["stage_label"], candidate["stage_cls"] = STAGE_LABELS.get(
        candidate.get("pipeline_stage", "NEW"),
        ("New", "primary"),
    )
    candidate["recommendation"] = analysis.get("recommendation", "-")
    candidate["notes"] = candidate_repo.get_notes(candidate_db_id)
    candidate["timeline"] = candidate_repo.get_timeline(candidate_db_id)
    candidate["interview"] = candidate_repo.get_interview(candidate_db_id)
    return candidate


def move_to_stage(candidate_db_id: int, new_stage: str, user_id: int) -> None:
    """Move a candidate to a new pipeline stage and log it."""
    if new_stage not in PIPELINE_STAGES:
        raise ValueError(f"Invalid stage: {new_stage}")

    candidate_repo.update_pipeline_stage(candidate_db_id, new_stage)
    if new_stage == "SHORTLISTED":
        pass
    elif new_stage == "REJECTED":
        candidate_repo.reject_candidate(candidate_db_id)
        return

    stage_label = STAGE_LABELS.get(new_stage, (new_stage, ""))[0]
    candidate_repo.add_timeline_event(
        candidate_db_id,
        f"Stage Changed -> {stage_label}",
        f"Pipeline stage updated to {new_stage}",
        user_id,
    )
    logger.info("Candidate #%d moved to stage: %s", candidate_db_id, new_stage)


def shortlist_candidate(candidate_db_id: int, company_id: int, jd_id: int, user_id: int) -> None:
    """Shortlist a candidate (also moves to SHORTLISTED stage)."""
    candidate_repo.shortlist_candidate(candidate_db_id, company_id, jd_id, user_id)
    candidate_repo.add_timeline_event(
        candidate_db_id,
        "Shortlisted",
        "Candidate was shortlisted by recruiter.",
        user_id,
    )


def reject_candidate(candidate_db_id: int, user_id: int) -> None:
    """Reject a candidate."""
    candidate_repo.reject_candidate(candidate_db_id)
    candidate_repo.add_timeline_event(
        candidate_db_id,
        "Rejected",
        "Candidate was rejected by recruiter.",
        user_id,
    )


def add_note(candidate_db_id: int, user_id: int, note_text: str) -> None:
    """Add a recruiter note to a candidate."""
    if not note_text.strip():
        raise ValueError("Note cannot be empty.")
    candidate_repo.add_note(candidate_db_id, user_id, note_text.strip())
    candidate_repo.add_timeline_event(
        candidate_db_id,
        "Note Added",
        note_text[:100] + ("..." if len(note_text) > 100 else ""),
        user_id,
    )


def schedule_interview(
    candidate_db_id: int,
    company_id: int,
    jd_id: int,
    user_id: int,
    interview_data: dict,
) -> dict[str, str | bool]:
    """Schedule an interview, update pipeline stage, and notify the candidate."""
    candidate_repo.schedule_interview(candidate_db_id, company_id, jd_id, user_id, interview_data)
    candidate_repo.update_pipeline_stage(candidate_db_id, "INTERVIEW_SCHEDULED")
    candidate_repo.add_timeline_event(
        candidate_db_id,
        "Interview Scheduled",
        f"Round: {interview_data.get('round', '')} | Date: {interview_data.get('date', '')}",
        user_id,
    )

    candidate = candidate_repo.get_candidate(candidate_db_id) or {}
    company = company_repo.get_company(company_id) or {}
    jd = jd_repo.get_jd(jd_id) if jd_id else None
    user = user_repo.get_user_by_id(user_id) or {}

    interview_payload = dict(interview_data)
    if not interview_payload.get("interviewer"):
        interview_payload["interviewer"] = user.get("name", "Hiring Team")

    mail_result = send_interview_schedule_email(
        candidate_email=str(candidate.get("email", "")),
        candidate_name=str(candidate.get("name", "")),
        company_name=str(company.get("name", "")),
        jd_title=str((jd or {}).get("title", "")),
        interview_data=interview_payload,
    )
    candidate_repo.add_timeline_event(
        candidate_db_id,
        "Email Notification",
        str(mail_result.get("message", "")),
        user_id,
    )
    return mail_result


def get_candidates_by_stage(company_id: int, jd_id: Optional[int], stage: str) -> list[dict[str, Any]]:
    """Return all candidates in a given pipeline stage."""
    rows = candidate_repo.get_candidates_by_stage(company_id, jd_id, stage)
    for row in rows:
        row["score_pct"] = int(float(row.get("overall_score", 0.0)) * 100)
        row["skills"] = get_candidate_skills_list(row["id"])
    return rows


def get_candidate_skills_list(candidate_db_id: int) -> list[str]:
    """Return skill names for a candidate."""
    skills = candidate_repo.get_candidate_skills(candidate_db_id)
    return [s["name"] for s in skills[:6] if s.get("name")]


def get_resume_file_path(candidate_db_id: int) -> Optional[str]:
    """Return the file path of a candidate's resume, or None."""
    from backend.database.db import get_db

    with get_db() as db:
        row = db.execute(
            """SELECT ru.file_path FROM candidates c
               JOIN resume_uploads ru ON ru.id = c.upload_id
               WHERE c.id = ? LIMIT 1""",
            (candidate_db_id,),
        ).fetchone()
        return row[0] if row else None
