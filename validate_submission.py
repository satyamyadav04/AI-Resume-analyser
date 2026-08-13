"""
validate_submission.py — Self-test validator for sample_submission.csv
=======================================================================
Run automatically at the end of ``execute_pipeline()`` or standalone:

    python validate_submission.py --csv data/sample_submission.csv

Exit codes
----------
0   All checks passed.
1   One or more validation errors found (details printed to stderr).
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# Minimum required columns in the submission CSV.
_REQUIRED_COLUMNS: set[str] = {"candidate_id", "rank", "score", "reasoning"}

# Acceptable score range.
_SCORE_MIN: float = 0.0
_SCORE_MAX: float = 1.0


def validate(csv_path: str) -> list[str]:
    """Return a list of validation error strings (empty list = all OK)."""
    errors: list[str] = []
    path = Path(csv_path)

    # ── File existence ────────────────────────────────────────────────────
    if not path.exists():
        return [f"File not found: {csv_path}"]

    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return ["CSV file is empty or has no header row."]

        # ── Column presence ───────────────────────────────────────────────
        missing_cols = _REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing_cols:
            errors.append(f"Missing required columns: {sorted(missing_cols)}")

        rows: list[dict] = list(reader)

    # ── Row count ─────────────────────────────────────────────────────────
    if len(rows) == 0:
        errors.append("CSV has a header but no data rows.")
        return errors

    if len(rows) > 100:
        errors.append(
            f"Submission must contain ≤ 100 candidates; found {len(rows)}."
        )

    # ── Per-row checks ────────────────────────────────────────────────────
    seen_ids: set[str] = set()
    seen_ranks: set[int] = set()
    prev_score: float = float("inf")
    prev_id: str = ""

    for i, row in enumerate(rows, start=1):
        cid: str = row.get("candidate_id", "").strip()
        rank_raw: str = row.get("rank", "").strip()
        score_raw: str = row.get("score", "").strip()

        # candidate_id
        if not cid:
            errors.append(f"Row {i}: empty candidate_id.")
        elif cid in seen_ids:
            errors.append(f"Row {i}: duplicate candidate_id '{cid}'.")
        else:
            seen_ids.add(cid)

        # rank
        try:
            rank_val: int = int(rank_raw)
        except ValueError:
            errors.append(f"Row {i}: non-integer rank '{rank_raw}'.")
            rank_val = -1
        else:
            if rank_val != i:
                errors.append(
                    f"Row {i}: expected rank={i}, got rank={rank_val}."
                )
            if rank_val in seen_ranks:
                errors.append(f"Row {i}: duplicate rank {rank_val}.")
            seen_ranks.add(rank_val)

        # score
        try:
            score_val: float = float(score_raw)
        except ValueError:
            errors.append(f"Row {i}: non-numeric score '{score_raw}'.")
            score_val = -1.0
        else:
            if not (_SCORE_MIN <= score_val <= _SCORE_MAX):
                errors.append(
                    f"Row {i}: score {score_val} out of range [{_SCORE_MIN}, {_SCORE_MAX}]."
                )
            # ── Sort order check (score desc, then id asc on tie) ─────────
            if score_val > prev_score + 1e-9:
                errors.append(
                    f"Row {i}: score {score_val:.4f} > previous {prev_score:.4f} "
                    f"— primary sort (score desc) violated."
                )
            elif abs(score_val - prev_score) < 1e-9 and cid < prev_id:
                errors.append(
                    f"Row {i}: tied score {score_val:.4f} but candidate_id "
                    f"'{cid}' < previous '{prev_id}' — tie-breaker (id asc) violated."
                )
            prev_score = score_val
            prev_id = cid

        # reasoning
        reasoning: str = row.get("reasoning", "").strip()
        if not reasoning:
            errors.append(f"Row {i}: empty reasoning field for '{cid}'.")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a RecruitAI sample_submission.csv."
    )
    parser.add_argument(
        "--csv",
        default="data/sample_submission.csv",
        help="Path to the submission CSV file.",
    )
    args = parser.parse_args()

    errors = validate(args.csv)
    if errors:
        print(f"❌  Validation FAILED — {len(errors)} error(s):", file=sys.stderr)
        for err in errors:
            print(f"   • {err}", file=sys.stderr)
        return 1

    print(f"✅  Validation PASSED — submission '{args.csv}' is valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
