"""
tests/test_phase1.py — Unit tests for Phase-1: Ingestion and Trap Filtering
===========================================================================
Tests cover:
  • CandidateParser  – streaming, malformed-line skipping
  • HeuristicFilter  – title trap, honeypot, penalty multiplier
  • sort_and_format_submission – sort order, rank assignment, top-100 limit
  • format_candidate_for_api  – field extraction

Run with:
    python -m pytest tests/test_phase1.py -v
"""

from __future__ import annotations

import gzip
import json
import os
import tempfile
from typing import Any

import pytest

from backend.parser import CandidateParser
from backend.scoring import HeuristicFilter
from backend.ranking import sort_and_format_submission, format_candidate_for_api

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_candidate(
    candidate_id: str = "CAND_001",
    title: str = "Senior AI Engineer",
    skills: list[dict] | None = None,
    experience_years: float = 5.0,
) -> dict[str, Any]:
    if skills is None:
        skills = [
            {"name": "Python", "proficiency": "expert", "duration_months": 36},
            {"name": "PyTorch", "proficiency": "advanced", "duration_months": 24},
        ]
    return {
        "candidate_id": candidate_id,
        "name": "Test Candidate",
        "experience_years": experience_years,
        "profile": {
            "current_title": title,
            "summary": "AI engineer with deep learning and NLP experience.",
        },
        "skills": skills,
        "experience": [],
        "education": [],
        "projects": [],
    }


def _write_jsonl_gz(records: list[dict], path: str) -> None:
    """Write a list of dicts as gzip JSONL to *path*."""
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record) + "\n")


# ===========================================================================
# CandidateParser
# ===========================================================================

class TestCandidateParser:

    def test_streams_all_valid_records(self, tmp_path):
        records = [_make_candidate(f"CAND_{i:03d}") for i in range(10)]
        gz_file = str(tmp_path / "candidates.jsonl.gz")
        _write_jsonl_gz(records, gz_file)

        parser = CandidateParser()
        result = list(parser.stream_candidates(gz_file))

        assert len(result) == 10
        assert parser.stats["total_read"] == 10
        assert parser.stats["total_skipped"] == 0

    def test_streams_plain_jsonl_records(self, tmp_path):
        records = [_make_candidate(f"CAND_{i:03d}") for i in range(3)]
        jsonl_file = tmp_path / "candidates.jsonl"
        with jsonl_file.open("w", encoding="utf-8") as fh:
            for record in records:
                fh.write(json.dumps(record) + "\n")

        parser = CandidateParser()
        result = list(parser.stream_candidates(str(jsonl_file)))

        assert len(result) == 3
        assert parser.stats["total_read"] == 3
        assert parser.stats["total_skipped"] == 0

    def test_skips_malformed_json(self, tmp_path):
        gz_file = str(tmp_path / "candidates.jsonl.gz")
        with gzip.open(gz_file, "wt") as fh:
            fh.write(json.dumps(_make_candidate("CAND_001")) + "\n")
            fh.write("{this is not valid json}\n")          # malformed
            fh.write(json.dumps(_make_candidate("CAND_002")) + "\n")

        parser = CandidateParser()
        result = list(parser.stream_candidates(gz_file))

        assert len(result) == 2
        assert parser.stats["total_skipped"] == 1

    def test_skips_records_missing_candidate_id(self, tmp_path):
        gz_file = str(tmp_path / "candidates.jsonl.gz")
        with gzip.open(gz_file, "wt") as fh:
            fh.write(json.dumps({"name": "No ID here"}) + "\n")
            fh.write(json.dumps(_make_candidate("CAND_001")) + "\n")

        parser = CandidateParser()
        result = list(parser.stream_candidates(gz_file))

        assert len(result) == 1
        assert result[0]["candidate_id"] == "CAND_001"

    def test_skips_blank_lines(self, tmp_path):
        gz_file = str(tmp_path / "candidates.jsonl.gz")
        with gzip.open(gz_file, "wt") as fh:
            fh.write("\n\n")
            fh.write(json.dumps(_make_candidate("CAND_001")) + "\n")
            fh.write("\n")

        parser = CandidateParser()
        result = list(parser.stream_candidates(gz_file))
        assert len(result) == 1

    def test_limit_parameter(self, tmp_path):
        records = [_make_candidate(f"CAND_{i:03d}") for i in range(50)]
        gz_file = str(tmp_path / "candidates.jsonl.gz")
        _write_jsonl_gz(records, gz_file)

        parser = CandidateParser()
        result = list(parser.stream_candidates(gz_file, limit=10))
        assert len(result) == 10

    def test_file_not_found_raises(self):
        parser = CandidateParser()
        with pytest.raises(FileNotFoundError):
            list(parser.stream_candidates("/nonexistent/path/file.jsonl.gz"))


# ===========================================================================
# HeuristicFilter — is_title_trap
# ===========================================================================

class TestIsTitleTrap:

    @pytest.mark.parametrize("title", [
        "Marketing Manager",
        "HR Manager",
        "Operations Manager",
        "Accountant",
        "Sales Representative",
        "Senior Accountant",
        "Head of Sales",
    ])
    def test_detects_non_technical_titles(self, title):
        candidate = _make_candidate(title=title)
        assert HeuristicFilter.is_title_trap(candidate) is True

    @pytest.mark.parametrize("title", [
        "Senior AI Engineer",
        "Machine Learning Engineer",
        "Data Scientist",
        "Software Engineer",
        "Backend Engineer",
        "ML Research Scientist",
    ])
    def test_passes_technical_titles(self, title):
        candidate = _make_candidate(title=title)
        assert HeuristicFilter.is_title_trap(candidate) is False

    def test_missing_profile_returns_false(self):
        candidate = {"candidate_id": "CAND_X"}
        assert HeuristicFilter.is_title_trap(candidate) is False

    def test_empty_title_returns_false(self):
        candidate = _make_candidate(title="")
        assert HeuristicFilter.is_title_trap(candidate) is False

    def test_case_insensitive(self):
        candidate = _make_candidate(title="MARKETING MANAGER")
        assert HeuristicFilter.is_title_trap(candidate) is True


# ===========================================================================
# HeuristicFilter — is_honeypot
# ===========================================================================

class TestIsHoneypot:

    def test_detects_expert_with_zero_months(self):
        candidate = _make_candidate(
            skills=[{"name": "Kubernetes", "proficiency": "expert", "duration_months": 0}]
        )
        assert HeuristicFilter.is_honeypot(candidate) is True

    def test_detects_advanced_with_zero_months(self):
        candidate = _make_candidate(
            skills=[{"name": "TensorFlow", "proficiency": "advanced", "duration_months": 0}]
        )
        assert HeuristicFilter.is_honeypot(candidate) is True

    def test_intermediate_zero_months_is_not_honeypot(self):
        candidate = _make_candidate(
            skills=[{"name": "Spark", "proficiency": "intermediate", "duration_months": 0}]
        )
        assert HeuristicFilter.is_honeypot(candidate) is False

    def test_expert_nonzero_months_is_clean(self):
        candidate = _make_candidate(
            skills=[{"name": "Python", "proficiency": "expert", "duration_months": 48}]
        )
        assert HeuristicFilter.is_honeypot(candidate) is False

    def test_no_skills_returns_false(self):
        candidate = _make_candidate(skills=[])
        assert HeuristicFilter.is_honeypot(candidate) is False

    def test_case_insensitive_proficiency(self):
        candidate = _make_candidate(
            skills=[{"name": "Go", "proficiency": "EXPERT", "duration_months": 0}]
        )
        assert HeuristicFilter.is_honeypot(candidate) is True


# ===========================================================================
# HeuristicFilter — get_base_penalty
# ===========================================================================

class TestGetBasePenalty:

    def test_honeypot_returns_zero(self):
        candidate = _make_candidate(
            skills=[{"name": "PyTorch", "proficiency": "expert", "duration_months": 0}]
        )
        assert HeuristicFilter.get_base_penalty(candidate) == 0.0

    def test_title_trap_returns_point_one(self):
        candidate = _make_candidate(title="Marketing Manager")
        assert HeuristicFilter.get_base_penalty(candidate) == 0.1

    def test_clean_returns_one(self):
        candidate = _make_candidate()
        assert HeuristicFilter.get_base_penalty(candidate) == 1.0

    def test_honeypot_takes_priority_over_title_trap(self):
        """Honeypot (0.0) must win over title trap (0.1)."""
        candidate = _make_candidate(
            title="Marketing Manager",
            skills=[{"name": "GPT-4", "proficiency": "expert", "duration_months": 0}],
        )
        assert HeuristicFilter.get_base_penalty(candidate) == 0.0


# ===========================================================================
# sort_and_format_submission
# ===========================================================================

class TestSortAndFormatSubmission:

    def _make_scored(self, candidate_id: str, score: float) -> dict[str, Any]:
        return {
            "candidate_id": candidate_id,
            "score": score,
            "reasoning": "test",
        }

    def test_primary_sort_by_score_descending(self):
        candidates = [
            self._make_scored("CAND_A", 0.5),
            self._make_scored("CAND_B", 0.9),
            self._make_scored("CAND_C", 0.7),
        ]
        result = sort_and_format_submission(candidates)
        scores = [r["score"] for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_tie_break_by_candidate_id_ascending(self):
        candidates = [
            self._make_scored("CAND_Z", 0.8),
            self._make_scored("CAND_A", 0.8),
            self._make_scored("CAND_M", 0.8),
        ]
        result = sort_and_format_submission(candidates)
        ids = [r["candidate_id"] for r in result]
        assert ids == ["CAND_A", "CAND_M", "CAND_Z"]

    def test_rank_starts_at_one(self):
        candidates = [self._make_scored(f"CAND_{i:03d}", 0.9 - i * 0.01) for i in range(5)]
        result = sort_and_format_submission(candidates)
        assert result[0]["rank"] == 1
        assert result[4]["rank"] == 5

    def test_returns_max_100_candidates(self):
        candidates = [self._make_scored(f"CAND_{i:04d}", float(i) / 200) for i in range(200)]
        result = sort_and_format_submission(candidates)
        assert len(result) == 100

    def test_raises_on_missing_candidate_id(self):
        with pytest.raises(ValueError, match="candidate_id"):
            sort_and_format_submission([{"score": 0.5, "reasoning": "x"}])

    def test_raises_on_missing_score(self):
        with pytest.raises(ValueError, match="score"):
            sort_and_format_submission([{"candidate_id": "CAND_1", "reasoning": "x"}])

    def test_empty_input_returns_empty(self):
        result = sort_and_format_submission([])
        assert result == []

    def test_fewer_than_100_returns_all(self):
        candidates = [self._make_scored(f"CAND_{i:03d}", 0.5) for i in range(30)]
        result = sort_and_format_submission(candidates)
        assert len(result) == 30


# ===========================================================================
# format_candidate_for_api
# ===========================================================================

class TestFormatCandidateForApi:

    def test_contains_all_required_api_fields(self):
        candidate = _make_candidate()
        candidate["rank"] = 1
        candidate["score"] = 0.95
        candidate["skill_match"] = 0.7
        candidate["semantic_match"] = 0.6
        candidate["status"] = "CLEAN"
        candidate["reasoning"] = "Strong AI background."
        candidate["analysis"] = {
            "why_selected": "Great fit.",
            "missing_skills": ["Spark"],
            "best_alternate_roles": ["Data Scientist"],
        }

        api_response = format_candidate_for_api(candidate)

        required_keys = [
            "rank", "candidate_id", "name", "overall_score",
            "skill_match", "semantic_match", "experience_years",
            "top_skills", "status", "reason",
            "resume_summary", "skills", "experience", "education",
            "projects", "certifications", "github", "linkedin",
            "why_selected", "missing_skills", "best_alternate_roles",
        ]
        for key in required_keys:
            assert key in api_response, f"Missing API field: {key!r}"

    def test_score_is_rounded_to_4dp(self):
        candidate = _make_candidate()
        candidate["rank"] = 1
        candidate["score"] = 0.123456789
        candidate["skill_match"] = 0.0
        candidate["semantic_match"] = 0.0
        candidate["status"] = "CLEAN"
        candidate["reasoning"] = ""

        api_response = format_candidate_for_api(candidate)
        assert api_response["overall_score"] == 0.1235
