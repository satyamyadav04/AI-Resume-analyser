"""
tests/test_phase3.py — Automated Phase-3 Unit & Integration Tests
==================================================================
Covers VectorRanker, ExplanationEngine, validate_submission, and the
end-to-end execute_pipeline with synthetic data.

Run with:
    python -m pytest tests/test_phase3.py -v
"""

from __future__ import annotations

import csv
import gzip
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_candidate(
    candidate_id: str = "CAND_001",
    title: str = "Senior AI Engineer",
    skills: list[dict] | None = None,
    experience_years: float = 5.0,
    summary: str = "Experienced AI engineer with NLP and deep learning.",
) -> dict[str, Any]:
    if skills is None:
        skills = [
            {"name": "Python", "proficiency": "expert", "duration_months": 48},
            {"name": "PyTorch", "proficiency": "advanced", "duration_months": 36},
            {"name": "NLP", "proficiency": "intermediate", "duration_months": 24},
        ]
    return {
        "candidate_id": candidate_id,
        "name": f"Test {candidate_id}",
        "experience_years": experience_years,
        "profile": {
            "current_title": title,
            "summary": summary,
            "github": "https://github.com/test",
            "linkedin": "",
        },
        "skills": skills,
        "experience": [
            {
                "company": "OpenAI",
                "title": "ML Engineer",
                "duration_months": 24,
                "description": "Trained LLMs with PyTorch.",
            }
        ],
        "education": [],
        "projects": [],
        "certifications": [],
        "redrob_signals": {
            "recruiter_response_rate": 0.85,
            "last_active_date": "2026-05-20",
            "interview_completion_rate": 0.90,
        },
    }


def _write_jsonl_gz(records: list[dict], path: str) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


# ===========================================================================
# TestVectorRanker
# ===========================================================================


class TestVectorRanker:
    """Unit tests for VectorRanker.build_index and query_top_k."""

    DIM = 8  # small dimension for fast tests

    @pytest.fixture
    def ranker(self):
        from backend.ranking import VectorRanker
        return VectorRanker(embedding_dim=self.DIM)

    @pytest.fixture
    def vectors(self):
        rng = np.random.default_rng(42)
        return rng.random((20, self.DIM)).astype(np.float32)

    def test_build_index_sets_n_indexed(self, ranker, vectors):
        ranker.build_index(vectors)
        assert ranker.n_indexed == 20

    def test_build_index_updates_embedding_dim_on_mismatch(self):
        from backend.ranking import VectorRanker
        r = VectorRanker(embedding_dim=self.DIM)
        wrong_dim_vectors = np.random.rand(5, self.DIM + 4).astype(np.float32)
        r.build_index(wrong_dim_vectors)
        assert r.embedding_dim == self.DIM + 4

    def test_build_index_rejects_empty(self, ranker):
        with pytest.raises(ValueError, match="empty"):
            ranker.build_index(np.empty((0, self.DIM), dtype=np.float32))

    def test_build_index_rejects_1d(self, ranker):
        with pytest.raises(ValueError, match="2-D"):
            ranker.build_index(np.ones(self.DIM, dtype=np.float32))

    def test_query_top_k_without_build_raises(self, ranker):
        q = np.ones(self.DIM, dtype=np.float32)
        with pytest.raises(RuntimeError, match="build_index"):
            ranker.query_top_k(q)

    def test_query_returns_correct_shapes(self, ranker, vectors):
        ranker.build_index(vectors)
        q = np.ones(self.DIM, dtype=np.float32)
        indices, scores = ranker.query_top_k(q, k=5)
        assert indices.shape == (5,)
        assert scores.shape == (5,)

    def test_scores_are_descending(self, ranker, vectors):
        ranker.build_index(vectors)
        q = np.random.rand(self.DIM).astype(np.float32)
        _, scores = ranker.query_top_k(q, k=10)
        assert list(scores) == sorted(scores.tolist(), reverse=True), (
            "Scores from query_top_k must be in descending order."
        )

    def test_scores_clipped_to_0_1(self, ranker, vectors):
        ranker.build_index(vectors)
        q = np.random.rand(self.DIM).astype(np.float32)
        _, scores = ranker.query_top_k(q, k=10)
        assert np.all(scores >= 0.0) and np.all(scores <= 1.0), (
            "All scores must be in [0, 1]."
        )

    def test_query_k_clamped_to_n_indexed(self, ranker, vectors):
        ranker.build_index(vectors)  # 20 vectors
        q = np.random.rand(self.DIM).astype(np.float32)
        indices, scores = ranker.query_top_k(q, k=9999)
        assert len(indices) == 20, "k must be clamped to n_indexed."

    def test_perfect_match_candidate_is_top_result(self, ranker):
        """The JD vector itself (as a candidate) must rank #1."""
        from backend.ranking import VectorRanker
        r = VectorRanker(embedding_dim=self.DIM)
        jd = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        others = np.random.rand(10, self.DIM).astype(np.float32) * 0.5
        # Insert JD vector at row 7
        mat = np.vstack([others[:7], jd.reshape(1, -1), others[7:]])
        r.build_index(mat)
        indices, scores = r.query_top_k(jd, k=5)
        assert indices[0] == 7, "Perfect-match vector should be rank-1."
        assert scores[0] == pytest.approx(1.0, abs=1e-5)

    def test_2d_query_accepted(self, ranker, vectors):
        ranker.build_index(vectors)
        q = np.random.rand(1, self.DIM).astype(np.float32)
        indices, scores = ranker.query_top_k(q, k=3)
        assert len(indices) == 3


# ===========================================================================
# TestExplanationEngine
# ===========================================================================


class TestExplanationEngine:
    """Unit tests for ExplanationEngine.generate_reasoning and export_to_csv."""

    @pytest.fixture
    def engine(self):
        from backend.utils import ExplanationEngine
        return ExplanationEngine()

    # ── generate_reasoning ────────────────────────────────────────────────

    def test_generate_reasoning_returns_string(self, engine):
        candidate = _make_candidate()
        result = engine.generate_reasoning(candidate, semantic_score=0.75)
        assert isinstance(result, str)
        assert len(result) > 20

    def test_reasoning_contains_title(self, engine):
        candidate = _make_candidate(title="Senior AI Engineer")
        result = engine.generate_reasoning(candidate, semantic_score=0.70)
        assert "Senior AI Engineer" in result

    def test_reasoning_contains_experience_years(self, engine):
        candidate = _make_candidate(experience_years=7.3)
        result = engine.generate_reasoning(candidate, semantic_score=0.65)
        assert "7.3" in result

    def test_reasoning_contains_verified_skill_count(self, engine):
        candidate = _make_candidate(skills=[
            {"name": "python", "proficiency": "expert", "duration_months": 48},
            {"name": "pytorch", "proficiency": "expert", "duration_months": 36},
            # honeypot — should NOT count (duration=0)
            {"name": "llm", "proficiency": "expert", "duration_months": 0},
        ])
        result = engine.generate_reasoning(candidate, semantic_score=0.60)
        # Only 2 verified (duration > 0 and in core set), NOT 3.
        assert "2 verified" in result

    def test_reasoning_no_api_latency(self, engine):
        """generate_reasoning must complete in well under 1 ms (template only)."""
        import time
        candidate = _make_candidate()
        t0 = time.perf_counter()
        for _ in range(100):
            engine.generate_reasoning(candidate, semantic_score=0.80)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert elapsed_ms < 500, (
            f"100 reasoning calls took {elapsed_ms:.1f} ms; expected < 500 ms."
        )

    def test_reasoning_semantic_label_excellent(self, engine):
        result = engine.generate_reasoning(_make_candidate(), semantic_score=0.90)
        assert "excellent" in result

    def test_reasoning_semantic_label_low(self, engine):
        result = engine.generate_reasoning(_make_candidate(), semantic_score=0.20)
        assert "low" in result

    # ── export_to_csv ─────────────────────────────────────────────────────

    def test_export_creates_file(self, engine, tmp_path):
        candidates = [
            {**_make_candidate(f"CAND_{i:03d}"), "rank": i, "score": 0.9 - i * 0.01,
             "reasoning": "Test reasoning."}
            for i in range(1, 6)
        ]
        out = str(tmp_path / "out.csv")
        engine.export_to_csv(candidates, out)
        assert os.path.exists(out)

    def test_export_has_correct_columns(self, engine, tmp_path):
        c = {**_make_candidate(), "rank": 1, "score": 0.75, "reasoning": "OK."}
        out = str(tmp_path / "out.csv")
        engine.export_to_csv([c], out)
        with open(out, newline="") as fh:
            header = next(csv.reader(fh))
        assert set(header) == {"candidate_id", "rank", "score", "reasoning"}

    def test_export_score_exactly_4dp(self, engine, tmp_path):
        c = {**_make_candidate(), "rank": 1, "score": 0.123456789, "reasoning": "Test."}
        out = str(tmp_path / "out.csv")
        engine.export_to_csv([c], out)
        with open(out, newline="") as fh:
            rows = list(csv.DictReader(fh))
        score_str = rows[0]["score"]
        # Must have exactly 4 decimal places.
        assert "." in score_str
        decimal_part = score_str.split(".")[1]
        assert len(decimal_part) == 4, (
            f"Score '{score_str}' must have exactly 4 decimal places."
        )
        assert score_str == "0.1235", f"Expected '0.1235', got '{score_str}'."

    def test_export_empty_raises(self, engine, tmp_path):
        with pytest.raises(ValueError, match="empty"):
            engine.export_to_csv([], str(tmp_path / "out.csv"))

    def test_export_creates_parent_dirs(self, engine, tmp_path):
        nested_path = str(tmp_path / "a" / "b" / "c" / "out.csv")
        c = {**_make_candidate(), "rank": 1, "score": 0.5, "reasoning": "x"}
        engine.export_to_csv([c], nested_path)
        assert os.path.exists(nested_path)

    def test_export_row_count_matches(self, engine, tmp_path):
        candidates = [
            {**_make_candidate(f"CAND_{i:03d}"), "rank": i, "score": 0.5, "reasoning": "x"}
            for i in range(1, 11)
        ]
        out = str(tmp_path / "out.csv")
        engine.export_to_csv(candidates, out)
        with open(out, newline="") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == 10


# ===========================================================================
# TestValidateSubmission
# ===========================================================================


class TestValidateSubmission:
    """Unit tests for validate_submission.validate()."""

    @pytest.fixture(autouse=True)
    def _import_validate(self):
        """Load the validator module dynamically (it lives in project root)."""
        import importlib.util
        project_root = Path(__file__).parent.parent
        validator_path = project_root / "validate_submission.py"
        spec = importlib.util.spec_from_file_location("validate_submission", validator_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.validate = mod.validate

    def _write_csv(self, path: str, rows: list[dict]) -> None:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=["candidate_id", "rank", "score", "reasoning"],
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(rows)

    def _good_rows(self, n: int = 5) -> list[dict]:
        score = 0.95
        rows = []
        for i in range(1, n + 1):
            rows.append({
                "candidate_id": f"CAND_{i:04d}",
                "rank": i,
                "score": f"{score:.4f}",
                "reasoning": "Good candidate.",
            })
            score -= 0.01
        return rows

    def test_valid_csv_passes(self, tmp_path):
        p = str(tmp_path / "ok.csv")
        self._write_csv(p, self._good_rows(10))
        assert self.validate(p) == []

    def test_missing_file_returns_error(self):
        errors = self.validate("/no/such/file.csv")
        assert any("not found" in e.lower() for e in errors)

    def test_over_100_rows_fails(self, tmp_path):
        p = str(tmp_path / "big.csv")
        self._write_csv(p, self._good_rows(101))
        errors = self.validate(p)
        assert any("100" in e for e in errors)

    def test_duplicate_candidate_id_fails(self, tmp_path):
        p = str(tmp_path / "dup.csv")
        rows = self._good_rows(3)
        rows[2]["candidate_id"] = rows[0]["candidate_id"]  # duplicate
        self._write_csv(p, rows)
        errors = self.validate(p)
        assert any("duplicate" in e.lower() for e in errors)

    def test_wrong_rank_order_fails(self, tmp_path):
        p = str(tmp_path / "rank.csv")
        rows = self._good_rows(3)
        rows[0]["rank"] = 2  # wrong
        rows[1]["rank"] = 1
        self._write_csv(p, rows)
        errors = self.validate(p)
        assert any("rank" in e.lower() for e in errors)

    def test_score_out_of_range_fails(self, tmp_path):
        p = str(tmp_path / "score.csv")
        rows = self._good_rows(3)
        rows[0]["score"] = "1.5"
        self._write_csv(p, rows)
        errors = self.validate(p)
        assert any("score" in e.lower() and "1.5" in e for e in errors)

    def test_score_not_descending_fails(self, tmp_path):
        p = str(tmp_path / "desc.csv")
        rows = self._good_rows(3)
        # Reverse order → row 2 higher than row 1.
        rows[0]["score"] = "0.50"
        rows[1]["score"] = "0.90"
        self._write_csv(p, rows)
        errors = self.validate(p)
        assert any("sort" in e.lower() or "desc" in e.lower() or "previous" in e.lower()
                   for e in errors)

    def test_empty_reasoning_fails(self, tmp_path):
        p = str(tmp_path / "reas.csv")
        rows = self._good_rows(2)
        rows[1]["reasoning"] = ""
        self._write_csv(p, rows)
        errors = self.validate(p)
        assert any("reasoning" in e.lower() for e in errors)

    def test_tie_break_violation_fails(self, tmp_path):
        """Same score but candidate_id NOT ascending → validation error."""
        p = str(tmp_path / "tie.csv")
        with open(p, "w", newline="") as fh:
            w = csv.DictWriter(
                fh,
                fieldnames=["candidate_id", "rank", "score", "reasoning"],
                lineterminator="\n",
            )
            w.writeheader()
            w.writerow({"candidate_id": "CAND_Z", "rank": 1,
                        "score": "0.8000", "reasoning": "x"})
            w.writerow({"candidate_id": "CAND_A", "rank": 2,
                        "score": "0.8000", "reasoning": "x"})
        errors = self.validate(p)
        assert any("tie" in e.lower() or "tie-breaker" in e.lower()
                   for e in errors)


# ===========================================================================
# TestEndToEndPipeline
# ===========================================================================


class TestEndToEndPipeline:
    """Integration test: execute_pipeline on synthetic 200-candidate dataset."""

    @pytest.fixture(scope="class")
    def pipeline_output(self, tmp_path_factory):
        """Run the full pipeline on 200 synthetic candidates."""
        tmp = tmp_path_factory.mktemp("e2e")
        gz_path = str(tmp / "candidates.jsonl.gz")
        out_csv = str(tmp / "sample_submission.csv")

        # Generate 200 candidates (mix of clean, traps, honeypots)
        records: list[dict] = []
        for i in range(1, 181):
            records.append(_make_candidate(f"CAND_{i:04d}"))
        for i in range(181, 196):
            records.append(_make_candidate(
                f"CAND_{i:04d}", title="Marketing Manager",
                skills=[{"name": "Excel", "proficiency": "expert", "duration_months": 60}],
            ))
        for i in range(196, 201):
            records.append(_make_candidate(
                f"CAND_{i:04d}",
                skills=[{"name": "TensorFlow", "proficiency": "expert", "duration_months": 0}],
            ))
        _write_jsonl_gz(records, gz_path)

        from backend.main import execute_pipeline
        top100 = execute_pipeline(
            candidates_gzip_path=gz_path,
            jd_path=None,
            output_csv_path=out_csv,
            faiss_top_k=200,
            run_validator=True,
            log_level="WARNING",
        )
        return top100, out_csv

    def test_returns_exactly_100(self, pipeline_output):
        top100, _ = pipeline_output
        assert len(top100) == 100

    def test_ranks_are_1_to_100(self, pipeline_output):
        top100, _ = pipeline_output
        ranks = [c["rank"] for c in top100]
        assert ranks == list(range(1, 101))

    def test_scores_descending(self, pipeline_output):
        top100, _ = pipeline_output
        scores = [c["score"] for c in top100]
        assert scores == sorted(scores, reverse=True)

    def test_csv_file_written(self, pipeline_output):
        _, out_csv = pipeline_output
        assert os.path.exists(out_csv)

    def test_csv_passes_validator(self, pipeline_output):
        import importlib.util
        _, out_csv = pipeline_output
        project_root = Path(__file__).parent.parent
        spec = importlib.util.spec_from_file_location(
            "validate_submission", project_root / "validate_submission.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        errors = mod.validate(out_csv)
        assert errors == [], f"Validator reported errors:\n" + "\n".join(errors)

    def test_honeypots_excluded_from_top100(self, pipeline_output):
        top100, _ = pipeline_output
        for c in top100:
            assert c.get("status") != "HONEYPOT", (
                f"Honeypot {c['candidate_id']} made it into top-100!"
            )

    def test_all_candidates_have_reasoning(self, pipeline_output):
        top100, _ = pipeline_output
        for c in top100:
            assert c.get("reasoning"), f"{c['candidate_id']} has empty reasoning."

    def test_tie_break_respected(self, pipeline_output):
        """Within each score bucket, candidate_id must be ascending."""
        top100, _ = pipeline_output
        prev_score: float = float("inf")
        prev_id: str = ""
        for c in top100:
            score = c["score"]
            cid = c["candidate_id"]
            if abs(score - prev_score) < 1e-9:
                assert cid >= prev_id, (
                    f"Tie-break violation: {cid} < {prev_id} at score={score:.4f}"
                )
            prev_score = score
            prev_id = cid

    def test_csv_score_has_4dp(self, pipeline_output):
        _, out_csv = pipeline_output
        with open(out_csv, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                score_str = row["score"]
                decimal_part = score_str.split(".")[1] if "." in score_str else ""
                assert len(decimal_part) == 4, (
                    f"Score '{score_str}' does not have exactly 4 decimal places."
                )
