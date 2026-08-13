from __future__ import annotations

import pytest

import backend.database.db as db_module
from backend.database.db import get_db, init_db
from backend.repositories import candidate_repo, jd_repo
from backend.services import jd_service, upload_service


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    existing = getattr(db_module._local, "conn", None)
    if existing is not None:
        existing.close()
        db_module._local.conn = None

    test_db_path = tmp_path / "ats-test.db"
    monkeypatch.setattr(db_module, "_DB_PATH", str(test_db_path))
    init_db()

    yield

    conn = getattr(db_module._local, "conn", None)
    if conn is not None:
        conn.close()
        db_module._local.conn = None


def _seed_company_and_user() -> tuple[int, int]:
    with get_db() as db:
        company_id = db.execute(
            "INSERT INTO companies (name) VALUES (?)",
            ("Test Company",),
        ).lastrowid
        user_id = db.execute(
            """
            INSERT INTO users (company_id, name, email, password_hash, role)
            VALUES (?, ?, ?, ?, ?)
            """,
            (company_id, "Test User", "test@example.com", "hash", "hr_manager"),
        ).lastrowid
    return int(company_id), int(user_id)


def test_first_jd_is_auto_activated_without_explicit_flag(isolated_db):
    company_id, user_id = _seed_company_and_user()

    jd_id = jd_service.create_job_description(
        company_id,
        user_id,
        "Backend Engineer",
        "Build APIs and services",
        "Python, FastAPI",
        make_active=False,
    )

    active = jd_service.get_active_jd(company_id)

    assert active is not None
    assert jd_id == active["id"]
    assert active["title"] == "Backend Engineer"


def test_activate_jd_keeps_only_one_active(isolated_db):
    company_id, user_id = _seed_company_and_user()

    first_id = jd_service.create_job_description(company_id, user_id, "Role A", "Desc A", make_active=True)
    second_id = jd_service.create_job_description(company_id, user_id, "Role B", "Desc B", make_active=False)

    jd_service.activate_jd(company_id, second_id)

    with get_db() as db:
        active_rows = db.execute(
            "SELECT id FROM job_descriptions WHERE company_id = ? AND is_active = 1",
            (company_id,),
        ).fetchall()

    assert [row[0] for row in active_rows] == [second_id]
    assert first_id != second_id


def test_deleting_active_jd_promotes_another_jd(isolated_db):
    company_id, user_id = _seed_company_and_user()

    first_id = jd_service.create_job_description(company_id, user_id, "Role A", "Desc A", make_active=True)
    second_id = jd_service.create_job_description(company_id, user_id, "Role B", "Desc B", make_active=False)

    jd_service.delete_job_description(company_id, first_id)

    active = jd_service.get_active_jd(company_id)
    assert active is not None
    assert active["id"] == second_id


def test_deleting_only_active_jd_is_blocked(isolated_db):
    company_id, user_id = _seed_company_and_user()
    jd_id = jd_service.create_job_description(company_id, user_id, "Only Role", "Desc", make_active=True)

    with pytest.raises(ValueError, match="only active Job Description"):
        jd_service.delete_job_description(company_id, jd_id)


def test_delete_recent_upload_removes_storage_file_and_linked_records(isolated_db, tmp_path):
    company_id, user_id = _seed_company_and_user()
    jd_id = jd_service.create_job_description(
        company_id,
        user_id,
        "ML Engineer",
        "Need Python and ML skills",
        make_active=True,
    )

    file_path = tmp_path / "sample_resume.pdf"
    file_path.write_bytes(b"%PDF-1.4\nSample resume")

    upload_id = candidate_repo.save_upload_record(
        company_id=company_id,
        jd_id=jd_id,
        uploaded_by=user_id,
        filename="sample_resume.pdf",
        file_path=str(file_path),
        file_size=file_path.stat().st_size,
        file_hash="hash-123",
        status="completed",
    )

    jd_repo.increment_resume_count(jd_id)

    with get_db() as db:
        candidate_id = db.execute(
            """
            INSERT INTO candidates
            (company_id, jd_id, upload_id, candidate_uid, name, email, phone, location,
             current_title, experience_years, summary, github, linkedin, pipeline_stage)
            VALUES (?, ?, ?, ?, ?, '', '', '', '', 0.0, '', '', '', 'AI_ANALYZED')
            """,
            (company_id, jd_id, upload_id, "CAND_0001", "Test Candidate"),
        ).lastrowid

        db.execute(
            "INSERT INTO candidate_skills (candidate_id, name) VALUES (?, ?)",
            (candidate_id, "Python"),
        )
        db.execute(
            "INSERT INTO analysis_results (candidate_id, jd_id, overall_score) VALUES (?, ?, ?)",
            (candidate_id, jd_id, 0.62),
        )

    upload_service.delete_uploaded_resume(upload_id=upload_id, company_id=company_id)

    with get_db() as db:
        assert db.execute("SELECT COUNT(*) FROM resume_uploads WHERE id = ?", (upload_id,)).fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM candidates WHERE upload_id = ?", (upload_id,)).fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM candidate_skills WHERE candidate_id = ?", (candidate_id,)).fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM analysis_results WHERE candidate_id = ?", (candidate_id,)).fetchone()[0] == 0

    assert not file_path.exists()

    active = jd_service.get_active_jd(company_id)
    assert active is not None
    assert active["resume_count"] == 0
