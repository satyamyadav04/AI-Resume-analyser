"""
tests/test_analyzer_pipeline.py — Automated Phase-2 Integration & Unit Tests
==============================================================================
Covers every Phase-2 requirement with zero manual intervention needed.

Test groups
-----------
TestEmbeddingPipeline
    Unit tests for ``EmbeddingPipeline``:
    - Feature extraction produces required keys.
    - Cosine similarity handles zero-vectors, NaN, shape mismatch.
    - Honeypot skills are excluded from the text block.

TestComputeHybridScore
    Unit tests for ``ScoringEngine.compute_hybrid_score``:
    - Clean candidate produces a score in (0, 1].
    - Honeypot hard-overrides score to exactly 0.0.
    - Title-trap applies the strict 0.15 penalty factor.
    - Availability modifier is bounded in [0.60, 1.0].

TestTrapMitigation
    Integration test (Req 1): keyword-stuffing Marketing Manager candidate
    is detected as TITLE_TRAP and receives the penalty.

TestHoneypotElimination
    Integration test (Req 2): candidate with expert skill + 0 months receives
    a final score of exactly 0.0.

TestDeterministicSorting
    Integration test (Req 3): 5-candidate list with a 3-way score tie is
    sorted primary-score-desc / secondary-id-asc by
    ``sort_and_format_submission``, matching the validator contract.

TestAvailabilityModifier
    Unit tests for ``_compute_availability_modifier``:
    - Recent activity boosts score, old activity reduces it.
    - Missing signals fall back to neutral defaults.
    - Modifier is always ≥ _AVAILABILITY_FLOOR.

TestScoringEngineIntegration
    End-to-end: ``score_candidate`` returns all required enrichment keys.

Run with:
    python -m pytest tests/test_analyzer_pipeline.py -v
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Helpers & fixtures
# ---------------------------------------------------------------------------


def _make_candidate(
    candidate_id: str = "CAND_001",
    title: str = "Senior AI Engineer",
    skills: list[dict] | None = None,
    experience_years: float = 5.0,
    summary: str = "Experienced AI engineer with deep learning and NLP expertise.",
    redrob_signals: dict | None = None,
) -> dict[str, Any]:
    """Factory for a minimal well-formed candidate dict."""
    if skills is None:
        skills = [
            {"name": "Python", "proficiency": "expert", "duration_months": 48},
            {"name": "PyTorch", "proficiency": "advanced", "duration_months": 36},
            {"name": "NLP", "proficiency": "intermediate", "duration_months": 24},
        ]
    return {
        "candidate_id": candidate_id,
        "name": f"Test Candidate {candidate_id}",
        "experience_years": experience_years,
        "profile": {
            "current_title": title,
            "summary": summary,
            "github": f"https://github.com/{candidate_id.lower()}",
            "linkedin": "",
        },
        "skills": skills,
        "experience": [
            {
                "company": "OpenAI",
                "title": "ML Engineer",
                "duration_months": 24,
                "description": "Trained large language models using PyTorch and CUDA.",
            }
        ],
        "education": [
            {
                "institution": "MIT",
                "degree": "M.S.",
                "field": "Computer Science",
                "graduation_year": 2019,
            }
        ],
        "projects": [],
        "certifications": [],
        "redrob_signals": redrob_signals or {
            "recruiter_response_rate": 0.85,
            "last_active_date": "2026-05-15",
            "interview_completion_rate": 0.90,
        },
    }


def _make_honeypot_candidate(candidate_id: str = "CAND_HP001") -> dict[str, Any]:
    """Candidate with an advanced skill claiming 0 months — a honeypot."""
    return _make_candidate(
        candidate_id=candidate_id,
        title="Senior AI Engineer",
        skills=[
            {"name": "TensorFlow", "proficiency": "expert", "duration_months": 0},
            {"name": "Python", "proficiency": "intermediate", "duration_months": 30},
        ],
    )


def _make_title_trap_candidate(candidate_id: str = "CAND_TT001") -> dict[str, Any]:
    """Marketing Manager who stuffed 'LLM' and 'AI' into their summary."""
    return _make_candidate(
        candidate_id=candidate_id,
        title="Marketing Manager",
        skills=[
            {"name": "Excel", "proficiency": "expert", "duration_months": 60},
            {"name": "PowerPoint", "proficiency": "expert", "duration_months": 48},
            {"name": "LLM", "proficiency": "beginner", "duration_months": 1},
        ],
        summary=(
            "Dynamic Marketing Manager with extensive experience in AI-driven "
            "campaigns. Proficient in LLM tools, ChatGPT, and machine learning "
            "strategy. Led cross-functional teams using Python and data analytics."
        ),
    )


# ===========================================================================
# TestEmbeddingPipeline
# ===========================================================================


class TestEmbeddingPipeline:
    """Unit tests for EmbeddingPipeline feature extraction and similarity."""

    @pytest.fixture(scope="class")
    def pipeline(self):
        from backend.embeddings import EmbeddingPipeline
        return EmbeddingPipeline()

    # ── extract_features ─────────────────────────────────────────────────

    def test_extract_features_returns_required_keys(self, pipeline):
        candidate = _make_candidate()
        features = pipeline.extract_features(candidate)
        required = {
            "text_block", "embedding", "cosine_similarity",
            "skill_match", "experience_years", "top_skills",
        }
        assert required.issubset(features.keys()), (
            f"Missing keys: {required - features.keys()}"
        )

    def test_embedding_is_numpy_array(self, pipeline):
        features = pipeline.extract_features(_make_candidate())
        assert isinstance(features["embedding"], np.ndarray), (
            "embedding must be a np.ndarray"
        )

    def test_cosine_similarity_in_range(self, pipeline):
        features = pipeline.extract_features(_make_candidate())
        sim = features["cosine_similarity"]
        assert 0.0 <= sim <= 1.0, f"cosine_similarity out of range: {sim}"

    def test_skill_match_in_range(self, pipeline):
        features = pipeline.extract_features(_make_candidate())
        sm = features["skill_match"]
        assert 0.0 <= sm <= 1.0, f"skill_match out of range: {sm}"

    def test_experience_years_preserved(self, pipeline):
        candidate = _make_candidate(experience_years=7.5)
        features = pipeline.extract_features(candidate)
        assert features["experience_years"] == pytest.approx(7.5)

    def test_honeypot_skills_excluded_from_text_block(self, pipeline):
        """expert + 0-months skills must NOT appear in the weighted text block."""
        candidate = _make_candidate(
            skills=[
                {"name": "HoneypotSkillXYZ", "proficiency": "expert", "duration_months": 0},
                {"name": "Python", "proficiency": "expert", "duration_months": 48},
            ]
        )
        features = pipeline.extract_features(candidate)
        # The honeypot skill name should be absent from the text block.
        assert "HoneypotSkillXYZ" not in features["text_block"], (
            "Honeypot skill leaked into the embedding text block."
        )

    def test_top_skills_respects_duration_ordering(self, pipeline):
        candidate = _make_candidate(
            skills=[
                {"name": "SkillA", "proficiency": "expert", "duration_months": 10},
                {"name": "SkillB", "proficiency": "expert", "duration_months": 50},
                {"name": "SkillC", "proficiency": "expert", "duration_months": 30},
            ]
        )
        features = pipeline.extract_features(candidate)
        assert features["top_skills"][0] == "SkillB", (
            "Top skill should be the one with the longest duration."
        )

    def test_empty_candidate_does_not_crash(self, pipeline):
        bare = {"candidate_id": "CAND_BARE", "name": "Bare"}
        features = pipeline.extract_features(bare)
        assert isinstance(features["embedding"], np.ndarray)

    # ── compute_cosine_similarity ─────────────────────────────────────────

    def test_identical_vectors_give_similarity_one(self, pipeline):
        v = np.array([1.0, 2.0, 3.0])
        assert pipeline.compute_cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors_give_zero(self, pipeline):
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([0.0, 1.0, 0.0])
        assert pipeline.compute_cosine_similarity(a, b) == pytest.approx(0.0)

    def test_zero_vector_returns_zero(self, pipeline):
        zero = np.zeros(4)
        v = np.array([1.0, 2.0, 3.0, 4.0])
        assert pipeline.compute_cosine_similarity(zero, v) == 0.0

    def test_both_zero_vectors_return_zero(self, pipeline):
        z = np.zeros(5)
        assert pipeline.compute_cosine_similarity(z, z) == 0.0

    def test_nan_vector_returns_zero(self, pipeline):
        nan_vec = np.array([float("nan"), 1.0, 2.0])
        clean = np.array([1.0, 0.0, 0.0])
        # Should not raise; should return 0.0 (nan treated as zero-vector).
        result = pipeline.compute_cosine_similarity(nan_vec, clean)
        assert result == 0.0

    def test_inf_vector_returns_zero(self, pipeline):
        inf_vec = np.array([float("inf"), 1.0, 2.0])
        clean = np.array([1.0, 0.0, 0.0])
        result = pipeline.compute_cosine_similarity(inf_vec, clean)
        assert result == 0.0

    def test_shape_mismatch_raises_value_error(self, pipeline):
        with pytest.raises(ValueError, match="Shape mismatch"):
            pipeline.compute_cosine_similarity(np.array([1.0, 2.0]), np.array([1.0]))

    def test_list_inputs_accepted(self, pipeline):
        a = [1.0, 0.0]
        b = [1.0, 0.0]
        assert pipeline.compute_cosine_similarity(a, b) == pytest.approx(1.0)

    def test_result_clipped_to_zero_one(self, pipeline):
        """Cosine of anti-parallel vectors is -1; must be clipped to 0.0."""
        a = np.array([1.0, 0.0])
        b = np.array([-1.0, 0.0])
        result = pipeline.compute_cosine_similarity(a, b)
        assert result == 0.0, "Anti-parallel cosine should be clipped to 0.0, not -1.0."


# ===========================================================================
# TestComputeHybridScore  (ScoringEngine.compute_hybrid_score)
# ===========================================================================


class TestComputeHybridScore:
    """Unit tests for the hybrid scoring formula in ScoringEngine."""

    @pytest.fixture(scope="class")
    def engine(self):
        from backend.scoring import ScoringEngine
        from backend.embeddings import EmbeddingPipeline
        return ScoringEngine(embedding_pipeline=EmbeddingPipeline())

    def test_clean_candidate_score_in_open_range(self, engine):
        candidate = _make_candidate()
        score = engine.compute_hybrid_score(
            semantic_similarity=0.75,
            candidate=candidate,
            skill_match=0.60,
            experience_years=6.0,
        )
        assert 0.0 < score <= 1.0, f"Expected (0, 1], got {score}"

    def test_honeypot_score_is_exactly_zero(self, engine):
        """Req 2: honeypot must always produce a score of exactly 0.0."""
        candidate = _make_honeypot_candidate()
        score = engine.compute_hybrid_score(
            semantic_similarity=0.95,   # even with a high semantic score
            candidate=candidate,
            skill_match=0.90,
            experience_years=10.0,
        )
        assert score == 0.0, f"Honeypot score must be 0.0, got {score}"

    def test_title_trap_applies_strict_015_factor(self, engine):
        """Req 1: title-trap factor must be ≤ 0.15× the base score."""
        trap_candidate = _make_title_trap_candidate()
        clean_candidate = _make_candidate()  # same signals, no trap

        trap_score = engine.compute_hybrid_score(
            semantic_similarity=0.80,
            candidate=trap_candidate,
            skill_match=0.50,
            experience_years=5.0,
        )
        clean_score = engine.compute_hybrid_score(
            semantic_similarity=0.80,
            candidate=clean_candidate,
            skill_match=0.50,
            experience_years=5.0,
        )
        # Trap score must be ≤ 15% of the equivalent clean score.
        assert trap_score <= clean_score * 0.15 + 1e-9, (
            f"Title-trap score {trap_score:.6f} exceeds 15% of clean "
            f"score {clean_score:.6f} (threshold={clean_score * 0.15:.6f})"
        )

    def test_title_trap_score_not_zero(self, engine):
        """Title-trap is penalised, but not eliminated (unlike honeypot)."""
        trap = _make_title_trap_candidate()
        score = engine.compute_hybrid_score(
            semantic_similarity=0.70,
            candidate=trap,
            skill_match=0.30,
            experience_years=3.0,
        )
        # Should be > 0 (just heavily penalised).
        assert score > 0.0, "Title-trap score should be > 0 (use honeypot for hard zero)."

    def test_score_is_clipped_to_one(self, engine):
        """Score must never exceed 1.0."""
        candidate = _make_candidate()
        score = engine.compute_hybrid_score(
            semantic_similarity=1.0,
            candidate=candidate,
            skill_match=1.0,
            experience_years=100.0,
        )
        assert score <= 1.0, f"Score exceeded 1.0: {score}"

    def test_higher_semantic_gives_higher_score(self, engine):
        c1 = _make_candidate("CAND_A")
        c2 = _make_candidate("CAND_B")
        low = engine.compute_hybrid_score(0.30, c1, 0.30, 3.0)
        high = engine.compute_hybrid_score(0.90, c2, 0.30, 3.0)
        assert high > low, "Higher semantic similarity should yield higher score."


# ===========================================================================
# TestTrapMitigation  (Integration — Req 1)
# ===========================================================================


class TestTrapMitigation:
    """Integration test: Marketing Manager keyword-stuffer is penalised."""

    @pytest.fixture(scope="class")
    def engine(self):
        from backend.scoring import ScoringEngine
        from backend.embeddings import EmbeddingPipeline
        return ScoringEngine(embedding_pipeline=EmbeddingPipeline())

    @pytest.fixture(scope="class")
    def trap_result(self, engine):
        candidate = _make_title_trap_candidate("CAND_TRAP")
        return engine.score_candidate(candidate)

    def test_status_is_title_trap(self, trap_result):
        assert trap_result["status"] == "TITLE_TRAP", (
            f"Expected status='TITLE_TRAP', got {trap_result['status']!r}"
        )

    def test_score_is_penalised(self, trap_result, engine):
        """Score must be ≤ 15% of what a clean candidate with same signals would get."""
        clean = _make_candidate("CAND_CLEAN_REF")
        clean_result = engine.score_candidate(clean)
        assert trap_result["score"] <= clean_result["score"] * 0.15 + 1e-6, (
            f"Trap score {trap_result['score']:.6f} not sufficiently penalised vs "
            f"clean score {clean_result['score']:.6f}."
        )

    def test_is_title_trap_flag_true(self):
        from backend.scoring import HeuristicFilter
        candidate = _make_title_trap_candidate()
        assert HeuristicFilter.is_title_trap(candidate) is True

    def test_reasoning_mentions_title_trap(self, trap_result):
        assert "title" in trap_result["reasoning"].lower() or \
               "non-technical" in trap_result["reasoning"].lower(), (
            "Reasoning should mention the title-trap penalty."
        )

    def test_best_alternate_roles_populated(self, trap_result):
        assert len(trap_result["analysis"]["best_alternate_roles"]) > 0, (
            "Title-trap candidate should have alternate roles suggested."
        )


# ===========================================================================
# TestHoneypotElimination  (Integration — Req 2)
# ===========================================================================


class TestHoneypotElimination:
    """Integration test: honeypot profile receives exactly 0.0 final score."""

    @pytest.fixture(scope="class")
    def engine(self):
        from backend.scoring import ScoringEngine
        from backend.embeddings import EmbeddingPipeline
        return ScoringEngine(embedding_pipeline=EmbeddingPipeline())

    @pytest.fixture(scope="class")
    def hp_result(self, engine):
        candidate = _make_honeypot_candidate("CAND_HP_INTEG")
        return engine.score_candidate(candidate)

    def test_score_is_exactly_zero(self, hp_result):
        """Req 2: final score must be exactly 0.0 — not 0.001, not 1e-10."""
        assert hp_result["score"] == 0.0, (
            f"Honeypot final score must be exactly 0.0, got {hp_result['score']!r}"
        )

    def test_status_is_honeypot(self, hp_result):
        assert hp_result["status"] == "HONEYPOT", (
            f"Expected status='HONEYPOT', got {hp_result['status']!r}"
        )

    def test_is_honeypot_flag_true(self):
        from backend.scoring import HeuristicFilter
        candidate = _make_honeypot_candidate()
        assert HeuristicFilter.is_honeypot(candidate) is True

    def test_expert_nonzero_duration_is_not_honeypot(self):
        from backend.scoring import HeuristicFilter
        candidate = _make_candidate(
            skills=[{"name": "Python", "proficiency": "expert", "duration_months": 24}]
        )
        assert HeuristicFilter.is_honeypot(candidate) is False

    def test_intermediate_zero_months_is_not_honeypot(self):
        from backend.scoring import HeuristicFilter
        candidate = _make_candidate(
            skills=[{"name": "Spark", "proficiency": "intermediate", "duration_months": 0}]
        )
        assert HeuristicFilter.is_honeypot(candidate) is False

    def test_reasoning_mentions_honeypot(self, hp_result):
        assert "honeypot" in hp_result["reasoning"].lower(), (
            "Reasoning must mention the honeypot disqualification."
        )

    def test_get_base_penalty_is_zero(self):
        from backend.scoring import HeuristicFilter
        candidate = _make_honeypot_candidate()
        assert HeuristicFilter.get_base_penalty(candidate) == 0.0

    def test_honeypot_beats_title_trap_in_priority(self):
        """A honeypot+title-trap candidate must still score 0.0."""
        from backend.scoring import HeuristicFilter
        candidate = _make_candidate(
            title="Marketing Manager",
            skills=[{"name": "GPT-4", "proficiency": "expert", "duration_months": 0}],
        )
        assert HeuristicFilter.get_base_penalty(candidate) == 0.0


# ===========================================================================
# TestDeterministicSorting  (Integration — Req 3)
# ===========================================================================


class TestDeterministicSorting:
    """Integration test: sort_and_format_submission meets the validator contract.

    Scenario: 5 candidates, 3 of them sharing the exact same score (0.77).

    Expected ranking after sort:
        Rank 1 → CAND_APEX  (score=0.95, unique top)
        Rank 2 → CAND_BETA  (score=0.82, unique second)
        Rank 3 → CAND_ALPHA (score=0.77, tie-broken by id: ALPHA < GAMMA < ZETA)
        Rank 4 → CAND_GAMMA (score=0.77)
        Rank 5 → CAND_ZETA  (score=0.77)
    """

    _TIED_SCORE: float = 0.77

    @pytest.fixture
    def candidates(self) -> list[dict[str, Any]]:
        """5 candidates, 3 tied on score, submitted in shuffled order."""
        return [
            {"candidate_id": "CAND_ZETA",  "score": self._TIED_SCORE, "reasoning": "x"},
            {"candidate_id": "CAND_APEX",  "score": 0.95,              "reasoning": "x"},
            {"candidate_id": "CAND_ALPHA", "score": self._TIED_SCORE, "reasoning": "x"},
            {"candidate_id": "CAND_GAMMA", "score": self._TIED_SCORE, "reasoning": "x"},
            {"candidate_id": "CAND_BETA",  "score": 0.82,              "reasoning": "x"},
        ]

    @pytest.fixture
    def ranked(self, candidates) -> list[dict[str, Any]]:
        from backend.ranking import sort_and_format_submission
        return sort_and_format_submission(candidates)

    def test_primary_sort_score_descending(self, ranked):
        """Scores must be monotonically non-increasing."""
        scores = [r["score"] for r in ranked]
        assert scores == sorted(scores, reverse=True), (
            f"Scores are not sorted descending: {scores}"
        )

    def test_rank_1_is_highest_score(self, ranked):
        assert ranked[0]["candidate_id"] == "CAND_APEX"
        assert ranked[0]["score"] == pytest.approx(0.95)

    def test_rank_2_is_second_highest(self, ranked):
        assert ranked[1]["candidate_id"] == "CAND_BETA"
        assert ranked[1]["score"] == pytest.approx(0.82)

    def test_tie_break_alphabetical_ascending(self, ranked):
        """Tied candidates must be ordered by candidate_id ascending."""
        tied = [r for r in ranked if r["score"] == pytest.approx(self._TIED_SCORE)]
        tied_ids = [r["candidate_id"] for r in tied]
        assert tied_ids == sorted(tied_ids), (
            f"Tied candidates not sorted by id: {tied_ids}"
        )

    def test_tied_candidate_order_exact(self, ranked):
        tied = [r for r in ranked if r["score"] == pytest.approx(self._TIED_SCORE)]
        assert [r["candidate_id"] for r in tied] == [
            "CAND_ALPHA", "CAND_GAMMA", "CAND_ZETA"
        ]

    def test_ranks_assigned_sequentially(self, ranked):
        """Ranks must be 1, 2, 3, 4, 5 — no gaps."""
        ranks = [r["rank"] for r in ranked]
        assert ranks == list(range(1, len(ranked) + 1)), (
            f"Ranks are not sequential: {ranks}"
        )

    def test_rank_1_assigned_to_first(self, ranked):
        assert ranked[0]["rank"] == 1

    def test_returns_max_100(self):
        from backend.ranking import sort_and_format_submission
        large = [
            {"candidate_id": f"CAND_{i:04d}", "score": float(i) / 200, "reasoning": "x"}
            for i in range(200)
        ]
        result = sort_and_format_submission(large)
        assert len(result) == 100

    def test_fewer_than_100_returns_all(self):
        from backend.ranking import sort_and_format_submission
        small = [
            {"candidate_id": f"CAND_{i:03d}", "score": 0.5, "reasoning": "x"}
            for i in range(30)
        ]
        result = sort_and_format_submission(small)
        assert len(result) == 30

    def test_empty_input_returns_empty(self):
        from backend.ranking import sort_and_format_submission
        assert sort_and_format_submission([]) == []

    def test_missing_candidate_id_raises(self):
        from backend.ranking import sort_and_format_submission
        with pytest.raises(ValueError, match="candidate_id"):
            sort_and_format_submission([{"score": 0.5, "reasoning": "x"}])

    def test_missing_score_raises(self):
        from backend.ranking import sort_and_format_submission
        with pytest.raises(ValueError, match="score"):
            sort_and_format_submission([{"candidate_id": "CAND_1", "reasoning": "x"}])


# ===========================================================================
# TestAvailabilityModifier
# ===========================================================================


class TestAvailabilityModifier:
    """Unit tests for the Redrob behavioural signal modifier."""

    def _modifier(self, signals: dict) -> float:
        from backend.scoring import ScoringEngine
        candidate = {"redrob_signals": signals}
        return ScoringEngine._compute_availability_modifier(candidate)

    def test_perfect_signals_gives_high_modifier(self):
        mod = self._modifier({
            "recruiter_response_rate": 1.0,
            "last_active_date": "2026-06-01",
            "interview_completion_rate": 1.0,
        })
        assert mod >= 0.90, f"Perfect signals should yield modifier ≥ 0.90, got {mod:.4f}"

    def test_missing_signals_defaults_to_neutral(self):
        mod = self._modifier({})
        assert 0.60 <= mod <= 1.0, (
            f"Missing signals should produce a neutral modifier in [0.60, 1.0], got {mod:.4f}"
        )

    def test_old_last_active_reduces_modifier(self):
        recent = self._modifier({"last_active_date": "2026-05-28"})
        stale = self._modifier({"last_active_date": "2025-06-01"})  # ~12 months idle
        assert stale < recent, (
            f"Stale activity ({stale:.4f}) should give lower modifier than "
            f"recent ({recent:.4f})."
        )

    def test_modifier_never_below_floor(self):
        """Modifier must always be ≥ _AVAILABILITY_FLOOR (0.60)."""
        from backend.scoring import _AVAILABILITY_FLOOR
        mod = self._modifier({
            "recruiter_response_rate": 0.0,
            "last_active_date": "2020-01-01",
            "interview_completion_rate": 0.0,
        })
        assert mod >= _AVAILABILITY_FLOOR, (
            f"Modifier {mod:.4f} fell below floor {_AVAILABILITY_FLOOR}"
        )

    def test_modifier_never_above_one(self):
        mod = self._modifier({
            "recruiter_response_rate": 1.0,
            "last_active_date": "2026-06-01",
            "interview_completion_rate": 1.0,
        })
        assert mod <= 1.0

    def test_invalid_date_uses_neutral(self):
        """Unparseable date should not raise — it should use the neutral default."""
        mod = self._modifier({"last_active_date": "not-a-date"})
        assert 0.60 <= mod <= 1.0


# ===========================================================================
# TestScoringEngineIntegration
# ===========================================================================


class TestScoringEngineIntegration:
    """End-to-end: score_candidate returns all required enrichment fields."""

    @pytest.fixture(scope="class")
    def engine(self):
        from backend.scoring import ScoringEngine
        from backend.embeddings import EmbeddingPipeline
        return ScoringEngine(embedding_pipeline=EmbeddingPipeline())

    @pytest.fixture(scope="class")
    def result(self, engine):
        return engine.score_candidate(_make_candidate("CAND_E2E"))

    def test_all_enrichment_keys_present(self, result):
        required = {"score", "skill_match", "semantic_match",
                    "status", "reasoning", "analysis"}
        assert required.issubset(result.keys()), (
            f"Missing enrichment keys: {required - result.keys()}"
        )

    def test_analysis_has_required_sub_keys(self, result):
        analysis = result["analysis"]
        assert "why_selected" in analysis
        assert "missing_skills" in analysis
        assert "best_alternate_roles" in analysis

    def test_score_is_float_in_range(self, result):
        assert isinstance(result["score"], float)
        assert 0.0 <= result["score"] <= 1.0

    def test_status_is_clean_for_valid_candidate(self, result):
        assert result["status"] == "CLEAN"

    def test_reasoning_is_non_empty_string(self, result):
        assert isinstance(result["reasoning"], str)
        assert len(result["reasoning"]) > 10

    def test_missing_skills_is_list(self, result):
        assert isinstance(result["analysis"]["missing_skills"], list)

    def test_best_alternate_roles_is_list(self, result):
        assert isinstance(result["analysis"]["best_alternate_roles"], list)

    def test_skill_match_is_float_in_range(self, result):
        sm = result["skill_match"]
        assert isinstance(sm, float)
        assert 0.0 <= sm <= 1.0

    def test_semantic_match_is_float_in_range(self, result):
        sem = result["semantic_match"]
        assert isinstance(sem, float)
        assert 0.0 <= sem <= 1.0
