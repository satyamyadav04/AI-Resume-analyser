"""
backend/services/upload_service.py — Resume Upload & Analysis Pipeline
=======================================================================
Orchestrates the full resume processing pipeline:
  1. Save file to storage/
  2. Extract text (UniversalParser)
  3. Structure candidate data
  4. Generate embeddings against active JD
  5. Score with ScoringEngine
  6. Generate AI reasoning (ExplanationEngine)
  7. Persist candidate + analysis to DB
  8. Update timeline
  9. Update JD resume count

Reuses all existing backend modules unchanged.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np

from backend.database.db import get_project_root
from backend.repositories import candidate_repo, jd_repo, analysis_repo
from backend.services import jd_service
from backend.document_parser import UniversalParser
from backend.embeddings import EmbeddingPipeline, _RELEVANT_SKILLS
from backend.scoring import ScoringEngine, HeuristicFilter
from backend.utils import ExplanationEngine

logger = logging.getLogger(__name__)

# Lazy-loaded singletons (heavy models loaded once per process)
_embedding_pipeline: Optional[EmbeddingPipeline] = None
_scoring_engine: Optional[ScoringEngine] = None
_explainer: Optional[ExplanationEngine] = None


def _get_pipeline() -> EmbeddingPipeline:
    global _embedding_pipeline
    if _embedding_pipeline is None:
        _embedding_pipeline = EmbeddingPipeline()
    return _embedding_pipeline


def _get_engine() -> ScoringEngine:
    global _scoring_engine
    if _scoring_engine is None:
        _scoring_engine = ScoringEngine(embedding_pipeline=_get_pipeline())
    return _scoring_engine


def _get_explainer() -> ExplanationEngine:
    global _explainer
    if _explainer is None:
        _explainer = ExplanationEngine()
    return _explainer


def process_resume(
    file_bytes: bytes,
    filename: str,
    company_id: int,
    jd_id: int,
    user_id: int,
    jd_text: str = "",
) -> dict[str, Any]:
    """Process a single resume end-to-end. Returns a result dict.

    Returns a dict with keys:
        success: bool
        candidate_id: int (DB id) — on success
        name: str
        score: float
        recommendation: str
        error: str — on failure
    """
    result = {
        "success": False,
        "filename": filename,
        "candidate_id": None,
        "name": "Unknown",
        "score": 0.0,
        "recommendation": "",
        "error": "",
    }

    try:
        active_jd = jd_service.get_upload_target_jd(company_id, jd_id)
        active_jd_id = int(active_jd["id"])
        effective_jd_text = jd_text.strip() or jd_service.get_active_jd_text(company_id)

        # ── 1. Compute file hash for duplicate detection ──────────────────
        file_hash = hashlib.md5(file_bytes).hexdigest()

        if candidate_repo.candidate_exists_by_hash(company_id, active_jd_id, file_hash):
            result["error"] = f"Duplicate resume — '{filename}' was already uploaded."
            return result

        # ── 2. Save file to storage/ ──────────────────────────────────────
        storage_dir = get_project_root() / "storage" / "resumes" / str(company_id) / str(active_jd_id)
        storage_dir.mkdir(parents=True, exist_ok=True)
        safe_name = _safe_filename(filename)
        file_path = storage_dir / safe_name
        file_path.write_bytes(file_bytes)

        # ── 3. Save upload record ─────────────────────────────────────────
        upload_id = candidate_repo.save_upload_record(
            company_id=company_id,
            jd_id=active_jd_id,
            uploaded_by=user_id,
            filename=filename,
            file_path=str(file_path),
            file_size=len(file_bytes),
            file_hash=file_hash,
            status="processing",
        )

        # ── 4. Extract text ───────────────────────────────────────────────
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
        raw_text = UniversalParser.extract_text(file_bytes, ext)
        if not raw_text.strip():
            raise ValueError("No text could be extracted from this resume.")

        # ── 5. Structure candidate data ───────────────────────────────────
        candidate_dict = UniversalParser.structure_candidate_data(raw_text)

        # ── 6. Generate JD-specific embedding ────────────────────────────
        pipeline = _get_pipeline()
        engine = _get_engine()
        explainer = _get_explainer()

        # Build JD vector from active JD text (not hardcoded target role)
        if effective_jd_text:
            jd_vector = pipeline._embed(effective_jd_text)
        else:
            jd_vector = pipeline.jd_vector

        features = pipeline.extract_features(candidate_dict)
        # Override cosine similarity with JD-specific vector
        candidate_embedding = features["embedding"]
        semantic_sim = float(pipeline.compute_cosine_similarity(candidate_embedding, jd_vector))
        features["cosine_similarity"] = semantic_sim

        # ── 7. Compute hybrid score ───────────────────────────────────────
        final_score = engine.compute_hybrid_score(
            semantic_similarity=semantic_sim,
            candidate=candidate_dict,
            skill_match=float(features.get("skill_match", 0.0)),
            experience_years=float(features.get("experience_years", 0.0)),
        )

        # ── 8. Determine status ───────────────────────────────────────────
        if HeuristicFilter.is_honeypot(candidate_dict):
            status = "HONEYPOT"
        elif HeuristicFilter.is_title_trap(candidate_dict):
            status = "TITLE_TRAP"
        else:
            status = "CLEAN"

        # ── 9. Generate AI reasoning ──────────────────────────────────────
        candidate_dict["score"] = final_score
        reasoning = explainer.generate_reasoning(candidate_dict, semantic_sim)

        # ── 10. Build score breakdown ─────────────────────────────────────
        exp_score = min(float(features.get("experience_years", 0.0)) / 10.0, 1.0)
        edu_score = _compute_education_score(candidate_dict)
        proj_score = _compute_project_score(candidate_dict)

        # Missing skills
        candidate_skills_lower = frozenset(
            (s.get("name", "") or "").lower()
            for s in (candidate_dict.get("skills", []) or [])
        )
        missing_skills = sorted(s for s in _RELEVANT_SKILLS if s not in candidate_skills_lower)[:10]

        # Strengths and weaknesses
        strengths, weaknesses = _compute_strengths_weaknesses(features, status)

        # Recommendation
        score_pct = final_score * 100
        if score_pct >= 75:
            recommendation = "Strong Fit"
        elif score_pct >= 55:
            recommendation = "Good Fit"
        elif score_pct >= 35:
            recommendation = "Possible Fit"
        else:
            recommendation = "Not a Fit"

        # AI Summary
        ai_summary = _build_ai_summary(candidate_dict, features, semantic_sim, final_score, status)

        # ── 11. Save candidate to DB ──────────────────────────────────────
        candidate_db_id = candidate_repo.save_candidate(
            company_id=company_id,
            jd_id=active_jd_id,
            upload_id=upload_id,
            candidate_dict=candidate_dict,
        )

        # ── 12. Save analysis ─────────────────────────────────────────────
        analysis_repo.save_analysis(
            candidate_db_id=candidate_db_id,
            jd_id=active_jd_id,
            scores={
                "overall_score": final_score,
                "skill_match": float(features.get("skill_match", 0.0)),
                "semantic_match": semantic_sim,
                "experience_score": exp_score,
                "education_score": edu_score,
                "project_score": proj_score,
                "ai_summary": ai_summary,
                "recommendation": recommendation,
                "reasoning": reasoning,
                "strengths": strengths,
                "weaknesses": weaknesses,
                "missing_skills": missing_skills,
                "status": status,
                "rank_position": 0,
            },
        )

        # ── 13. Update upload status & JD count ──────────────────────────
        candidate_repo.update_upload_status(upload_id, "completed")
        jd_repo.increment_resume_count(active_jd_id)

        # ── 14. Add timeline event ────────────────────────────────────────
        candidate_repo.add_timeline_event(
            candidate_db_id,
            "Resume Uploaded",
            f"Resume '{filename}' uploaded and parsed.",
            user_id,
        )
        candidate_repo.add_timeline_event(
            candidate_db_id,
            "AI Analysis Completed",
            f"Overall match: {score_pct:.1f}% | Recommendation: {recommendation}",
            user_id,
        )

        result.update({
            "success": True,
            "candidate_id": candidate_db_id,
            "name": candidate_dict.get("name", "Unknown"),
            "score": final_score,
            "recommendation": recommendation,
            "jd_id": active_jd_id,
            "active_jd_title": active_jd.get("title", ""),
        })
        logger.info("Processed resume '%s' → score=%.4f", filename, final_score)

    except Exception as exc:
        logger.exception("Failed to process resume '%s': %s", filename, exc)
        result["error"] = str(exc)
        if "upload_id" in locals():
            candidate_repo.update_upload_status(
                upload_id, "failed", error_message=str(exc)
            )

    return result


def delete_uploaded_resume(upload_id: int, company_id: int) -> dict[str, Any]:
    """Delete a recent upload and its stored resume file."""
    file_path = candidate_repo.delete_upload_record(upload_id=upload_id, company_id=company_id)
    if not file_path:
        raise ValueError("Upload not found.")

    try:
        Path(file_path).unlink(missing_ok=True)
    except Exception as exc:
        logger.warning("Failed to remove resume file '%s': %s", file_path, exc)

    return {"upload_id": upload_id, "file_path": file_path}


def process_bulk(
    files: list[tuple[str, bytes]],
    company_id: int,
    jd_id: int,
    user_id: int,
    jd_text: str = "",
    progress_callback: Optional[Callable[[int, int, str, dict], None]] = None,
) -> list[dict[str, Any]]:
    """Process multiple resumes sequentially with progress callback.

    Args:
        files: list of (filename, file_bytes) tuples
        progress_callback: called as callback(current_idx, total, filename, result)
    """
    results = []
    total = len(files)

    for i, (filename, file_bytes) in enumerate(files):
        if progress_callback:
            progress_callback(i, total, filename, {})

        result = process_resume(
            file_bytes=file_bytes,
            filename=filename,
            company_id=company_id,
            jd_id=jd_id,
            user_id=user_id,
            jd_text=jd_text,
        )
        results.append(result)

        if progress_callback:
            progress_callback(i + 1, total, filename, result)

    return results


def expand_zip(zip_bytes: bytes) -> list[tuple[str, bytes]]:
    """Expand a ZIP file into (filename, bytes) pairs for supported types."""
    files = []
    try:
        with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
                if ext in ("pdf", "docx", "txt") and not name.startswith("__"):
                    with zf.open(name) as f:
                        files.append((os.path.basename(name), f.read()))
    except zipfile.BadZipFile as exc:
        logger.error("Bad ZIP file: %s", exc)
    return files


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _safe_filename(filename: str) -> str:
    """Sanitize a filename for safe storage."""
    name = os.path.basename(filename)
    name = re.sub(r"[^\w\s\-\.]", "_", name)
    return name[:200]


def _compute_education_score(candidate_dict: dict) -> float:
    education = candidate_dict.get("education", []) or []
    if not education:
        return 0.3
    edu_str = " ".join(str(e) for e in education).lower()
    if any(k in edu_str for k in ["ph.d", "phd", "doctorate"]):
        return 1.0
    if any(k in edu_str for k in ["master", "m.tech", "m.s", "mtech"]):
        return 0.85
    if any(k in edu_str for k in ["bachelor", "b.tech", "btech", "b.e"]):
        return 0.70
    return 0.5


def _compute_project_score(candidate_dict: dict) -> float:
    projects = candidate_dict.get("projects", []) or []
    if not projects:
        return 0.2
    return min(len(projects) * 0.2, 1.0)


def _compute_strengths_weaknesses(features: dict, status: str) -> tuple[list[str], list[str]]:
    strengths = []
    weaknesses = []

    skill_match = features.get("skill_match", 0.0)
    cosine = features.get("cosine_similarity", 0.0)
    exp_yrs = features.get("experience_years", 0.0)

    if skill_match >= 0.5:
        strengths.append("Strong technical skill alignment")
    elif skill_match < 0.2:
        weaknesses.append("Limited relevant technical skills")

    if cosine >= 0.7:
        strengths.append("Excellent semantic match with job description")
    elif cosine < 0.4:
        weaknesses.append("Low semantic alignment with the role")

    if exp_yrs >= 5:
        strengths.append(f"Substantial experience ({exp_yrs:.1f} years)")
    elif exp_yrs < 2:
        weaknesses.append("Limited professional experience")
    else:
        strengths.append(f"Adequate experience ({exp_yrs:.1f} years)")

    if status == "HONEYPOT":
        weaknesses.append("Inconsistent skill proficiency claims detected")
    elif status == "TITLE_TRAP":
        weaknesses.append("Non-technical background — poor role fit")

    return strengths, weaknesses


def _build_ai_summary(candidate_dict: dict, features: dict, semantic_sim: float, score: float, status: str) -> str:
    profile = candidate_dict.get("profile", {}) or {}
    name = candidate_dict.get("name", "This candidate")
    title = profile.get("current_title", "professional")
    exp_yrs = features.get("experience_years", 0.0)
    skill_match = features.get("skill_match", 0.0)
    top_skills = features.get("top_skills", [])

    skills_str = ", ".join(top_skills[:4]) if top_skills else "general IT skills"

    if status == "HONEYPOT":
        return (f"{name} was flagged for inconsistent skill proficiency claims. "
                "Recommending disqualification pending further review.")
    if status == "TITLE_TRAP":
        return (f"{name} holds a non-technical {title} background. "
                f"Semantic alignment is low ({semantic_sim:.0%}). "
                "This candidate is unlikely to fit a technical engineering role.")

    return (
        f"{name} is a {title} with {exp_yrs:.1f} years of professional experience. "
        f"Key skills include {skills_str}. "
        f"Technical skill overlap with the job description is {skill_match:.0%}, "
        f"with {semantic_sim:.0%} overall semantic alignment. "
        f"Final AI match score: {score * 100:.1f}%."
    )
