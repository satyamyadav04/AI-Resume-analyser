"""
backend/embeddings.py — Local Semantic Feature Extractor
=========================================================
Provides CPU-optimised text embedding and cosine similarity utilities for the
RecruitAI hybrid scoring pipeline.

Architecture
------------
* Uses ``sentence-transformers`` with the lightweight ``all-MiniLM-L6-v2``
  model (80 MB, ~14k sentences/sec on a single CPU core) as the primary
  embedding backend.
* Falls back to a deterministic TF-IDF bag-of-words vectoriser (pure NumPy /
  stdlib) if ``sentence_transformers`` is unavailable, ensuring the pipeline
  always runs — even in an air-gapped hackathon environment.
* The embedding model is loaded **once** at class instantiation and reused for
  all subsequent calls (thread-safe read; write-once during ``__init__``).

Classes
-------
EmbeddingPipeline
    Stateful pipeline that owns the model and exposes high-level helpers.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any, Union

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Vector = Union[list[float], np.ndarray]

# ---------------------------------------------------------------------------
# Target role — used to seed the JD embedding and skill-gap analysis.
# ---------------------------------------------------------------------------
_TARGET_ROLE: str = (
    "Senior AI Engineer with expertise in machine learning, deep learning, "
    "NLP, computer vision, Python, PyTorch, TensorFlow, LLM, RAG, "
    "transformers, MLOps, Kubernetes, Docker, FastAPI, and data engineering."
)

# Skills that are genuinely relevant to a Senior AI Engineer role.
_RELEVANT_SKILLS: frozenset[str] = frozenset({
    "python", "pytorch", "tensorflow", "scikit-learn", "nlp",
    "computer vision", "kubernetes", "docker", "sql", "spark",
    "fastapi", "mlflow", "langchain", "cuda", "transformers",
    "huggingface", "rag", "llm", "feature engineering", "data engineering",
    "machine learning", "deep learning", "mlops", "ray", "triton",
})


class EmbeddingPipeline:
    """Semantic feature extractor and similarity calculator for RecruitAI.

    Attributes
    ----------
    model_name : str
        Name of the SentenceTransformer model in use.
    use_transformer : bool
        ``True`` if the heavy transformer model loaded successfully;
        ``False`` if the TF-IDF fallback is active.
    jd_vector : np.ndarray
        Pre-computed embedding of the target job description.  Shape
        ``(embedding_dim,)``.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name: str = model_name
        self.use_transformer: bool = False
        self._model: Any = None

        # ── Attempt to load sentence-transformers ──────────────────────────
        try:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415
            self._model = SentenceTransformer(model_name)
            self.use_transformer = True
            logger.info("EmbeddingPipeline: loaded '%s' transformer model.", model_name)
        except Exception as exc:  # ImportError or network/disk error
            logger.warning(
                "EmbeddingPipeline: sentence-transformers unavailable (%s). "
                "Falling back to TF-IDF bag-of-words vectoriser.",
                exc,
            )
            self._vocab: dict[str, int] = {}
            self._idf: np.ndarray = np.array([])

        # ── Pre-compute JD embedding ───────────────────────────────────────
        self.jd_vector: np.ndarray = self._embed(_TARGET_ROLE)
        logger.debug("EmbeddingPipeline: JD vector shape=%s", self.jd_vector.shape)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_features(self, candidate: dict[str, Any]) -> dict[str, Any]:
        """Extract a feature dict from a raw candidate record.

        The text block intentionally down-weights isolated keyword lists in
        favour of *contextualised* descriptions (summaries, job descriptions)
        to resist keyword-stuffing.  High-proficiency, long-duration skills
        receive more weight; honeypot skills (advanced + 0 months) are
        explicitly excluded.

        Parameters
        ----------
        candidate:
            Raw candidate dict as produced by
            :class:`~backend.parser.CandidateParser`.

        Returns
        -------
        dict[str, Any]
            ``{
                "text_block":        str,      # full text for embedding
                "embedding":         np.ndarray,
                "cosine_similarity": float,    # vs JD
                "skill_match":       float,    # 0.0 – 1.0 Jaccard-style
                "experience_years":  float,
                "top_skills":        list[str],
            }``
        """
        profile: dict[str, Any] = candidate.get("profile", {}) or {}
        skills: list[dict[str, Any]] = candidate.get("skills", []) or []
        experience: list[dict[str, Any]] = candidate.get("experience", []) or []

        # ── 1. Summary (high weight — contextualised prose) ──────────────
        summary: str = profile.get("summary", "") or ""

        # ── 2. Skills — contextualised, weighted, honeypots removed ──────
        skill_texts: list[str] = []
        clean_skill_names: list[str] = []
        for skill in skills:
            name: str = skill.get("name", "") or ""
            proficiency: str = (skill.get("proficiency", "") or "").lower()
            duration: int = skill.get("duration_months", 0) or 0
            # Exclude honeypot entries (advanced/expert + 0 months)
            if proficiency in {"expert", "advanced"} and duration == 0:
                logger.debug("extract_features: excluding honeypot skill '%s'", name)
                continue
            if name:
                # Repeat high-duration skills to increase their weight in the
                # TF-IDF bag without inflating the transformer embedding.
                repetitions = min(3, max(1, duration // 12))
                skill_texts.append(f"{name} " * repetitions)
                clean_skill_names.append(name)

        # ── 3. Recent career descriptions (up to 3 most recent jobs) ─────
        recent_jobs: list[str] = [
            exp.get("description", "") or ""
            for exp in experience[-3:]
            if exp.get("description")
        ]

        # ── Assemble text block ───────────────────────────────────────────
        # Summary is repeated to emphasise contextualised prose over keyword lists.
        text_block: str = " ".join(filter(None, [
            summary,
            summary,                       # ×2 weight on prose
            " ".join(skill_texts),
            " ".join(recent_jobs),
        ])).strip()

        if not text_block:
            text_block = candidate.get("name", "unknown candidate")

        # ── Compute embedding and cosine similarity ───────────────────────
        embedding: np.ndarray = self._embed(text_block)
        cosine_sim: float = self.compute_cosine_similarity(embedding, self.jd_vector)

        # ── Skill match: Jaccard between candidate skills and relevant set ─
        candidate_skill_set: frozenset[str] = frozenset(
            n.lower() for n in clean_skill_names
        )
        matched: int = len(candidate_skill_set & _RELEVANT_SKILLS)
        union: int = len(candidate_skill_set | _RELEVANT_SKILLS)
        skill_match: float = matched / union if union > 0 else 0.0

        # ── Top skills (by duration, descending) ─────────────────────────
        sorted_skills = sorted(
            [s for s in skills if (s.get("duration_months", 0) or 0) > 0],
            key=lambda s: s.get("duration_months", 0),
            reverse=True,
        )
        top_skills: list[str] = [s["name"] for s in sorted_skills[:5] if s.get("name")]

        experience_years: float = float(candidate.get("experience_years", 0.0) or 0.0)

        logger.debug(
            "extract_features: id=%s cosine=%.4f skill_match=%.4f",
            candidate.get("candidate_id", "?"),
            cosine_sim,
            skill_match,
        )

        return {
            "text_block": text_block,
            "embedding": embedding,
            "cosine_similarity": cosine_sim,
            "skill_match": skill_match,
            "experience_years": experience_years,
            "top_skills": top_skills,
        }

    @staticmethod
    def compute_cosine_similarity(vecA: Vector, vecB: Vector) -> float:
        """Return cosine similarity between two vectors, handling edge cases.

        Edge cases handled
        ------------------
        * Zero vector (all-zeros) for either input → returns ``0.0``.
        * Mismatched shapes → raises ``ValueError`` with a clear message.
        * NaN / Inf values in inputs → treated as zero-vectors.

        Parameters
        ----------
        vecA, vecB:
            1-D array-like objects of equal length.

        Returns
        -------
        float
            Similarity in ``[-1.0, 1.0]``.  Clipped to ``[0.0, 1.0]`` for
            downstream scoring (cosine can be negative for dissimilar texts).
        """
        a = np.asarray(vecA, dtype=np.float64).ravel()
        b = np.asarray(vecB, dtype=np.float64).ravel()

        # Sanitise NaN / Inf
        if not np.all(np.isfinite(a)):
            logger.warning("compute_cosine_similarity: vecA contains non-finite values; zeroing.")
            a = np.zeros_like(a)
        if not np.all(np.isfinite(b)):
            logger.warning("compute_cosine_similarity: vecB contains non-finite values; zeroing.")
            b = np.zeros_like(b)

        if a.shape != b.shape:
            raise ValueError(
                f"Shape mismatch in cosine similarity: "
                f"vecA={a.shape}, vecB={b.shape}"
            )

        norm_a: float = float(np.linalg.norm(a))
        norm_b: float = float(np.linalg.norm(b))

        if norm_a == 0.0 or norm_b == 0.0:
            logger.debug("compute_cosine_similarity: zero-vector detected; returning 0.0.")
            return 0.0

        similarity: float = float(np.dot(a, b) / (norm_a * norm_b))
        # Clip to [0, 1] — negative cosine means completely dissimilar text.
        return max(0.0, min(1.0, similarity))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _embed(self, text: str) -> np.ndarray:
        """Return a normalised 1-D embedding vector for *text*."""
        if self.use_transformer and self._model is not None:
            return self._embed_transformer(text)
        return self._embed_tfidf(text)

    def _embed_transformer(self, text: str) -> np.ndarray:
        """Encode *text* using the loaded SentenceTransformer model."""
        try:
            vec = self._model.encode(text, convert_to_numpy=True, show_progress_bar=False)
            return vec.astype(np.float64)
        except Exception as exc:
            logger.error("_embed_transformer failed (%s); returning zero vector.", exc)
            dim: int = self._model.get_sentence_embedding_dimension() or 384
            return np.zeros(dim, dtype=np.float64)

    def _embed_tfidf(self, text: str) -> np.ndarray:
        """Lightweight TF-IDF fallback embedding (no external dependencies).

        On first call, builds a vocabulary from the target JD tokens.
        Subsequent calls project *text* into the same space.
        """
        tokens: list[str] = self._tokenise(text)
        jd_tokens: list[str] = self._tokenise(_TARGET_ROLE)

        # Build or reuse vocabulary
        if not self._vocab:
            all_tokens: set[str] = set(jd_tokens) | set(tokens)
            self._vocab = {tok: i for i, tok in enumerate(sorted(all_tokens))}
            # Simple IDF: log(2 / (1 + df)) where df is approximate from JD
            jd_set = set(jd_tokens)
            self._idf = np.array([
                math.log(2.0 / (1 + (1 if tok in jd_set else 0)) + 1e-9)
                for tok in sorted(all_tokens)
            ], dtype=np.float64)

        # Build TF vector
        tf_vec: np.ndarray = np.zeros(len(self._vocab), dtype=np.float64)
        for token in tokens:
            if token in self._vocab:
                tf_vec[self._vocab[token]] += 1.0

        if tf_vec.sum() > 0:
            tf_vec /= tf_vec.sum()  # normalise TF

        # Apply IDF weights
        if len(self._idf) == len(tf_vec):
            tf_vec *= self._idf

        return tf_vec

    @staticmethod
    def _tokenise(text: str) -> list[str]:
        """Lower-case, strip punctuation, split on whitespace."""
        cleaned = re.sub(r"[^a-z0-9\s]", " ", text.lower())
        return [tok for tok in cleaned.split() if len(tok) > 1]
