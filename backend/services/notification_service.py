"""
backend/services/notification_service.py - Email notification helpers
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

import tomllib

logger = logging.getLogger(__name__)


def send_interview_schedule_email(
    *,
    candidate_email: str,
    candidate_name: str,
    company_name: str,
    jd_title: str,
    interview_data: dict,
) -> dict[str, str | bool]:
    """Send an interview schedule email when SMTP is configured."""
    recipient = (candidate_email or "").strip()
    if not recipient:
        return {
            "attempted": False,
            "sent": False,
            "recipient": "",
            "message": "Candidate email missing, so notification was skipped.",
        }

    smtp_config = _load_smtp_config()
    smtp_host = smtp_config["host"]
    smtp_user = smtp_config["user"]
    smtp_password = smtp_config["password"]
    from_email = smtp_config["from_email"]

    if not smtp_host or not from_email:
        return {
            "attempted": False,
            "sent": False,
            "recipient": recipient,
            "message": "SMTP is not configured yet. Interview saved without email.",
        }

    smtp_port = int(smtp_config["port"])
    use_tls = str(smtp_config["use_tls"]).strip().lower() != "false"
    from_name = str(smtp_config["from_name"] or company_name or "Recruitment Team").strip()

    msg = EmailMessage()
    msg["Subject"] = f"Interview Scheduled - {jd_title or 'Job Opportunity'}"
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = recipient
    msg.set_content(
        _build_interview_email_body(
            candidate_name=candidate_name,
            company_name=company_name,
            jd_title=jd_title,
            interview_data=interview_data,
        )
    )

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as smtp:
            if use_tls:
                smtp.starttls()
            if smtp_user and smtp_password:
                smtp.login(smtp_user, smtp_password)
            smtp.send_message(msg)
        return {
            "attempted": True,
            "sent": True,
            "recipient": recipient,
            "message": f"Interview email sent to {recipient}.",
        }
    except Exception as exc:
        logger.exception("Failed to send interview email to %s: %s", recipient, exc)
        return {
            "attempted": True,
            "sent": False,
            "recipient": recipient,
            "message": f"Interview saved, but email delivery failed: {exc}",
        }


def _build_interview_email_body(
    *,
    candidate_name: str,
    company_name: str,
    jd_title: str,
    interview_data: dict,
) -> str:
    date = interview_data.get("date", "TBD")
    time = interview_data.get("time", "TBD")
    round_name = interview_data.get("round", "Interview")
    interviewer = interview_data.get("interviewer", "Hiring Team")
    meeting_link = interview_data.get("link", "").strip()

    lines = [
        f"Hi {candidate_name or 'Candidate'},",
        "",
        f"Your interview has been scheduled for the role: {jd_title or 'Open Position'}.",
        "",
        f"Company: {company_name or 'Our team'}",
        f"Round: {round_name}",
        f"Date: {date}",
        f"Time: {time}",
        f"Interviewer: {interviewer}",
    ]

    if meeting_link:
        lines.append(f"Meeting Link: {meeting_link}")

    lines.extend(
        [
            "",
            "Please be available a few minutes early.",
            "",
            "Regards,",
            company_name or "Recruitment Team",
        ]
    )
    return "\n".join(lines)


def _load_smtp_config() -> dict[str, str]:
    secrets_config = _read_streamlit_smtp_secrets()
    smtp_user = os.getenv("ATS_SMTP_USER", secrets_config.get("user", "")).strip()
    return {
        "host": os.getenv("ATS_SMTP_HOST", secrets_config.get("host", "")).strip(),
        "port": os.getenv("ATS_SMTP_PORT", str(secrets_config.get("port", "587"))).strip(),
        "user": smtp_user,
        "password": os.getenv("ATS_SMTP_PASSWORD", secrets_config.get("password", "")).strip(),
        "from_email": os.getenv(
            "ATS_SMTP_FROM_EMAIL",
            str(secrets_config.get("from_email", smtp_user)),
        ).strip(),
        "from_name": os.getenv("ATS_SMTP_FROM_NAME", str(secrets_config.get("from_name", ""))).strip(),
        "use_tls": os.getenv("ATS_SMTP_USE_TLS", str(secrets_config.get("use_tls", "true"))).strip(),
    }


def _read_streamlit_smtp_secrets() -> dict[str, str]:
    root = Path(__file__).resolve().parents[2]
    secrets_path = root / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        return {}

    try:
        data = tomllib.loads(secrets_path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to read SMTP secrets from %s", secrets_path)
        return {}

    smtp_section = data.get("smtp", {})
    if not isinstance(smtp_section, dict):
        return {}
    return {str(key): value for key, value in smtp_section.items()}
