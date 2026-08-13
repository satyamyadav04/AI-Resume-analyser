"""
backend/services/dataset_service.py - Import challenge dataset into the ATS.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from backend.database.db import get_db, get_project_root
from backend.repositories import analysis_repo, candidate_repo, jd_repo
from backend.services import jd_service

DATASET_TITLE = "India Data and AI Challenge Role"
DATASET_ROOT = (
    get_project_root()
    / "data"
    / "recruitment_dataset"
    / "[PUB] India_runs_data_and_ai_challenge"
    / "India_runs_data_and_ai_challenge"
)
DATASET_CANDIDATES_PATH = DATASET_ROOT / "candidates.jsonl"
DATASET_JD_PATH = DATASET_ROOT / "job_description.docx"


def ensure_dataset_job_description(company_id: int, user_id: int) -> dict[str, Any]:
    """Create or activate the dataset JD and return it."""
    existing = _find_dataset_jd(company_id)
    if existing:
        jd_service.activate_jd(company_id, int(existing["id"]))
        return jd_service.get_active_jd(company_id) or existing

    jd_text = load_dataset_jd_text()
    jd_id = jd_service.create_job_description(
        company_id=company_id,
        user_id=user_id,
        title=DATASET_TITLE,
        description=jd_text,
        requirements=_extract_requirements(jd_text),
        make_active=True,
    )
    active = jd_service.get_active_jd(company_id)
    if not active:
        raise ValueError("Dataset JD could not be activated.")
    active["id"] = jd_id
    return active


def load_dataset_jd_text() -> str:
    """Load the challenge JD from docx, with a stable fallback."""
    if DATASET_JD_PATH.exists():
        try:
            from docx import Document

            doc = Document(str(DATASET_JD_PATH))
            text = "\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())
            if text:
                return text
        except Exception:
            pass

    return (
        "Data and AI role requiring strong Python, SQL, machine learning, data engineering, "
        "NLP, Spark, cloud platforms, analytics, and production ML experience."
    )


def import_challenge_candidates(
    company_id: int,
    jd_id: int,
    user_id: int,
    limit: int = 50,
    dataset_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Import candidates from the challenge JSONL into the active ATS database."""
    path = dataset_path or DATASET_CANDIDATES_PATH
    if not path.exists():
        raise FileNotFoundError(f"Dataset candidates file not found: {path}")

    jd = jd_repo.get_jd(jd_id)
    if not jd or int(jd["company_id"]) != int(company_id):
        raise ValueError("A valid active JD is required before importing dataset candidates.")

    jd_text = " ".join([jd.get("title", ""), jd.get("description", ""), jd.get("requirements", "")])
    jd_terms = _important_terms(jd_text)

    imported = 0
    skipped = 0
    last_candidate_id: Optional[int] = None

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if imported >= limit:
                break
            if not line.strip():
                continue

            raw = json.loads(line)
            candidate_uid = str(raw.get("candidate_id", "")).strip()
            if not candidate_uid or _candidate_exists(company_id, jd_id, candidate_uid):
                skipped += 1
                continue

            candidate = _map_dataset_candidate(raw)
            candidate_db_id = candidate_repo.save_candidate(
                company_id=company_id,
                jd_id=jd_id,
                upload_id=None,
                candidate_dict=candidate,
            )
            analysis_repo.save_analysis(
                candidate_db_id=candidate_db_id,
                jd_id=jd_id,
                scores=_score_dataset_candidate(raw, candidate, jd_terms, imported + 1),
            )
            candidate_repo.add_timeline_event(
                candidate_db_id,
                "Dataset Imported",
                f"Imported from challenge dataset record {candidate_uid}.",
                user_id,
            )
            jd_repo.increment_resume_count(jd_id)
            imported += 1
            last_candidate_id = candidate_db_id

    return {
        "imported": imported,
        "skipped": skipped,
        "last_candidate_id": last_candidate_id,
        "dataset_path": str(path),
    }


def _find_dataset_jd(company_id: int) -> Optional[dict[str, Any]]:
    for jd in jd_service.list_job_descriptions(company_id):
        if jd.get("title") == DATASET_TITLE:
            return jd
    return None


def _candidate_exists(company_id: int, jd_id: int, candidate_uid: str) -> bool:
    with get_db() as db:
        row = db.execute(
            """
            SELECT 1
            FROM candidates
            WHERE company_id = ? AND jd_id = ? AND candidate_uid = ?
            LIMIT 1
            """,
            (company_id, jd_id, candidate_uid),
        ).fetchone()
        return row is not None


def _map_dataset_candidate(raw: dict[str, Any]) -> dict[str, Any]:
    profile = raw.get("profile", {}) or {}
    candidate_uid = str(raw.get("candidate_id", "")).strip()
    mapped_profile = {
        "current_title": profile.get("current_title", ""),
        "summary": profile.get("summary", ""),
        "location": profile.get("location", ""),
        "github": "",
        "linkedin": "",
    }

    return {
        "candidate_id": candidate_uid,
        "name": profile.get("anonymized_name") or candidate_uid or "Dataset Candidate",
        "email": f"{candidate_uid.lower()}@dataset.local" if candidate_uid else "",
        "phone": "",
        "experience_years": float(profile.get("years_of_experience") or 0.0),
        "profile": mapped_profile,
        "skills": raw.get("skills", []) or [],
        "experience": raw.get("career_history", []) or [],
        "education": [_map_education(row) for row in raw.get("education", []) or []],
        "certifications": raw.get("certifications", []) or [],
        "projects": [],
    }


def _map_education(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "degree": row.get("degree", ""),
        "institution": row.get("institution", ""),
        "year": row.get("end_year", ""),
        "score": row.get("grade", ""),
    }


def _score_dataset_candidate(
    raw: dict[str, Any],
    candidate: dict[str, Any],
    jd_terms: set[str],
    rank_position: int,
) -> dict[str, Any]:
    skills = {str(s.get("name", "")).strip().lower() for s in candidate.get("skills", []) if isinstance(s, dict)}
    skill_match = _ratio(len(skills & jd_terms), max(len(jd_terms), 1))

    profile = raw.get("profile", {}) or {}
    summary_terms = _important_terms(
        " ".join(
            [
                profile.get("headline", ""),
                profile.get("summary", ""),
                " ".join(exp.get("description", "") for exp in raw.get("career_history", []) or []),
            ]
        )
    )
    semantic_match = _ratio(len(summary_terms & jd_terms), max(len(jd_terms), 1))

    years = float(candidate.get("experience_years") or 0.0)
    experience_score = min(years / 8.0, 1.0)
    signals = raw.get("redrob_signals", {}) or {}
    availability = _availability_score(signals)
    education_score = _education_score(raw.get("education", []) or [])
    project_score = 0.35 if any(term in summary_terms for term in {"rag", "ml", "machine", "ai", "model"}) else 0.2

    overall = (
        (0.38 * skill_match)
        + (0.27 * semantic_match)
        + (0.18 * experience_score)
        + (0.10 * availability)
        + (0.07 * education_score)
    )
    overall = max(0.05, min(overall, 0.98))
    recommendation = _recommendation(overall)

    missing_skills = sorted(jd_terms - skills)[:10]
    strengths = _strengths(skills, years, signals)
    weaknesses = _weaknesses(missing_skills, signals)

    return {
        "overall_score": overall,
        "skill_match": skill_match,
        "semantic_match": semantic_match,
        "experience_score": experience_score,
        "education_score": education_score,
        "project_score": project_score,
        "ai_summary": _summary(candidate, overall, skill_match, semantic_match),
        "recommendation": recommendation,
        "reasoning": (
            f"Dataset candidate scored with skill overlap {skill_match:.0%}, "
            f"JD text overlap {semantic_match:.0%}, and {years:.1f} years of experience."
        ),
        "strengths": strengths,
        "weaknesses": weaknesses,
        "missing_skills": missing_skills,
        "status": "CLEAN",
        "rank_position": rank_position,
    }


def _extract_requirements(jd_text: str) -> str:
    terms = sorted(_important_terms(jd_text))
    return ", ".join(terms[:30])


def _important_terms(text: str) -> set[str]:
    allowlist = {
        "ai",
        "airflow",
        "analytics",
        "aws",
        "azure",
        "cloud",
        "data",
        "deep",
        "docker",
        "etl",
        "gcp",
        "kafka",
        "kubernetes",
        "llm",
        "machine",
        "ml",
        "mlops",
        "model",
        "nlp",
        "python",
        "rag",
        "spark",
        "sql",
        "statistics",
        "tensorflow",
        "pytorch",
    }
    tokens = set(re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{1,}", text.lower()))
    return {token for token in tokens if token in allowlist}


def _availability_score(signals: dict[str, Any]) -> float:
    score = 0.5
    if signals.get("open_to_work_flag"):
        score += 0.2
    if signals.get("verified_email"):
        score += 0.1
    notice = signals.get("notice_period_days")
    if isinstance(notice, (int, float)):
        score += 0.2 if notice <= 30 else 0.1 if notice <= 60 else 0.0
    return min(score, 1.0)


def _education_score(education: list[dict[str, Any]]) -> float:
    text = " ".join(str(row.get("degree", "")) for row in education).lower()
    if any(key in text for key in ["ph.d", "phd"]):
        return 1.0
    if any(key in text for key in ["m.tech", "m.s", "master"]):
        return 0.85
    if any(key in text for key in ["b.tech", "b.e", "bachelor"]):
        return 0.7
    return 0.5 if education else 0.3


def _recommendation(score: float) -> str:
    if score >= 0.75:
        return "Strong Fit"
    if score >= 0.55:
        return "Good Fit"
    if score >= 0.35:
        return "Possible Fit"
    return "Not a Fit"


def _strengths(skills: set[str], years: float, signals: dict[str, Any]) -> list[str]:
    strengths = []
    if skills:
        strengths.append("Relevant dataset skills: " + ", ".join(sorted(skills)[:6]))
    if years >= 5:
        strengths.append(f"Strong experience depth ({years:.1f} years)")
    if signals.get("open_to_work_flag"):
        strengths.append("Candidate is open to work")
    return strengths[:5]


def _weaknesses(missing_skills: list[str], signals: dict[str, Any]) -> list[str]:
    weaknesses = []
    if missing_skills:
        weaknesses.append("Missing key JD skills: " + ", ".join(missing_skills[:5]))
    if not signals.get("verified_email", True):
        weaknesses.append("Email is not verified in source dataset")
    return weaknesses[:5]


def _summary(candidate: dict[str, Any], overall: float, skill_match: float, semantic_match: float) -> str:
    return (
        f"{candidate.get('name', 'This candidate')} was imported from the challenge dataset. "
        f"Overall fit is {overall:.0%}, with {skill_match:.0%} skill overlap and "
        f"{semantic_match:.0%} JD text overlap."
    )


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return max(0.0, min(float(numerator) / float(denominator), 1.0))
