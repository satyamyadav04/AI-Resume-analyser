"""
backend/services/dataset_service.py - Import challenge dataset into the ATS.

Dataset candidates are scored through the same local ML pipeline used by
uploaded resumes: SentenceTransformer embeddings + cosine similarity +
hybrid scoring.  The repository contains a 50-record sample dataset, so the
application remains deployable even when the larger JSONL dataset is not
present in the deployment image.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from backend.database.db import get_db, get_project_root
from backend.embeddings import EmbeddingPipeline, _RELEVANT_SKILLS
from backend.repositories import analysis_repo, candidate_repo, jd_repo
from backend.scoring import HeuristicFilter, ScoringEngine
from backend.services import jd_service
from backend.utils import ExplanationEngine

DATASET_TITLE = "India Data and AI Challenge Role"
DATASET_ROOT = (
    get_project_root()
    / "data"
    / "recruitment_dataset"
    / "[PUB] India_runs_data_and_ai_challenge"
    / "India_runs_data_and_ai_challenge"
)
DATASET_CANDIDATES_PATH = DATASET_ROOT / "candidates.jsonl"
# This checked-in file is available in the deployed repository.
DATASET_SAMPLE_PATH = DATASET_ROOT / "sample_candidates.json"
DATASET_JD_PATH = DATASET_ROOT / "job_description.docx"

_embedding_pipeline: Optional[EmbeddingPipeline] = None
_scoring_engine: Optional[ScoringEngine] = None
_explainer: Optional[ExplanationEngine] = None


def _get_ml_pipeline() -> EmbeddingPipeline:
    global _embedding_pipeline
    if _embedding_pipeline is None:
        _embedding_pipeline = EmbeddingPipeline()
    return _embedding_pipeline


def _get_scoring_engine() -> ScoringEngine:
    global _scoring_engine
    if _scoring_engine is None:
        _scoring_engine = ScoringEngine(embedding_pipeline=_get_ml_pipeline())
    return _scoring_engine


def _get_explainer() -> ExplanationEngine:
    global _explainer
    if _explainer is None:
        _explainer = ExplanationEngine()
    return _explainer


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


def _resolve_dataset_path(dataset_path: Optional[Path]) -> Path:
    """Prefer the full JSONL dataset, then the checked-in sample dataset."""
    if dataset_path is not None:
        return dataset_path
    if DATASET_CANDIDATES_PATH.exists():
        return DATASET_CANDIDATES_PATH
    if DATASET_SAMPLE_PATH.exists():
        return DATASET_SAMPLE_PATH
    raise FileNotFoundError(
        "Dataset candidates file not found. Expected candidates.jsonl or sample_candidates.json."
    )


def _iter_dataset_records(path: Path):
    """Yield records from JSONL or the checked-in JSON sample."""
    if path.suffix.lower() == ".jsonl":
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)
        return

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON array in dataset file: {path}")
    yield from payload


def import_challenge_candidates(
    company_id: int,
    jd_id: int,
    user_id: int,
    limit: int = 50,
    dataset_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Import and ML-score dataset candidates against the active JD."""
    path = _resolve_dataset_path(dataset_path)

    jd = jd_repo.get_jd(jd_id)
    if not jd or int(jd["company_id"]) != int(company_id):
        raise ValueError("A valid active JD is required before importing dataset candidates.")

    jd_text = " ".join(
        [jd.get("title", ""), jd.get("description", ""), jd.get("requirements", "")]
    ).strip()
    pipeline = _get_ml_pipeline()
    engine = _get_scoring_engine()
    explainer = _get_explainer()
    jd_vector = pipeline._embed(jd_text) if jd_text else pipeline.jd_vector
    jd_skill_terms = _jd_skill_terms(jd_text)

    imported = 0
    skipped = 0
    last_candidate_id: Optional[int] = None

    for raw in _iter_dataset_records(path):
        if imported >= limit:
            break

        candidate_uid = str(raw.get("candidate_id", "")).strip()
        if not candidate_uid or _candidate_exists(company_id, jd_id, candidate_uid):
            skipped += 1
            continue

        candidate = _map_dataset_candidate(raw)
        scores = _score_dataset_candidate(
            raw=raw,
            candidate=candidate,
            pipeline=pipeline,
            engine=engine,
            explainer=explainer,
            jd_vector=jd_vector,
            jd_skill_terms=jd_skill_terms,
        )

        candidate_db_id = candidate_repo.save_candidate(
            company_id=company_id,
            jd_id=jd_id,
            upload_id=None,
            candidate_dict=candidate,
        )
        analysis_repo.save_analysis(
            candidate_db_id=candidate_db_id,
            jd_id=jd_id,
            scores=scores,
        )
        candidate_repo.add_timeline_event(
            candidate_db_id,
            "Dataset Imported",
            f"Imported and ML-scored from {path.name}: {candidate_uid}.",
            user_id,
        )
        candidate_repo.add_timeline_event(
            candidate_db_id,
            "AI Analysis Completed",
            f"Semantic match: {scores['semantic_match']:.1%} | Overall: {scores['overall_score']:.1%}",
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
        "ml_enabled": pipeline.use_transformer,
        "embedding_model": pipeline.model_name if pipeline.use_transformer else "TF-IDF fallback",
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
            WHERE company_id = %s AND jd_id = %s AND candidate_uid = %s
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
    pipeline: EmbeddingPipeline,
    engine: ScoringEngine,
    explainer: ExplanationEngine,
    jd_vector: Any,
    jd_skill_terms: set[str],
) -> dict[str, Any]:
    features = pipeline.extract_features(candidate)
    semantic_match = float(
        pipeline.compute_cosine_similarity(features["embedding"], jd_vector)
    )
    skill_match = _candidate_jd_skill_match(candidate, jd_skill_terms)
    years = float(candidate.get("experience_years") or 0.0)

    final_score = float(
        engine.compute_hybrid_score(
            semantic_similarity=semantic_match,
            candidate=candidate,
            skill_match=skill_match,
            experience_years=years,
        )
    )

    if HeuristicFilter.is_honeypot(candidate):
        status = "HONEYPOT"
    elif HeuristicFilter.is_title_trap(candidate):
        status = "TITLE_TRAP"
    else:
        status = "CLEAN"

    candidate_for_explanation = dict(candidate)
    candidate_for_explanation["score"] = final_score
    reasoning = explainer.generate_reasoning(candidate_for_explanation, semantic_match)

    exp_score = min(years / 10.0, 1.0)
    edu_score = _education_score(candidate.get("education", []) or [])
    proj_score = _project_score(raw, candidate)
    candidate_skills = {
        str(s.get("name", "")).strip().lower()
        for s in candidate.get("skills", [])
        if isinstance(s, dict)
    }
    missing_skills = sorted(jd_skill_terms - candidate_skills)[:10]

    recommendation = _recommendation(final_score)
    ai_summary = (
        f"{candidate.get('name', 'This candidate')} was evaluated using the local "
        f"Sentence Transformer embedding pipeline. Semantic JD match is {semantic_match:.0%}, "
        f"skill match is {skill_match:.0%}, and the final hybrid fit score is {final_score:.0%}."
    )

    strengths = []
    if skill_match >= 0.5:
        strengths.append("Strong overlap with the active JD skills")
    if semantic_match >= 0.65:
        strengths.append("Strong semantic alignment with the role")
    if years >= 5:
        strengths.append(f"{years:.1f} years of professional experience")
    signals = raw.get("redrob_signals", {}) or {}
    if signals.get("open_to_work_flag"):
        strengths.append("Candidate is open to work")

    weaknesses = []
    if missing_skills:
        weaknesses.append("Missing: " + ", ".join(missing_skills[:5]))
    if semantic_match < 0.4:
        weaknesses.append("Low semantic alignment with the active JD")

    return {
        "overall_score": final_score,
        "skill_match": skill_match,
        "semantic_match": semantic_match,
        "experience_score": exp_score,
        "education_score": edu_score,
        "project_score": proj_score,
        "ai_summary": ai_summary,
        "recommendation": recommendation,
        "reasoning": reasoning,
        "strengths": strengths[:5],
        "weaknesses": weaknesses[:5],
        "missing_skills": missing_skills,
        "status": status,
        "rank_position": 0,
    }


def _jd_skill_terms(jd_text: str) -> set[str]:
    """Extract relevant multi-word/single-word skills actually present in the JD."""
    text = jd_text.lower()
    found = set()
    for skill in _RELEVANT_SKILLS:
        if skill in text:
            found.add(skill)
    return found


def _candidate_jd_skill_match(candidate: dict[str, Any], jd_skill_terms: set[str]) -> float:
    if not jd_skill_terms:
        return 0.0
    candidate_skills = {
        str(s.get("name", "")).strip().lower()
        for s in candidate.get("skills", [])
        if isinstance(s, dict)
    }
    matched = 0
    for required in jd_skill_terms:
        if required in candidate_skills or any(
            required in skill or skill in required for skill in candidate_skills
        ):
            matched += 1
    return matched / len(jd_skill_terms)


def _extract_requirements(jd_text: str) -> str:
    terms = sorted(_jd_skill_terms(jd_text))
    return ", ".join(terms[:30])


def _education_score(education: list[dict[str, Any]]) -> float:
    text = " ".join(str(row.get("degree", "")) for row in education).lower()
    if any(key in text for key in ["ph.d", "phd"]):
        return 1.0
    if any(key in text for key in ["m.tech", "m.s", "master"]):
        return 0.85
    if any(key in text for key in ["b.tech", "b.e", "bachelor"]):
        return 0.7
    return 0.5 if education else 0.3


def _project_score(raw: dict[str, Any], candidate: dict[str, Any]) -> float:
    text = " ".join(
        [
            str(candidate.get("profile", {}).get("summary", "")),
            " ".join(str(x.get("description", "")) for x in raw.get("career_history", []) or []),
        ]
    ).lower()
    if any(term in text for term in ["machine learning", "deep learning", "ml model", "llm", "rag"]):
        return 0.8
    if "data" in text or "analytics" in text:
        return 0.6
    return 0.3


def _recommendation(score: float) -> str:
    if score >= 0.75:
        return "Strong Fit"
    if score >= 0.55:
        return "Good Fit"
    if score >= 0.35:
        return "Possible Fit"
    return "Not a Fit"
