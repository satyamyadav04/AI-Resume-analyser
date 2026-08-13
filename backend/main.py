"""
backend/main.py — End-to-End RecruitAI Orchestrator Pipeline
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np

# Configure logger early
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Pipeline constants
_FAISS_TOP_K: int = 500
_DEFAULT_JD_TEXT: str = "Senior AI Engineer with expertise in machine learning, NLP, LLM, RAG, Python, and MLOps."

def execute_pipeline(
    candidates_gzip_path: str,
    jd_path: Optional[str] = None,
    output_csv_path: str = "sample_submission.csv",
    *,
    faiss_top_k: int = _FAISS_TOP_K,
    limit: Optional[int] = None,
    run_validator: bool = True,
    log_level: str = "INFO",
) -> list[dict[str, Any]]:
    """Run the full RecruitAI scoring pipeline end-to-end."""
    
    # 1. Resolve paths to absolute to fix Cloud/Container issues
    abs_candidates_path = str(Path(candidates_gzip_path).resolve())
    abs_output_path = str(Path(output_csv_path).resolve())
    
    logger.info("=" * 70)
    logger.info("RecruitAI Pipeline — START")
    logger.info("  Absolute Candidates Path: %s", abs_candidates_path)
    logger.info("  Absolute Output Path:     %s", abs_output_path)
    logger.info("=" * 70)

    # 2. Verify file exists before proceeding
    if not os.path.exists(abs_candidates_path):
        error_msg = f"Candidate file not found at resolved path: {abs_candidates_path}"
        logger.critical(error_msg)
        raise FileNotFoundError(error_msg)

    # Lazy imports
    from backend.parser import CandidateParser
    from backend.embeddings import EmbeddingPipeline
    from backend.scoring import HeuristicFilter, ScoringEngine
    from backend.ranking import VectorRanker, sort_and_format_submission
    from backend.utils import ExplanationEngine

    # STEP 0: Load models
    pipeline = EmbeddingPipeline()
    engine = ScoringEngine(embedding_pipeline=pipeline)
    ranker = VectorRanker(embedding_dim=pipeline.jd_vector.shape[0])
    explainer = ExplanationEngine()

    jd_text = _load_jd(jd_path)
    jd_vector = pipeline._embed(jd_text).astype(np.float32)

    # STEP 1: Streaming ingestion
    parser = CandidateParser()
    candidate_store = []
    embedding_list = []
    
    logger.info("Starting ingestion from: %s", abs_candidates_path)
    for candidate in parser.stream_candidates(abs_candidates_path, limit=limit):
        if HeuristicFilter.is_honeypot(candidate):
            continue
        
        # Phase-2 feature extraction
        features = pipeline.extract_features(candidate)
        candidate["_features"] = features
        
        candidate_store.append(candidate)
        embedding_list.append(features["embedding"].astype(np.float32))

    if not candidate_store:
        raise RuntimeError("No valid candidates parsed from the file.")

    # STEP 2 & 3: Indexing and Scoring
    embedding_matrix = np.vstack(embedding_list)
    ranker.build_index(embedding_matrix)
    top_indices, faiss_scores = ranker.query_top_k(jd_vector, k=min(faiss_top_k, len(candidate_store)))

    # STEP 4: Hybrid Scoring
    scored = []
    for idx, faiss_sim in zip(top_indices.tolist(), faiss_scores.tolist()):
        candidate = candidate_store[idx]
        features = candidate.pop("_features")
        
        final_score = engine.compute_hybrid_score(
            semantic_similarity=float(faiss_sim),
            candidate=candidate,
            skill_match=float(features.get("skill_match", 0.0)),
            experience_years=float(features.get("experience_years", 0.0)),
        )
        
        status = (
            "HONEYPOT"
            if HeuristicFilter.is_honeypot(candidate)
            else ("TITLE_TRAP" if HeuristicFilter.is_title_trap(candidate) else "CLEAN")
        )

        candidate["score"] = final_score
        candidate["experience_years"] = float(features.get("experience_years", 0.0))
        candidate["skill_match"] = round(float(features.get("skill_match", 0.0)), 4)
        candidate["semantic_match"] = round(float(faiss_sim), 4)
        candidate["status"] = status
        candidate["reasoning"] = explainer.generate_reasoning(candidate, float(faiss_sim))
        candidate["analysis"] = engine._build_analysis(
            candidate=candidate,
            features={
                **features,
                "cosine_similarity": float(faiss_sim),
            },
            status=status,
        )
        
        scored.append(candidate)

    # STEP 5: Sort and Export
    top100 = sort_and_format_submission(scored)
    explainer.export_to_csv(top100, abs_output_path)
    
    if run_validator:
        _run_validator(abs_output_path)
        
    return top100

def _load_jd(jd_path: Optional[str]) -> str:
    if jd_path and os.path.exists(jd_path):
        with open(jd_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return _DEFAULT_JD_TEXT

def _run_validator(csv_path: str) -> None:
    # Use absolute path to the validator
    here = os.path.dirname(os.path.abspath(__file__))
    validator_path = os.path.join(os.path.dirname(here), "validate_submission.py")
    if os.path.exists(validator_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("validate", validator_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        errors = mod.validate(csv_path)
        if errors:
            logger.error("Validation failed: %s", errors)
        else:
            logger.info("Submission passed validation.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default="data/candidates.jsonl.gz")
    parser.add_argument("--output", default="sample_submission.csv")
    args = parser.parse_args()
    execute_pipeline(args.candidates, output_csv_path=args.output)

# """
# backend/main.py — End-to-End RecruitAI Orchestrator Pipeline
# =============================================================
# Single entry point that coordinates all three phases:

# Phase 1 — Streaming Ingestion
#     :class:`~backend.parser.CandidateParser` streams candidates one-by-one
#     from a ``.jsonl.gz`` file via a generator.  Zero full-list allocation.

# Phase 2 — Embedding Generation & Heuristic Filtering
#     :class:`~backend.embeddings.EmbeddingPipeline` extracts semantic feature
#     vectors.  :class:`~backend.scoring.HeuristicFilter` labels honeypots and
#     title traps immediately so they are skipped before FAISS indexing.

# Phase 3 — FAISS Indexing, Hybrid Scoring, Ranking & Export
#     :class:`~backend.ranking.VectorRanker` builds an ``IndexFlatIP`` over all
#     non-honeypot embeddings, queries the top-500 semantic matches, then
#     :class:`~backend.scoring.ScoringEngine` computes the full hybrid score
#     (semantic + skill + experience + availability modifier).
#     :func:`~backend.ranking.sort_and_format_submission` enforces the validator
#     sort contract, and :class:`~backend.utils.ExplanationEngine` writes a
#     templated reasoning string before the CSV is exported.

# Performance targets
# -------------------
# * 100 000 candidates in < 5 minutes on a single CPU core.
# * Peak RAM < 16 GB — streaming ingestion + pre-allocated NumPy matrix.

# Usage
# -----
# ::

#     from backend.main import execute_pipeline

#     execute_pipeline(
#         candidates_gzip_path="data/candidates.jsonl.gz",
#         jd_path="data/job_description.txt",       # plain text or .json
#         output_csv_path="data/sample_submission.csv",
#     )

# Or as a CLI:

#     python -m backend.main \\
#         --candidates data/candidates.jsonl.gz \\
#         --jd data/job_description.txt \\
#         --output data/sample_submission.csv
# """

# from __future__ import annotations

# import argparse
# import logging
# import os
# import sys
# import time
# from typing import Any, Optional

# import numpy as np

# logger = logging.getLogger(__name__)

# # ---------------------------------------------------------------------------
# # Pipeline constants
# # ---------------------------------------------------------------------------

# # Max semantic pre-candidates passed to the full hybrid scorer.
# _FAISS_TOP_K: int = 500

# # Default JD text used when no external jd_path is provided.
# _DEFAULT_JD_TEXT: str = (
#     "Senior AI Engineer with expertise in machine learning, deep learning, "
#     "NLP, computer vision, Python, PyTorch, TensorFlow, LLM, RAG, "
#     "transformers, MLOps, Kubernetes, Docker, FastAPI, and data engineering."
# )


# # ===========================================================================
# # Main pipeline function
# # ===========================================================================


# def execute_pipeline(
#     candidates_gzip_path: str,
#     jd_path: Optional[str] = None,
#     output_csv_path: str = "data/sample_submission.csv",
#     *,
#     faiss_top_k: int = _FAISS_TOP_K,
#     limit: Optional[int] = None,
#     run_validator: bool = True,
#     log_level: str = "INFO",
# ) -> list[dict[str, Any]]:
#     """Run the full RecruitAI scoring pipeline end-to-end.

#     Parameters
#     ----------
#     candidates_gzip_path:
#         Path to the ``.jsonl.gz`` candidate dataset.
#     jd_path:
#         Path to a plain-text or JSON job description file.  If ``None`` or
#         the file is missing, the built-in default JD string is used.
#     output_csv_path:
#         Destination for ``sample_submission.csv``.
#     faiss_top_k:
#         Number of semantic nearest neighbours to retrieve from the FAISS
#         index before full hybrid scoring.  Default 500.
#     limit:
#         If given, process only the first *limit* candidates (dev / testing).
#     run_validator:
#         Whether to invoke ``validate_submission.py`` after export.
#     log_level:
#         Python logging level string (``"DEBUG"``, ``"INFO"``, ``"WARNING"``).

#     Returns
#     -------
#     list[dict[str, Any]]
#         The final ranked top-100 candidates (as returned by
#         :func:`~backend.ranking.sort_and_format_submission`).

#     Raises
#     ------
#     FileNotFoundError
#         If *candidates_gzip_path* does not exist.
#     RuntimeError
#         If no valid (non-honeypot) candidates were found after ingestion.
#     """
#     _configure_logging(log_level)
#     t_start: float = time.perf_counter()

#     logger.info("=" * 70)
#     logger.info("RecruitAI Pipeline — START")
#     logger.info("  Candidates : %s", candidates_gzip_path)
#     logger.info("  JD path    : %s", jd_path or "<built-in default>")
#     logger.info("  Output     : %s", output_csv_path)
#     logger.info("=" * 70)

#     # ── Lazy imports (keep module load time low) ──────────────────────────
#     from backend.parser import CandidateParser
#     from backend.embeddings import EmbeddingPipeline
#     from backend.scoring import HeuristicFilter, ScoringEngine
#     from backend.ranking import VectorRanker, sort_and_format_submission
#     from backend.utils import ExplanationEngine

#     # =========================================================================
#     # STEP 0 — Load models and JD
#     # =========================================================================
#     try:
#         logger.info("Step 0/5 — Loading embedding model …")
#         pipeline = EmbeddingPipeline()
#         engine = ScoringEngine(embedding_pipeline=pipeline)
#         ranker = VectorRanker(embedding_dim=pipeline.jd_vector.shape[0])
#         explainer = ExplanationEngine()

#         jd_text: str = _load_jd(jd_path)
#         jd_vector: np.ndarray = pipeline._embed(jd_text).astype(np.float32)
#         logger.info("  JD vector shape: %s", jd_vector.shape)

#     except Exception as exc:
#         logger.exception("Step 0 failed during model/JD loading.")
#         raise

#     # =========================================================================
#     # STEP 1 — Streaming ingestion + embedding extraction (Phase 1 & 2)
#     # =========================================================================
#     logger.info("Step 1/5 — Streaming ingestion + embedding extraction …")

#     parser = CandidateParser()
#     candidate_store: list[dict[str, Any]] = []   # non-honeypot candidates
#     embedding_list: list[np.ndarray] = []        # parallel to candidate_store
#     honeypot_count: int = 0
#     trap_count: int = 0

#     try:
#         for candidate in parser.stream_candidates(candidates_gzip_path, limit=limit):
#             # ── Phase-1 trap check ────────────────────────────────────────
#             if HeuristicFilter.is_honeypot(candidate):
#                 candidate["score"] = 0.0
#                 candidate["status"] = "HONEYPOT"
#                 candidate["reasoning"] = (
#                     "Disqualified: expert/advanced proficiency with 0 months experience."
#                 )
#                 honeypot_count += 1
#                 continue   # honeypots never enter the FAISS index

#             is_trap = HeuristicFilter.is_title_trap(candidate)
#             if is_trap:
#                 trap_count += 1

#             # ── Phase-2 embedding extraction ──────────────────────────────
#             features: dict[str, Any] = pipeline.extract_features(candidate)

#             # Attach features to candidate for later use in scoring.
#             candidate["_features"] = features

#             candidate_store.append(candidate)
#             embedding_list.append(
#                 features["embedding"].astype(np.float32)
#             )

#     except FileNotFoundError:
#         logger.error("Candidates file not found: %s", candidates_gzip_path)
#         raise

#     total_valid = len(candidate_store)
#     logger.info(
#         "  Ingested: %d valid | %d honeypots skipped | %d title-traps flagged",
#         total_valid, honeypot_count, trap_count,
#     )
#     logger.info("  Parser stats: %s", parser.stats)

#     if total_valid == 0:
#         raise RuntimeError(
#             "No valid candidates found — check dataset path and format."
#         )

#     # =========================================================================
#     # STEP 2 — Build FAISS index (Phase 3)
#     # =========================================================================
#     logger.info("Step 2/5 — Building FAISS index over %d embeddings …", total_valid)

#     try:
#         embedding_matrix: np.ndarray = np.vstack(embedding_list)   # (N, D)
#         del embedding_list   # free ~N×D×4 bytes immediately
#         ranker.build_index(embedding_matrix)
#         logger.info("  Index built: %d vectors, dim=%d", ranker.n_indexed, ranker.embedding_dim)
#     except Exception as exc:
#         logger.exception("Step 2 failed during FAISS index construction.")
#         raise

#     # =========================================================================
#     # STEP 3 — Query top-K semantic candidates (Phase 3)
#     # =========================================================================
#     effective_k = min(faiss_top_k, total_valid)
#     logger.info("Step 3/5 — Querying top-%d semantic matches …", effective_k)

#     try:
#         top_indices, faiss_scores = ranker.query_top_k(jd_vector, k=effective_k)
#         logger.info(
#             "  Top-1 score=%.4f | Top-%d score=%.4f",
#             float(faiss_scores[0]),
#             effective_k,
#             float(faiss_scores[-1]),
#         )
#     except Exception as exc:
#         logger.exception("Step 3 failed during FAISS query.")
#         raise

#     # =========================================================================
#     # STEP 4 — Hybrid scoring on top-K candidates (Phase 2 + Phase 3)
#     # =========================================================================
#     logger.info("Step 4/5 — Hybrid scoring %d candidates …", effective_k)
#     scored: list[dict[str, Any]] = []

#     for pos, (idx, faiss_sim) in enumerate(
#         zip(top_indices.tolist(), faiss_scores.tolist())
#     ):
#         candidate = candidate_store[idx]
#         features = candidate.pop("_features", {})   # remove temp key

#         try:
#             # Prefer the FAISS-computed cosine similarity over the pipeline's
#             # own value (they are equal when both normalise, but FAISS is exact).
#             final_score: float = engine.compute_hybrid_score(
#                 semantic_similarity=float(faiss_sim),
#                 candidate=candidate,
#                 skill_match=float(features.get("skill_match", 0.0)),
#                 experience_years=float(features.get("experience_years", 0.0)),
#             )

#             # Determine status.
#             from backend.scoring import HeuristicFilter as _HF
#             if _HF.is_honeypot(candidate):
#                 status = "HONEYPOT"
#             elif _HF.is_title_trap(candidate):
#                 status = "TITLE_TRAP"
#             else:
#                 status = "CLEAN"

#             # Generate reasoning via ExplanationEngine (template, no API call).
#             reasoning: str = explainer.generate_reasoning(
#                 candidate=candidate,
#                 semantic_score=float(faiss_sim),
#             )

#             candidate.update({
#                 "score": final_score,
#                 "skill_match": round(float(features.get("skill_match", 0.0)), 4),
#                 "semantic_match": round(float(faiss_sim), 4),
#                 "status": status,
#                 "reasoning": reasoning,
#                 "analysis": {
#                     "why_selected": (
#                         f"Semantic alignment {faiss_sim:.2%} with Senior AI Engineer role."
#                         if status == "CLEAN"
#                         else "Penalised — see reasoning."
#                     ),
#                     "missing_skills": [],
#                     "best_alternate_roles": [],
#                 },
#             })
#             scored.append(candidate)

#         except Exception as exc:
#             logger.warning(
#                 "Scoring failed for candidate %s (pos=%d): %s — skipping.",
#                 candidate.get("candidate_id", "?"), pos, exc,
#             )
#             continue

#     logger.info("  Scored %d / %d candidates successfully.", len(scored), effective_k)

#     # =========================================================================
#     # STEP 5 — Sort, rank, and export (Phase 1 + Phase 3)
#     # =========================================================================
#     logger.info("Step 5/5 — Sorting, ranking, and exporting …")

#     try:
#         top100: list[dict[str, Any]] = sort_and_format_submission(scored)
#         logger.info(
#             "  Top-100 selected | #1: %s (%.4f) | #100: %s (%.4f)",
#             top100[0]["candidate_id"],
#             top100[0]["score"],
#             top100[-1]["candidate_id"],
#             top100[-1]["score"],
#         )

#         # ── Export minimal submission CSV via ExplanationEngine ───────────
#         explainer.export_to_csv(top100, output_csv_path)
#         logger.info("  Submission CSV written: %s", output_csv_path)

#     except Exception as exc:
#         logger.exception("Step 5 failed during sort/rank/export.")
#         raise

#     # =========================================================================
#     # STEP 6 — Self-validate the submission file
#     # =========================================================================
#     if run_validator:
#         _run_validator(output_csv_path)

#     elapsed: float = time.perf_counter() - t_start
#     logger.info("=" * 70)
#     logger.info(
#         "Pipeline COMPLETE — %d candidates processed in %.1f s (%.0f candidates/s)",
#         total_valid + honeypot_count,
#         elapsed,
#         (total_valid + honeypot_count) / elapsed,
#     )
#     logger.info("=" * 70)

#     return top100


# # ===========================================================================
# # Private helpers
# # ===========================================================================


# def _load_jd(jd_path: Optional[str]) -> str:
#     """Return JD text from *jd_path*, or fall back to the built-in default."""
#     if jd_path and os.path.exists(jd_path):
#         try:
#             with open(jd_path, encoding="utf-8") as fh:
#                 text = fh.read().strip()
#             if text:
#                 logger.info("_load_jd: loaded JD from '%s' (%d chars).", jd_path, len(text))
#                 return text
#         except OSError as exc:
#             logger.warning("_load_jd: could not read '%s' (%s); using default.", jd_path, exc)
#     else:
#         if jd_path:
#             logger.warning("_load_jd: '%s' not found; using built-in default JD.", jd_path)
#     return _DEFAULT_JD_TEXT


# def _run_validator(csv_path: str) -> None:
#     """Invoke validate_submission.py as an in-process check."""
#     # Resolve path relative to the project root (parent of backend/).
#     here = os.path.dirname(os.path.abspath(__file__))
#     project_root = os.path.dirname(here)
#     validator_path = os.path.join(project_root, "validate_submission.py")

#     if not os.path.exists(validator_path):
#         logger.warning(
#             "_run_validator: validate_submission.py not found at '%s'; skipping.",
#             validator_path,
#         )
#         return

#     try:
#         import importlib.util  # noqa: PLC0415
#         spec = importlib.util.spec_from_file_location(
#             "validate_submission", validator_path
#         )
#         if spec is None or spec.loader is None:
#             raise ImportError("Could not load validate_submission module.")

#         mod = importlib.util.module_from_spec(spec)
#         spec.loader.exec_module(mod)  # type: ignore[union-attr]

#         errors: list[str] = mod.validate(csv_path)  # type: ignore[attr-defined]
#         if errors:
#             logger.error(
#                 "_run_validator: %d validation error(s) in '%s':",
#                 len(errors), csv_path,
#             )
#             for err in errors:
#                 logger.error("  • %s", err)
#         else:
#             logger.info(
#                 "_run_validator: ✅ Submission '%s' passed all validation checks.",
#                 csv_path,
#             )
#     except Exception as exc:
#         logger.warning("_run_validator: error during validation (%s); skipping.", exc)


# def _configure_logging(level: str = "INFO") -> None:
#     """Configure root logger if no handlers are attached yet."""
#     root = logging.getLogger()
#     if root.handlers:
#         return   # already configured by caller

#     handler = logging.StreamHandler(sys.stdout)
#     handler.setFormatter(
#         logging.Formatter(
#             fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
#             datefmt="%H:%M:%S",
#         )
#     )
#     root.addHandler(handler)
#     root.setLevel(getattr(logging, level.upper(), logging.INFO))


# # ===========================================================================
# # CLI entry point
# # ===========================================================================


# def _parse_args() -> argparse.Namespace:
#     p = argparse.ArgumentParser(
#         description="RecruitAI — Phase 3 End-to-End Pipeline",
#         formatter_class=argparse.ArgumentDefaultsHelpFormatter,
#     )
#     p.add_argument(
#         "--candidates",
#         default="data/candidates.jsonl.gz",
#         metavar="PATH",
#         help="Path to the gzip-compressed JSONL candidate file.",
#     )
#     p.add_argument(
#         "--jd",
#         default=None,
#         metavar="PATH",
#         help="Path to the job description text file (optional).",
#     )
#     p.add_argument(
#         "--output",
#         default="data/sample_submission.csv",
#         metavar="PATH",
#         help="Output path for sample_submission.csv.",
#     )
#     p.add_argument(
#         "--top-k",
#         type=int,
#         default=_FAISS_TOP_K,
#         metavar="K",
#         help="FAISS pre-selection top-K (default 500).",
#     )
#     p.add_argument(
#         "--limit",
#         type=int,
#         default=None,
#         metavar="N",
#         help="Process only first N candidates (dev/testing).",
#     )
#     p.add_argument(
#         "--no-validate",
#         action="store_true",
#         help="Skip the post-export validation step.",
#     )
#     p.add_argument(
#         "--log-level",
#         default="INFO",
#         choices=["DEBUG", "INFO", "WARNING", "ERROR"],
#         help="Logging verbosity.",
#     )
#     return p.parse_args()


# if __name__ == "__main__":
#     args = _parse_args()
#     try:
#         execute_pipeline(
#             candidates_gzip_path=args.candidates,
#             jd_path=args.jd,
#             output_csv_path=args.output,
#             faiss_top_k=args.top_k,
#             limit=args.limit,
#             run_validator=not args.no_validate,
#             log_level=args.log_level,
#         )
#     except Exception as exc:
#         logger.critical("Pipeline aborted: %s", exc)
#         sys.exit(1)
