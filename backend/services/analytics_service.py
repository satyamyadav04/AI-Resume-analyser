"""
backend/services/analytics_service.py — Analytics Aggregations for Charts & Dashboard
"""
from __future__ import annotations

from typing import Any, Optional

from backend.repositories import analysis_repo


def get_dashboard_kpis(company_id: int, jd_id: Optional[int] = None) -> dict[str, Any]:
    """Return live KPI data for the dashboard metric cards."""
    kpis = analysis_repo.get_kpi_counts(company_id, jd_id)

    best_score_pct = int(kpis["best_score"] * 100)
    avg_score_pct = round(kpis["avg_score"] * 100, 1)

    return {
        "resumes_uploaded": {
            "value": str(kpis["total_resumes"]),
            "delta": f"{kpis['today_uploads']} today",
            "up": kpis["today_uploads"] > 0,
        },
        "analyses_completed": {
            "value": str(kpis["analyses_completed"]),
            "delta": f"{kpis['shortlisted_count']} shortlisted",
            "up": kpis["analyses_completed"] > 0,
        },
        "best_score": {
            "value": f"{best_score_pct}%",
            "delta": kpis["best_candidate_name"] or "—",
            "up": best_score_pct > 0,
        },
        "avg_score": {
            "value": f"{avg_score_pct}%",
            "delta": f"{kpis['analyses_completed']} analyzed",
            "up": avg_score_pct > 0,
        },
        # Raw values for other uses
        "_raw": kpis,
    }


def get_score_distribution(company_id: int, jd_id: Optional[int] = None) -> dict[str, Any]:
    return analysis_repo.get_score_distribution(company_id, jd_id)


def get_skills_coverage(company_id: int, jd_id: Optional[int] = None) -> dict[str, Any]:
    return analysis_repo.get_skills_frequency(company_id, jd_id, top_n=10)


def get_experience_distribution(company_id: int, jd_id: Optional[int] = None) -> dict[str, Any]:
    return analysis_repo.get_experience_distribution(company_id, jd_id)


def get_education_breakdown(company_id: int, jd_id: Optional[int] = None) -> dict[str, Any]:
    return analysis_repo.get_education_breakdown(company_id, jd_id)


def get_top_technologies(company_id: int, jd_id: Optional[int] = None) -> dict[str, Any]:
    data = analysis_repo.get_skills_frequency(company_id, jd_id, top_n=8)
    return {"tech": data["skills"], "count": data["coverage"]}


def get_missing_skills(company_id: int, jd_id: Optional[int] = None) -> dict[str, Any]:
    return analysis_repo.get_missing_skills_frequency(company_id, jd_id, top_n=8)


def get_hiring_funnel(company_id: int, jd_id: Optional[int] = None) -> dict[str, Any]:
    return analysis_repo.get_pipeline_funnel(company_id, jd_id)
