"""
backend/ranking.py - Vector ranking and submission formatting helpers.
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

_REQUIRED_SCORED_FIELDS: tuple[str, ...] = ("candidate_id", "score")
_TOP_N: int = 100

_CSV_COLUMNS: tuple[str, ...] = (
    "rank",
    "candidate_id",
    "name",
    "overall_score",
    "skill_match",
    "semantic_match",
    "experience_years",
    "top_skills",
    "status",
    "reason",
    "resume_summary",
    "github",
    "linkedin",
    "why_selected",
    "missing_skills",
    "best_alternate_roles",
)


class VectorRanker:
    """Rank embedding vectors with FAISS when available, else NumPy."""

    def __init__(self, embedding_dim: int = 384) -> None:
        self.embedding_dim: int = embedding_dim
        self.index: Optional[Any] = None
        self.n_indexed: int = 0
        self._candidate_matrix: Optional[np.ndarray] = None
        self._use_faiss: bool = False

    def build_index(self, candidate_embeddings: np.ndarray) -> None:
        try:
            import faiss  # noqa: PLC0415
        except ImportError:
            faiss = None

        if candidate_embeddings.ndim != 2:
            raise ValueError(
                f"candidate_embeddings must be 2-D (N, D), got shape {candidate_embeddings.shape}."
            )

        n, d = candidate_embeddings.shape
        if n == 0:
            raise ValueError("candidate_embeddings is empty - nothing to index.")
        if d != self.embedding_dim:
            logger.warning(
                "build_index: column count %d != embedding_dim %d; updating embedding_dim to %d.",
                d,
                self.embedding_dim,
                d,
            )
            self.embedding_dim = d

        vectors = np.ascontiguousarray(candidate_embeddings, dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0.0, 1.0, norms)
        vectors = vectors / norms

        self._candidate_matrix = vectors

        if faiss is not None:
            self._use_faiss = True
            self.index = faiss.IndexFlatIP(self.embedding_dim)
            self.index.add(vectors)  # type: ignore[union-attr]
            self.n_indexed = self.index.ntotal
        else:
            self._use_faiss = False
            self.index = None
            self.n_indexed = vectors.shape[0]
            logger.warning(
                "VectorRanker: faiss not available; using NumPy fallback for ranking."
            )

        logger.info(
            "VectorRanker: index built - %d vectors, dim=%d.",
            self.n_indexed,
            self.embedding_dim,
        )

    def query_top_k(
        self,
        jd_embedding: np.ndarray,
        k: int = 500,
    ) -> Tuple[np.ndarray, np.ndarray]:
        if self.n_indexed == 0 or self._candidate_matrix is None:
            raise RuntimeError(
                "VectorRanker.build_index() must be called before query_top_k()."
            )

        query = np.ascontiguousarray(jd_embedding, dtype=np.float32).reshape(1, -1)
        query_norm = np.linalg.norm(query, axis=1, keepdims=True)
        query_norm = np.where(query_norm == 0.0, 1.0, query_norm)
        query = query / query_norm

        effective_k = min(k, self.n_indexed)

        if self._use_faiss and self.index is not None:
            scores_2d, indices_2d = self.index.search(query, effective_k)
            indices = indices_2d[0]
            scores = scores_2d[0]
        else:
            scores_all = np.dot(self._candidate_matrix, query[0])
            order = np.argsort(-scores_all, kind="stable")[:effective_k]
            indices = order.astype(np.int64, copy=False)
            scores = scores_all[order].astype(np.float32, copy=False)

        scores = np.clip(scores, 0.0, 1.0)

        logger.debug(
            "VectorRanker.query_top_k: k=%d, top_score=%.4f, bottom_score=%.4f",
            effective_k,
            float(scores[0]) if len(scores) > 0 else 0.0,
            float(scores[-1]) if len(scores) > 0 else 0.0,
        )
        return indices, scores


def sort_and_format_submission(
    scored_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not scored_candidates:
        return []

    for entry in scored_candidates:
        for field in _REQUIRED_SCORED_FIELDS:
            if field not in entry:
                raise ValueError(
                    f"Scored candidate is missing required field '{field}': {entry!r}"
                )

    sorted_candidates = sorted(
        scored_candidates,
        key=lambda c: (-c["score"], c["candidate_id"]),
    )

    top_n = sorted_candidates[:_TOP_N]
    for rank, candidate in enumerate(top_n, start=1):
        candidate["rank"] = rank

    return top_n


def format_candidate_for_api(
    candidate: dict[str, Any],
) -> dict[str, Any]:
    profile: dict[str, Any] = candidate.get("profile", {}) or {}
    analysis: dict[str, Any] = candidate.get("analysis", {}) or {}

    raw_skills: list[dict[str, Any]] = candidate.get("skills", []) or []
    sorted_skills = sorted(
        raw_skills,
        key=lambda s: s.get("duration_months", 0),
        reverse=True,
    )
    top_skills: list[str] = [s.get("name", "") for s in sorted_skills[:5]]
    certifications: list[Any] = candidate.get("certifications", []) or []

    return {
        "rank": candidate.get("rank"),
        "candidate_id": candidate.get("candidate_id", ""),
        "name": candidate.get("name", ""),
        "overall_score": round(candidate.get("score", 0.0), 4),
        "skill_match": candidate.get("skill_match", 0.0),
        "semantic_match": candidate.get("semantic_match", 0.0),
        "experience_years": candidate.get("experience_years", 0.0),
        "top_skills": top_skills,
        "status": candidate.get("status", "UNKNOWN"),
        "reason": candidate.get("reasoning", ""),
        "resume_summary": profile.get("summary", ""),
        "skills": raw_skills,
        "experience": candidate.get("experience", []),
        "education": candidate.get("education", []),
        "projects": candidate.get("projects", []),
        "certifications": certifications,
        "github": profile.get("github", ""),
        "linkedin": profile.get("linkedin", ""),
        "why_selected": analysis.get("why_selected", ""),
        "missing_skills": analysis.get("missing_skills", []),
        "best_alternate_roles": analysis.get("best_alternate_roles", []),
    }


def generate_submission_csv(
    ranked_candidates: list[dict[str, Any]],
) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=list(_CSV_COLUMNS),
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()

    for candidate in ranked_candidates:
        api_row = format_candidate_for_api(candidate)
        api_row["top_skills"] = " | ".join(api_row.get("top_skills", []))
        api_row["missing_skills"] = " | ".join(
            str(s) for s in api_row.get("missing_skills", [])
        )
        api_row["best_alternate_roles"] = " | ".join(
            str(r) for r in api_row.get("best_alternate_roles", [])
        )
        writer.writerow(api_row)

    return output.getvalue()
