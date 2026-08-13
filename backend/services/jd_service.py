"""
backend/services/jd_service.py — Job Description Business Logic
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from backend.repositories import jd_repo

logger = logging.getLogger(__name__)


def create_job_description(
    company_id: int,
    user_id: int,
    title: str,
    description: str,
    requirements: str = "",
    make_active: bool = True,
) -> int:
    """Create a new JD and optionally activate it. Returns jd_id."""
    title = title.strip()
    description = description.strip()
    requirements = requirements.strip()

    if not title:
        raise ValueError("Job title cannot be empty.")
    if not description:
        raise ValueError("Job description cannot be empty.")

    jd_id = jd_repo.create_jd(
        company_id=company_id,
        created_by=user_id,
        title=title,
        description=description,
        requirements=requirements,
    )

    should_activate = make_active or jd_repo.get_active_jd(company_id) is None
    if should_activate:
        jd_repo.set_active_jd(company_id, jd_id)
        logger.info("Created and activated JD #%d: %s", jd_id, title)
    else:
        logger.info("Created JD #%d: %s (not active)", jd_id, title)

    return jd_id


def activate_jd(company_id: int, jd_id: int) -> None:
    """Set a JD as active (deactivating all others)."""
    jd = jd_repo.get_jd(jd_id)
    if not jd or jd["company_id"] != company_id:
        raise ValueError(f"Job description #{jd_id} not found.")
    jd_repo.set_active_jd(company_id, jd_id)
    logger.info("Activated JD #%d for company #%d", jd_id, company_id)


def get_active_jd(company_id: int) -> Optional[dict[str, Any]]:
    """Return the active JD dict or None."""
    return jd_repo.get_active_jd(company_id)


def get_active_jd_text(company_id: int) -> str:
    """Return the full text of the active JD for embedding."""
    jd = jd_repo.get_active_jd(company_id)
    if not jd:
        return ""
    parts = [jd.get("title", ""), jd.get("description", ""), jd.get("requirements", "")]
    return " ".join(p for p in parts if p).strip()


def get_upload_target_jd(company_id: int, requested_jd_id: Optional[int] = None) -> dict[str, Any]:
    """Return the enforced active JD for resume uploads."""
    active_jd = jd_repo.get_active_jd(company_id)
    if not active_jd:
        raise ValueError("No active Job Description found. Create or activate one before uploading resumes.")

    if requested_jd_id and requested_jd_id != active_jd["id"]:
        logger.warning(
            "Upload requested for JD #%d, but active JD #%d is enforced for company #%d",
            requested_jd_id,
            active_jd["id"],
            company_id,
        )

    return active_jd


def list_job_descriptions(company_id: int) -> list[dict[str, Any]]:
    """Return all JDs for a company."""
    return jd_repo.list_jds(company_id)


def update_job_description(company_id: int, jd_id: int, title: str, description: str, requirements: str = "") -> None:
    """Update a JD."""
    jd = jd_repo.get_jd(jd_id)
    if not jd or jd["company_id"] != company_id:
        raise ValueError(f"Job description #{jd_id} not found.")
    title = title.strip()
    description = description.strip()
    requirements = requirements.strip()
    if not title:
        raise ValueError("Job title cannot be empty.")
    if not description:
        raise ValueError("Job description cannot be empty.")
    jd_repo.update_jd(jd_id, title=title, description=description, requirements=requirements)


def delete_job_description(company_id: int, jd_id: int) -> None:
    """Delete a JD."""
    jd = jd_repo.get_jd(jd_id)
    if not jd or jd["company_id"] != company_id:
        raise ValueError(f"Job description #{jd_id} not found.")
    if jd.get("is_active"):
        remaining_jds = [row for row in jd_repo.list_jds(company_id) if row["id"] != jd_id]
        if not remaining_jds:
            raise ValueError("Cannot delete the only active Job Description. Create another JD first.")
        jd_repo.set_active_jd(company_id, remaining_jds[0]["id"])
    jd_repo.delete_jd(jd_id)
    logger.info("Deleted JD #%d", jd_id)


def duplicate_job_description(company_id: int, user_id: int, jd_id: int) -> int:
    """Duplicate an existing JD. Returns new jd_id."""
    jd = jd_repo.get_jd(jd_id)
    if not jd or jd["company_id"] != company_id:
        raise ValueError(f"Job description #{jd_id} not found.")
    new_id = jd_repo.create_jd(
        company_id=company_id,
        created_by=user_id,
        title=f"Copy of {jd['title']}",
        description=jd["description"],
        requirements=jd.get("requirements", ""),
    )
    logger.info("Duplicated JD #%d → #%d", jd_id, new_id)
    return new_id
