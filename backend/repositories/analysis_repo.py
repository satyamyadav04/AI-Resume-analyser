"""
backend/repositories/analysis_repo.py — Analysis Results CRUD + Analytics Queries
PostgreSQL compatible version.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from backend.database.db import get_db


def _row_to_dict(cur, row) -> Optional[dict[str, Any]]:
    """Convert a PostgreSQL row tuple into a dictionary."""
    if not row:
        return None

    columns = [desc[0] for desc in cur.description]
    return dict(zip(columns, row))


def save_analysis(
    candidate_db_id: int,
    jd_id: int,
    scores: dict[str, Any],
) -> int:
    """Save analysis result. Returns analysis_id."""

    missing_skills = json.dumps(scores.get("missing_skills", []))
    strengths = json.dumps(scores.get("strengths", []))
    weaknesses = json.dumps(scores.get("weaknesses", []))

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO analysis_results
                (
                    candidate_id,
                    jd_id,
                    overall_score,
                    skill_match,
                    semantic_match,
                    experience_score,
                    education_score,
                    project_score,
                    ai_summary,
                    recommendation,
                    reasoning,
                    strengths,
                    weaknesses,
                    missing_skills,
                    status,
                    rank_position
                )
                VALUES
                (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    candidate_db_id,
                    jd_id,
                    scores.get("overall_score", 0.0),
                    scores.get("skill_match", 0.0),
                    scores.get("semantic_match", 0.0),
                    scores.get("experience_score", 0.0),
                    scores.get("education_score", 0.0),
                    scores.get("project_score", 0.0),
                    scores.get("ai_summary", ""),
                    scores.get("recommendation", ""),
                    scores.get("reasoning", ""),
                    strengths,
                    weaknesses,
                    missing_skills,
                    scores.get("status", "CLEAN"),
                    scores.get("rank_position", 0),
                ),
            )

            row = cur.fetchone()
            return int(row[0])


# ---------------------------------------------------------------------------
# Analytics Queries
# ---------------------------------------------------------------------------


def get_kpi_counts(
    company_id: int,
    jd_id: Optional[int] = None,
) -> dict[str, Any]:
    """Return KPI counts for the dashboard."""

    params: list[Any] = [company_id]

    jd_filter = ""

    if jd_id is not None:
        jd_filter = "AND c.jd_id = %s"
        params.append(jd_id)

    with get_db() as db:
        with db.cursor() as cur:

            # Total resumes
            cur.execute(
                f"""
                SELECT COUNT(*)
                FROM candidates c
                WHERE c.company_id = %s
                {jd_filter}
                """,
                params,
            )
            total_resumes = cur.fetchone()[0]

            # Today's uploads
            cur.execute(
                f"""
                SELECT COUNT(*)
                FROM candidates c
                WHERE c.company_id = %s
                {jd_filter}
                AND c.created_at::date = CURRENT_DATE
                """,
                params,
            )
            today_uploads = cur.fetchone()[0]

            # Analyses completed
            cur.execute(
                f"""
                SELECT COUNT(*)
                FROM candidates c
                JOIN analysis_results ar
                    ON ar.candidate_id = c.id
                WHERE c.company_id = %s
                {jd_filter}
                """,
                params,
            )
            analyzed = cur.fetchone()[0]

            # Average score
            cur.execute(
                f"""
                SELECT AVG(ar.overall_score)
                FROM candidates c
                JOIN analysis_results ar
                    ON ar.candidate_id = c.id
                WHERE c.company_id = %s
                {jd_filter}
                """,
                params,
            )
            avg_score_row = cur.fetchone()
            avg_score = float(avg_score_row[0] or 0.0)

            # Best candidate
            cur.execute(
                f"""
                SELECT c.name, ar.overall_score
                FROM candidates c
                JOIN analysis_results ar
                    ON ar.candidate_id = c.id
                WHERE c.company_id = %s
                {jd_filter}
                ORDER BY ar.overall_score DESC
                LIMIT 1
                """,
                params,
            )

            best_row = cur.fetchone()

            best_name = best_row[0] if best_row else "—"
            best_score = float(best_row[1]) if best_row else 0.0

            # Shortlisted candidates
            cur.execute(
                f"""
                SELECT COUNT(*)
                FROM candidates c
                WHERE c.company_id = %s
                {jd_filter}
                AND c.pipeline_stage = 'SHORTLISTED'
                """,
                params,
            )
            shortlisted_count = cur.fetchone()[0]

    return {
        "total_resumes": total_resumes,
        "today_uploads": today_uploads,
        "analyses_completed": analyzed,
        "avg_score": avg_score,
        "best_candidate_name": best_name,
        "best_score": best_score,
        "shortlisted_count": shortlisted_count,
    }


def get_score_distribution(
    company_id: int,
    jd_id: Optional[int] = None,
) -> dict[str, Any]:
    """Return score distribution bucketed into 5 ranges."""

    params: list[Any] = [company_id]

    jd_filter = ""

    if jd_id is not None:
        jd_filter = "AND c.jd_id = %s"
        params.append(jd_id)

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                f"""
                SELECT ar.overall_score
                FROM candidates c
                JOIN analysis_results ar
                    ON ar.candidate_id = c.id
                WHERE c.company_id = %s
                {jd_filter}
                """,
                params,
            )

            rows = cur.fetchall()

    buckets = {
        "0–20": 0,
        "21–40": 0,
        "41–60": 0,
        "61–80": 0,
        "81–100": 0,
    }

    for row in rows:
        score = float(row[0] or 0) * 100

        if score <= 20:
            buckets["0–20"] += 1
        elif score <= 40:
            buckets["21–40"] += 1
        elif score <= 60:
            buckets["41–60"] += 1
        elif score <= 80:
            buckets["61–80"] += 1
        else:
            buckets["81–100"] += 1

    return {
        "buckets": list(buckets.keys()),
        "counts": list(buckets.values()),
    }


def get_skills_frequency(
    company_id: int,
    jd_id: Optional[int] = None,
    top_n: int = 10,
) -> dict[str, Any]:
    """Return most common skills across all candidates."""

    params: list[Any] = [company_id]

    jd_filter = ""

    if jd_id is not None:
        jd_filter = "AND c.jd_id = %s"
        params.append(jd_id)

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    MIN(cs.name) AS name,
                    COUNT(*) AS freq
                FROM candidate_skills cs
                JOIN candidates c
                    ON cs.candidate_id = c.id
                WHERE c.company_id = %s
                {jd_filter}
                GROUP BY LOWER(cs.name)
                ORDER BY freq DESC
                LIMIT %s
                """,
                params + [top_n],
            )

            rows = cur.fetchall()

    skills = [r[0] for r in rows]
    counts = [r[1] for r in rows]

    return {
        "skills": skills,
        "coverage": counts,
    }


def get_missing_skills_frequency(
    company_id: int,
    jd_id: Optional[int] = None,
    top_n: int = 8,
) -> dict[str, Any]:
    """Return most commonly missing skills from analysis results."""

    params: list[Any] = [company_id]

    jd_filter = ""

    if jd_id is not None:
        jd_filter = "AND c.jd_id = %s"
        params.append(jd_id)

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                f"""
                SELECT ar.missing_skills
                FROM candidates c
                JOIN analysis_results ar
                    ON ar.candidate_id = c.id
                WHERE c.company_id = %s
                {jd_filter}
                AND ar.missing_skills IS NOT NULL
                AND ar.missing_skills != '[]'
                """,
                params,
            )

            rows = cur.fetchall()

    skill_counter: dict[str, int] = {}

    for row in rows:
        try:
            raw = row[0]

            if isinstance(raw, str):
                skills = json.loads(raw)
            else:
                skills = raw

            if isinstance(skills, list):
                for skill in skills:
                    if isinstance(skill, str):
                        skill_counter[skill] = (
                            skill_counter.get(skill, 0) + 1
                        )

        except (json.JSONDecodeError, TypeError):
            pass

    sorted_skills = sorted(
        skill_counter.items(),
        key=lambda x: x[1],
        reverse=True,
    )[:top_n]

    return {
        "skills": [s[0] for s in sorted_skills],
        "counts": [s[1] for s in sorted_skills],
    }


def get_experience_distribution(
    company_id: int,
    jd_id: Optional[int] = None,
) -> dict[str, Any]:
    """Return experience bucketed into ranges."""

    params: list[Any] = [company_id]

    jd_filter = ""

    if jd_id is not None:
        jd_filter = "AND c.jd_id = %s"
        params.append(jd_id)

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                f"""
                SELECT c.experience_years
                FROM candidates c
                WHERE c.company_id = %s
                {jd_filter}
                """,
                params,
            )

            rows = cur.fetchall()

    buckets = {
        "0–1 yrs": 0,
        "1–3 yrs": 0,
        "3–5 yrs": 0,
        "5–8 yrs": 0,
        "8+ yrs": 0,
    }

    for row in rows:
        yrs = float(row[0] or 0)

        if yrs <= 1:
            buckets["0–1 yrs"] += 1
        elif yrs <= 3:
            buckets["1–3 yrs"] += 1
        elif yrs <= 5:
            buckets["3–5 yrs"] += 1
        elif yrs <= 8:
            buckets["5–8 yrs"] += 1
        else:
            buckets["8+ yrs"] += 1

    return {
        "labels": list(buckets.keys()),
        "counts": list(buckets.values()),
    }


def get_education_breakdown(
    company_id: int,
    jd_id: Optional[int] = None,
) -> dict[str, Any]:
    """Return education level distribution."""

    params: list[Any] = [company_id]

    jd_filter = ""

    if jd_id is not None:
        jd_filter = "AND c.jd_id = %s"
        params.append(jd_id)

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                f"""
                SELECT ce.degree
                FROM candidate_education ce
                JOIN candidates c
                    ON ce.candidate_id = c.id
                WHERE c.company_id = %s
                {jd_filter}
                """,
                params,
            )

            rows = cur.fetchall()

    cats = {
        "B.Tech / B.E": 0,
        "M.Tech / M.S": 0,
        "B.Sc / BCA": 0,
        "MBA": 0,
        "Other": 0,
    }

    for row in rows:
        deg = (row[0] or "").lower()

        if any(
            k in deg
            for k in [
                "b.tech",
                "btech",
                "be ",
                "b.e.",
                "bachelor",
            ]
        ):
            cats["B.Tech / B.E"] += 1

        elif any(
            k in deg
            for k in [
                "m.tech",
                "mtech",
                "m.s",
                "master",
                "msc",
            ]
        ):
            cats["M.Tech / M.S"] += 1

        elif any(
            k in deg
            for k in [
                "b.sc",
                "bsc",
                "bca",
                "mca",
            ]
        ):
            cats["B.Sc / BCA"] += 1

        elif "mba" in deg:
            cats["MBA"] += 1

        else:
            cats["Other"] += 1

    return {
        "labels": list(cats.keys()),
        "counts": list(cats.values()),
    }


def get_pipeline_funnel(
    company_id: int,
    jd_id: Optional[int] = None,
) -> dict[str, Any]:
    """Return candidate counts per pipeline stage."""

    params: list[Any] = [company_id]

    jd_filter = ""

    if jd_id is not None:
        jd_filter = "AND jd_id = %s"
        params.append(jd_id)

    from backend.repositories.candidate_repo import PIPELINE_STAGES

    with get_db() as db:
        with db.cursor() as cur:
            cur.execute(
                f"""
                SELECT pipeline_stage, COUNT(*) AS cnt
                FROM candidates
                WHERE company_id = %s
                {jd_filter}
                GROUP BY pipeline_stage
                """,
                params,
            )

            rows = cur.fetchall()

    stage_counts = {
        r[0]: r[1]
        for r in rows
    }

    return {
        "stages": PIPELINE_STAGES,
        "counts": [
            stage_counts.get(stage, 0)
            for stage in PIPELINE_STAGES
        ],
    }