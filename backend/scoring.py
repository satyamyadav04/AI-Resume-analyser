"""
backend/scoring.py — Hybrid Scoring Matrix Engine
==================================================
Combines Phase-1 trap heuristics with semantic signals and 23 Redrob
behavioural signals to produce a deterministic, auditable final score for
every candidate.

Scoring formula
---------------
::

    availability_modifier = f(recruiter_response_rate,
                               last_active_recency,
                               interview_completion_rate)

    base_score = (semantic_similarity * W_SEMANTIC
                  + skill_match       * W_SKILL
                  + experience_score  * W_EXPERIENCE)

    trap_multiplier = get_base_penalty(candidate)     # 0.0 / 0.1 / 1.0

    final_score = base_score * trap_multiplier * availability_modifier

Special cases
-------------
* Honeypot candidates always receive ``final_score = 0.0`` (hard override).
* Title-trap candidates receive ``base_score * 0.15`` (strict per-spec factor).

Classes
-------
HeuristicFilter
    Phase-1 static heuristics (preserved unchanged from Phase 1).
ScoringEngine
    Stateful engine that owns the EmbeddingPipeline and executes the full
    hybrid scoring matrix.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scoring weight constants
# ---------------------------------------------------------------------------

W_SEMANTIC: float = 0.45     # cosine similarity vs JD embedding
W_SKILL: float = 0.35        # Jaccard skill-match against relevant skill set
W_EXPERIENCE: float = 0.20   # years of experience (capped at 10 yrs → 1.0)

_EXPERIENCE_CAP_YEARS: float = 10.0

# Title-trap strict penalty factor (overrides the Phase-1 0.1 multiplier for
# the hybrid engine per the Phase-2 spec: "reduce score by factor of 0.15").
_TITLE_TRAP_FACTOR: float = 0.15

# Availability modifier bounds: never let it drop below this floor.
_AVAILABILITY_FLOOR: float = 0.60

# Reference date for recency calculations (June 2026 as specified).
_REFERENCE_DATE: date = date(2026, 6, 1)


# ===========================================================================
# Phase-1 HeuristicFilter — preserved verbatim
# ===========================================================================


class HeuristicFilter:
    """Static heuristics for flagging low-quality or dishonest candidates.

    All methods operate on the raw candidate ``dict`` as produced by
    :class:`~backend.parser.CandidateParser` and never mutate the input.
    """

    # Non-technical keyword fragments (lower-cased for case-insensitive match).
    # A title is flagged if ANY of these substrings is found within it.
    _TRAP_KEYWORDS: frozenset[str] = frozenset({
        "marketing",
        "hr manager",
        "human resource",
        "operations manager",
        "accountant",
        "accounting",
        "sales",
        "recruiter",
        "customer service",
        "logistics",
        "business development",
        "procurement",
        "supply chain",
        "payroll",
        "administrative",
        "office manager",
        "receptionist",
        "event coordinator",
    })

    # Proficiency levels that are considered implausibly high for 0 months.
    _HIGH_PROFICIENCY: frozenset[str] = frozenset({"expert", "advanced"})

    @staticmethod
    def is_title_trap(candidate: dict[str, Any]) -> bool:
        """Return ``True`` if the candidate's current title is non-technical.

        Detection is case-insensitive substring matching against a curated
        blocklist of non-technical role keywords.

        Parameters
        ----------
        candidate:
            Raw candidate dict.  Expected key path: ``profile.current_title``.

        Returns
        -------
        bool
            ``True``  → title contains a non-technical keyword.
            ``False`` → title is absent, empty, or passes all checks.
        """
        profile: dict[str, Any] = candidate.get("profile", {})
        title: str = profile.get("current_title", "") or ""
        if not title:
            return False

        title_lower = title.lower()
        return any(keyword in title_lower for keyword in HeuristicFilter._TRAP_KEYWORDS)

    @staticmethod
    def is_honeypot(candidate: dict[str, Any]) -> bool:
        """Return ``True`` if the candidate contains an impossible skill claim.

        A skill is a honeypot when:
        - ``proficiency`` is ``"expert"`` or ``"advanced"``  **AND**
        - ``duration_months`` is ``0``.

        Parameters
        ----------
        candidate:
            Raw candidate dict.  Expected key: ``skills`` → list of skill dicts.

        Returns
        -------
        bool
            ``True``  → at least one honeypot skill detected.
            ``False`` → skills list is absent, empty, or all claims are plausible.
        """
        skills: list[dict[str, Any]] = candidate.get("skills", []) or []
        for skill in skills:
            proficiency: str = (skill.get("proficiency", "") or "").lower()
            duration: int = skill.get("duration_months", -1)
            if (
                proficiency in HeuristicFilter._HIGH_PROFICIENCY
                and duration == 0
            ):
                return True
        return False

    @staticmethod
    def get_base_penalty(candidate: dict[str, Any]) -> float:
        """Return the penalty multiplier to apply to this candidate's score.

        Priority (highest penalty wins):
        1. Honeypot → ``0.0`` (disqualified; score reduced to zero).
        2. Title trap → ``0.1`` (heavily penalised; likely irrelevant).
        3. Clean candidate → ``1.0`` (no penalty).

        Parameters
        ----------
        candidate:
            Raw candidate dict.

        Returns
        -------
        float
            One of ``{0.0, 0.1, 1.0}``.
        """
        if HeuristicFilter.is_honeypot(candidate):
            return 0.0
        if HeuristicFilter.is_title_trap(candidate):
            return 0.1
        return 1.0


# ===========================================================================
# Phase-2 ScoringEngine
# ===========================================================================


class ScoringEngine:
    """Hybrid scoring matrix engine for RecruitAI Phase 2.

    The engine orchestrates:
    1. Semantic feature extraction (via :class:`~backend.embeddings.EmbeddingPipeline`).
    2. Trap filtering (via :class:`HeuristicFilter`).
    3. Availability modifier computation from Redrob behavioural signals.
    4. Final score assembly with deterministic rules for traps.

    Parameters
    ----------
    embedding_pipeline:
        An already-initialised :class:`~backend.embeddings.EmbeddingPipeline`.
        Pass ``None`` to lazy-import and instantiate on first use.
    """

    def __init__(self, embedding_pipeline: Optional[Any] = None) -> None:
        self._pipeline = embedding_pipeline
        if self._pipeline is None:
            self._pipeline = self._load_pipeline()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        """Score a single candidate and return the enriched dict.

        Parameters
        ----------
        candidate:
            Raw candidate dict from the parser.

        Returns
        -------
        dict[str, Any]
            Original dict **extended** with:
            ``score``, ``skill_match``, ``semantic_match``,
            ``status``, ``reasoning``, ``analysis``.
        """
        cid: str = candidate.get("candidate_id", "?")
        logger.debug("Scoring candidate %s", cid)

        # ── Extract semantic features ─────────────────────────────────────
        features: dict[str, Any] = self._pipeline.extract_features(candidate)
        semantic_similarity: float = features["cosine_similarity"]
        skill_match: float = features["skill_match"]
        experience_years: float = features["experience_years"]

        # ── Compute final hybrid score ────────────────────────────────────
        final_score: float = self.compute_hybrid_score(
            semantic_similarity=semantic_similarity,
            candidate=candidate,
            skill_match=skill_match,
            experience_years=experience_years,
        )

        # ── Determine status label ────────────────────────────────────────
        if HeuristicFilter.is_honeypot(candidate):
            status = "HONEYPOT"
        elif HeuristicFilter.is_title_trap(candidate):
            status = "TITLE_TRAP"
        else:
            status = "CLEAN"

        # ── Build reasoning string ────────────────────────────────────────
        reasoning: str = self._build_reasoning(
            status=status,
            semantic_similarity=semantic_similarity,
            skill_match=skill_match,
            experience_years=experience_years,
            final_score=final_score,
        )

        # ── Build analysis block ──────────────────────────────────────────
        analysis: dict[str, Any] = self._build_analysis(
            candidate=candidate,
            features=features,
            status=status,
        )

        candidate.update({
            "score": final_score,
            "skill_match": round(skill_match, 4),
            "semantic_match": round(semantic_similarity, 4),
            "status": status,
            "reasoning": reasoning,
            "analysis": analysis,
        })

        logger.info(
            "Scored %s: score=%.4f status=%s semantic=%.4f skill=%.4f",
            cid, final_score, status, semantic_similarity, skill_match,
        )
        return candidate

    def compute_hybrid_score(
        self,
        semantic_similarity: float,
        candidate: dict[str, Any],
        skill_match: float = 0.0,
        experience_years: float = 0.0,
    ) -> float:
        """Compute the final hybrid score for a candidate.

        Formula
        -------
        ::

            experience_score = min(experience_years / EXPERIENCE_CAP, 1.0)

            base_score = (semantic_similarity * W_SEMANTIC
                          + skill_match       * W_SKILL
                          + experience_score  * W_EXPERIENCE)

            availability = _compute_availability_modifier(candidate)

            if is_honeypot:
                return 0.0
            elif is_title_trap:
                return base_score * TITLE_TRAP_FACTOR * availability
            else:
                return base_score * availability

        Parameters
        ----------
        semantic_similarity:
            Cosine similarity between candidate text and JD embedding.
            Range ``[0.0, 1.0]``.
        candidate:
            Raw candidate dict (used for trap checks and Redrob signals).
        skill_match:
            Jaccard skill overlap.  Range ``[0.0, 1.0]``.
        experience_years:
            Total years of professional experience.

        Returns
        -------
        float
            Final score in ``[0.0, 1.0]`` (hard-clipped).
        """
        # ── Hard override: honeypot ───────────────────────────────────────
        if HeuristicFilter.is_honeypot(candidate):
            logger.debug(
                "compute_hybrid_score: honeypot detected for %s → 0.0",
                candidate.get("candidate_id", "?"),
            )
            return 0.0

        # ── Weighted base score ───────────────────────────────────────────
        experience_score: float = min(experience_years / _EXPERIENCE_CAP_YEARS, 1.0)
        base_score: float = (
            semantic_similarity * W_SEMANTIC
            + skill_match       * W_SKILL
            + experience_score  * W_EXPERIENCE
        )

        # ── Availability modifier from Redrob behavioural signals ─────────
        availability: float = self._compute_availability_modifier(candidate)

        # ── Apply trap penalty ────────────────────────────────────────────
        if HeuristicFilter.is_title_trap(candidate):
            logger.debug(
                "compute_hybrid_score: title trap for %s → ×%.2f",
                candidate.get("candidate_id", "?"), _TITLE_TRAP_FACTOR,
            )
            raw: float = base_score * _TITLE_TRAP_FACTOR * availability
        else:
            raw = base_score * availability

        # ── Hard clip to [0, 1] ───────────────────────────────────────────
        return float(max(0.0, min(1.0, raw)))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_availability_modifier(candidate: dict[str, Any]) -> float:
        """Compute a [AVAILABILITY_FLOOR, 1.0] availability modifier.

        Uses three Redrob behavioural signals:

        1. ``recruiter_response_rate`` (0.0–1.0)
           → direct weight (how often the candidate responds to outreach).

        2. ``last_active_date`` recency vs June 2026
           → recent activity boosts score; 6+ months idle reduces it.

        3. ``interview_completion_rate`` (0.0–1.0)
           → penalises candidates who accept interviews but ghost them.

        Parameters
        ----------
        candidate:
            Raw or enriched candidate dict.  All Redrob signals are optional;
            missing signals default to neutral values.

        Returns
        -------
        float
            Modifier in ``[_AVAILABILITY_FLOOR, 1.0]``.
        """
        signals: dict[str, Any] = candidate.get("redrob_signals", {}) or {}

        # ── Signal 1: recruiter response rate ────────────────────────────
        rrr: float = float(signals.get("recruiter_response_rate", 0.75))
        rrr = max(0.0, min(1.0, rrr))

        # ── Signal 2: last active recency ─────────────────────────────────
        last_active_raw: str = signals.get("last_active_date", "") or ""
        recency_score: float = 0.75  # neutral default
        if last_active_raw:
            try:
                last_active: date = datetime.strptime(
                    last_active_raw[:10], "%Y-%m-%d"
                ).date()
                days_idle: int = (_REFERENCE_DATE - last_active).days
                if days_idle <= 0:
                    recency_score = 1.0         # active today / future
                elif days_idle <= 30:
                    recency_score = 0.95
                elif days_idle <= 90:
                    recency_score = 0.85
                elif days_idle <= 180:
                    recency_score = 0.70
                else:
                    recency_score = 0.50        # 6+ months idle
            except ValueError:
                logger.warning(
                    "_compute_availability_modifier: unparseable last_active_date=%r",
                    last_active_raw,
                )

        # ── Signal 3: interview completion rate ───────────────────────────
        icr: float = float(signals.get("interview_completion_rate", 0.80))
        icr = max(0.0, min(1.0, icr))

        # ── Weighted composite (hand-tuned from Redrob 23-signal corpus) ─
        modifier: float = (rrr * 0.40) + (recency_score * 0.35) + (icr * 0.25)

        # Floor and ceiling
        return float(max(_AVAILABILITY_FLOOR, min(1.0, modifier)))

    @staticmethod
    def _build_reasoning(
        *,
        status: str,
        semantic_similarity: float,
        skill_match: float,
        experience_years: float,
        final_score: float,
    ) -> str:
        """Return a one-line human-readable scoring rationale."""
        if status == "HONEYPOT":
            return (
                "Disqualified: candidate claims expert/advanced proficiency "
                "with 0 months of experience (honeypot pattern)."
            )
        if status == "TITLE_TRAP":
            return (
                f"Heavily penalised: non-technical title detected "
                f"(title-trap factor ×{_TITLE_TRAP_FACTOR}). "
                f"Semantic={semantic_similarity:.3f}, "
                f"SkillMatch={skill_match:.3f}, "
                f"FinalScore={final_score:.4f}."
            )
        return (
            f"CLEAN: Semantic={semantic_similarity:.3f}, "
            f"SkillMatch={skill_match:.3f}, "
            f"Experience={experience_years:.1f}yr, "
            f"FinalScore={final_score:.4f}."
        )

    @staticmethod
    def _build_analysis(
        *,
        candidate: dict[str, Any],
        features: dict[str, Any],
        status: str,
    ) -> dict[str, Any]:
        """Build the ``analysis`` sub-dict for the API response."""
        from backend.embeddings import _RELEVANT_SKILLS  # local import to avoid cycle

        candidate_skills_lower: frozenset[str] = frozenset(
            (s.get("name", "") or "").lower()
            for s in (candidate.get("skills", []) or [])
        )
        missing: list[str] = sorted(
            s for s in _RELEVANT_SKILLS if s not in candidate_skills_lower
        )[:8]  # cap at 8 for readability

        alternate_roles: list[str] = []
        if status == "TITLE_TRAP":
            alternate_roles = [
                "Data Analyst",
                "AI Product Manager",
                "Technical Recruiter (AI Focus)",
            ]
        elif features.get("experience_years", 0) < 2:
            alternate_roles = ["Junior ML Engineer", "AI Research Intern"]
        else:
            alternate_roles = ["Senior ML Engineer", "MLOps Engineer", "AI Lead"]

        why_selected: str = (
            "Disqualified — see reasoning."
            if status in {"HONEYPOT", "TITLE_TRAP"}
            else (
                f"Strong alignment with Senior AI Engineer role: "
                f"semantic similarity {features.get('cosine_similarity', 0):.2%}, "
                f"skill overlap {features.get('skill_match', 0):.2%}."
            )
        )

        return {
            "why_selected": why_selected,
            "missing_skills": missing,
            "best_alternate_roles": alternate_roles,
        }

    @staticmethod
    def _load_pipeline() -> Any:
        """Lazy-import and instantiate the EmbeddingPipeline."""
        from backend.embeddings import EmbeddingPipeline  # noqa: PLC0415
        return EmbeddingPipeline()
