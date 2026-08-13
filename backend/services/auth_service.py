"""
backend/services/auth_service.py — Authentication & Session Management
=======================================================================
Provides secure password hashing (PBKDF2-SHA256 with random salt),
user registration, login, and session helpers. Zero external dependencies.
"""
from __future__ import annotations

import hashlib
import logging
import os
from typing import Any, Optional

from backend.repositories import company_repo, user_repo, settings_repo

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    """Return a salted PBKDF2-SHA256 hash string: 'salt$hash'."""
    salt = os.urandom(16).hex()
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000).hex()
    return f"{salt}${hashed}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored 'salt$hash' string."""
    try:
        salt, expected = stored_hash.split("$", 1)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000).hex()
        return actual == expected
    except Exception:
        return False


def register(name: str, company_name: str, email: str, password: str) -> dict[str, Any]:
    """Create a new company + HR user. Returns user dict with company info.

    Raises ValueError if email already exists or password is too short.
    """
    email = email.strip().lower()

    if user_repo.email_exists(email):
        raise ValueError("An account with this email already exists.")

    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")

    if not name.strip():
        raise ValueError("Name cannot be empty.")

    if not company_name.strip():
        raise ValueError("Company name cannot be empty.")

    # Create company
    company_id = company_repo.create_company(company_name.strip())

    # Create user
    pw_hash = hash_password(password)
    user_id = user_repo.create_user(
        company_id=company_id,
        name=name.strip(),
        email=email,
        password_hash=pw_hash,
        role="hr_manager",
    )

    # Insert default settings
    settings_repo.get_settings(user_id)

    user = user_repo.get_user_by_id(user_id)
    company = company_repo.get_company(company_id)
    logger.info("Registered new user: %s (company: %s)", email, company_name)

    return _build_session_user(user, company)


def login(email: str, password: str) -> Optional[dict[str, Any]]:
    """Authenticate and return a session user dict, or None on failure."""
    email = email.strip().lower()
    user = user_repo.get_user_by_email(email)

    if not user:
        logger.debug("Login failed — no user with email: %s", email)
        return None

    if not verify_password(password, user["password_hash"]):
        logger.debug("Login failed — wrong password for: %s", email)
        return None

    company = company_repo.get_company(user["company_id"])
    logger.info("User logged in: %s", email)
    return _build_session_user(user, company)


def _build_session_user(user: dict, company: Optional[dict]) -> dict[str, Any]:
    """Build a minimal, safe session dict (no password hash)."""
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role": user.get("role", "hr_manager"),
        "avatar_initials": user.get("avatar_initials") or _initials(user["name"]),
        "company_id": user["company_id"],
        "company_name": company["name"] if company else "Unknown Company",
    }


def _initials(name: str) -> str:
    parts = name.strip().split()
    return "".join(p[0].upper() for p in parts[:2]) if parts else "??"


def update_profile(user_id: int, name: str, email: str, new_password: Optional[str] = None) -> dict[str, Any]:
    """Update user profile. Re-hashes password if provided."""
    fields: dict[str, Any] = {"name": name.strip(), "email": email.strip().lower()}
    if new_password:
        if len(new_password) < 6:
            raise ValueError("New password must be at least 6 characters.")
        fields["password_hash"] = hash_password(new_password)
    user_repo.update_user(user_id, **fields)
    user = user_repo.get_user_by_id(user_id)
    company = company_repo.get_company(user["company_id"])
    return _build_session_user(user, company)
