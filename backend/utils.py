"""
backend/utils.py — Explainable AI Template Reasoner & CSV Exporter
===================================================================
Provides two stateless utilities used during Phase 3 output generation:

``ExplanationEngine``
    Assembles human-readable, template-driven reasoning strings without
    hitting any external API — zero latency, fully deterministic.

``export_to_csv``
    Thin wrapper that writes a minimal ``candidate_id,rank,score,reasoning``
    submission file with exactly 4 decimal places on the score column.

Design philosophy
-----------------
* All strings are assembled from live candidate data — no canned phrases.
* The CSV schema matches the hackathon validator's minimum required columns;
  richer fields are handled by :func:`~backend.ranking.generate_submission_csv`.
* The module is dependency-free beyond the Python stdlib so it loads
  instantly even in restricted environments.
"""

from __future__ import annotations

import csv
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Core AI skills counted for the reasoning string.
# Mirrors the relevant set from embeddings.py.
# ---------------------------------------------------------------------------
_CORE_AI_SKILLS: frozenset[str] = frozenset({
    "python", "pytorch", "tensorflow", "scikit-learn", "nlp",
    "computer vision", "kubernetes", "docker", "sql", "spark",
    "fastapi", "mlflow", "langchain", "cuda", "transformers",
    "huggingface", "rag", "llm", "feature engineering", "data engineering",
    "machine learning", "deep learning", "mlops", "ray", "triton",
})

# Submission CSV schema — minimal 4-column format validated by the hackathon.
_SUBMISSION_COLUMNS: tuple[str, ...] = (
    "candidate_id",
    "rank",
    "score",
    "reasoning",
)


class ExplanationEngine:
    """Template-driven explainable AI reasoner.

    All methods are ``@staticmethod``; no instance state is required.
    Instantiate for namespace convenience or call via the class directly.
    """

    @staticmethod
    def generate_reasoning(candidate: dict[str, Any], semantic_score: float) -> str:
        """Dynamically assemble a 1-2 sentence reasoning string.

        The string incorporates:
        - Candidate's actual ``profile.current_title``.
        - Exact ``experience_years`` (1 decimal place).
        - Count of verified core AI skills (those with ``duration_months > 0``
          and a name matching the AI skill set).
        - Platform availability index derived from ``redrob_signals``.
        - Semantic alignment score vs the JD.

        Parameters
        ----------
        candidate:
            Fully or partially enriched candidate dict.
        semantic_score:
            Cosine similarity vs the job description embedding, ``[0.0, 1.0]``.

        Returns
        -------
        str
            A concise, factual sentence ready for the ``reasoning`` CSV column.
        """
        # ── Extract fields ────────────────────────────────────────────────
        profile: dict[str, Any] = candidate.get("profile", {}) or {}
        title: str = profile.get("current_title", "Unknown Title") or "Unknown Title"

        exp_years: float = float(candidate.get("experience_years", 0.0) or 0.0)

        skills: list[dict[str, Any]] = candidate.get("skills", []) or []
        verified_core: int = sum(
            1
            for s in skills
            if (s.get("name", "") or "").lower() in _CORE_AI_SKILLS
            and (s.get("duration_months", 0) or 0) > 0
        )

        # ── Availability index from Redrob signals ────────────────────────
        signals: dict[str, Any] = candidate.get("redrob_signals", {}) or {}
        rrr: float = float(signals.get("recruiter_response_rate", 0.75))
        icr: float = float(signals.get("interview_completion_rate", 0.80))
        availability_index: float = round((rrr * 0.6 + icr * 0.4), 2)

        # ── Qualifier words ───────────────────────────────────────────────
        semantic_label: str
        if semantic_score >= 0.80:
            semantic_label = "excellent"
        elif semantic_score >= 0.60:
            semantic_label = "strong"
        elif semantic_score >= 0.40:
            semantic_label = "moderate"
        else:
            semantic_label = "low"

        avail_label: str
        if availability_index >= 0.85:
            avail_label = "strong"
        elif availability_index >= 0.70:
            avail_label = "good"
        else:
            avail_label = "moderate"

        # ── Assemble sentence ─────────────────────────────────────────────
        reasoning: str = (
            f"{title} with {exp_years:.1f} years experience; "
            f"{verified_core} verified core AI skill{'s' if verified_core != 1 else ''}; "
            f"{avail_label} platform responsiveness index ({availability_index:.2f}); "
            f"{semantic_label} semantic alignment ({semantic_score:.3f}) with target role."
        )

        logger.debug(
            "generate_reasoning: id=%s verified_core=%d avail=%.2f semantic=%.3f",
            candidate.get("candidate_id", "?"),
            verified_core,
            availability_index,
            semantic_score,
        )
        return reasoning

    @staticmethod
    def export_to_csv(ranked_candidates: list[dict[str, Any]], output_path: str) -> None:
        """Write the top-100 submission file to *output_path*.

        Schema written: ``candidate_id, rank, score, reasoning``
        Score is formatted with **exactly 4 decimal places** (``%.4f``).

        Parameters
        ----------
        ranked_candidates:
            Output of :func:`~backend.ranking.sort_and_format_submission` —
            already sorted, ranked, and capped.
        output_path:
            Absolute or relative path for the output ``.csv`` file.
            Parent directories are created automatically.

        Raises
        ------
        OSError
            Re-raised if the file cannot be opened for writing.
        ValueError
            If *ranked_candidates* is empty.
        """
        if not ranked_candidates:
            raise ValueError("ranked_candidates is empty — nothing to export.")

        # ── Ensure parent directory exists ────────────────────────────────
        parent: str = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(parent, exist_ok=True)

        try:
            with open(output_path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh, lineterminator="\n")
                writer.writerow(_SUBMISSION_COLUMNS)

                for candidate in ranked_candidates:
                    cid: str = candidate.get("candidate_id", "")
                    rank: int = int(candidate.get("rank", 0))
                    raw_score: float = float(candidate.get("score", 0.0))
                    reasoning: str = candidate.get("reasoning", "")

                    # Format score to exactly 4 decimal places.
                    score_str: str = f"{raw_score:.4f}"

                    # Sanitise reasoning for CSV: replace internal newlines.
                    safe_reasoning: str = reasoning.replace("\n", " ").replace("\r", " ")

                    writer.writerow([cid, rank, score_str, safe_reasoning])

        except OSError:
            logger.exception("export_to_csv: failed to write to '%s'.", output_path)
            raise

        written: int = len(ranked_candidates)
        logger.info(
            "export_to_csv: wrote %d rows to '%s'.",
            written, output_path,
        )
