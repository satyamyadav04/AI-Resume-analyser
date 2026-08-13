"""
backend/parser.py — Memory-Safe Data Ingestion
===============================================
Streams candidates one-by-one from a ``.jsonl.gz`` file without loading the
entire dataset into memory.  Designed to handle 100 000+ records within the
16 GB RAM constraint.

Classes
-------
CandidateParser
    Stateful parser that tracks read/skipped counts via ``stats``.
"""

from __future__ import annotations

import gzip
import json
import logging
from pathlib import Path
from typing import Any, Generator, Optional

logger = logging.getLogger(__name__)


class CandidateParser:
    """Stream candidates from a JSONL or gzip-compressed JSONL file.

    The parser is intentionally dependency-free (stdlib only) to keep the
    memory footprint minimal.  Each line is decoded, validated, and yielded
    individually so the garbage collector can reclaim memory between records.

    Attributes
    ----------
    stats : dict[str, int]
        Counters updated during streaming:
        - ``total_read``    – number of successfully parsed candidates.
        - ``total_skipped`` – number of lines silently dropped.
    """

    _REQUIRED_FIELDS: frozenset[str] = frozenset({"candidate_id"})

    def __init__(self) -> None:
        self.stats: dict[str, int] = {
            "total_read": 0,
            "total_skipped": 0,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def stream_candidates(
        self,
        filepath: str,
        limit: Optional[int] = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Yield valid candidate dicts from *filepath* one at a time.

        Parameters
        ----------
        filepath:
            Absolute or relative path to a ``.jsonl`` or ``.jsonl.gz`` file.
        limit:
            If given, stop after yielding *limit* candidates.  Useful for
            smoke-testing without iterating the full dataset.

        Yields
        ------
        dict[str, Any]
            A single candidate record whose ``candidate_id`` field is present.

        Raises
        ------
        FileNotFoundError
            Re-raised immediately if *filepath* does not exist so callers can
            detect bad configuration early.
        """
        # Reset stats for each new streaming session.
        self.stats["total_read"] = 0
        self.stats["total_skipped"] = 0

        yielded = 0

        try:
            path = Path(filepath)
            if path.suffix.lower() == ".gz":
                fh = gzip.open(path, "rt", encoding="utf-8")
            else:
                fh = path.open("rt", encoding="utf-8")
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise FileNotFoundError(
                f"Cannot open '{filepath}': {exc}"
            ) from exc

        with fh:
            for raw_line in fh:
                # ── Early-exit if limit reached ────────────────────────
                if limit is not None and yielded >= limit:
                    break

                # ── Skip blank / whitespace-only lines ─────────────────
                line = raw_line.strip()
                if not line:
                    continue

                # ── Parse JSON ─────────────────────────────────────────
                try:
                    record: dict[str, Any] = json.loads(line)
                except json.JSONDecodeError:
                    self.stats["total_skipped"] += 1
                    logger.debug("Skipped malformed JSON line.")
                    continue

                # ── Validate required fields ───────────────────────────
                if not isinstance(record, dict):
                    self.stats["total_skipped"] += 1
                    continue

                if not self._REQUIRED_FIELDS.issubset(record.keys()):
                    self.stats["total_skipped"] += 1
                    logger.debug(
                        "Skipped record missing required fields: %s",
                        self._REQUIRED_FIELDS - record.keys(),
                    )
                    continue

                # ── Yield valid record ─────────────────────────────────
                self.stats["total_read"] += 1
                yielded += 1
                yield record
