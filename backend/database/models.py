"""
backend/database/models.py — Table DDL Definitions
====================================================
All 18 ATS table definitions as SQL strings.
ALL_DDL is imported by db.init_db() to create the schema.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------
_COMPANIES_DDL = """
CREATE TABLE IF NOT EXISTS companies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

# ---------------------------------------------------------------------------
# Users (HR accounts)
# ---------------------------------------------------------------------------
_USERS_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id    INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name          TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'hr_manager',
    avatar_initials TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

# ---------------------------------------------------------------------------
# Job Descriptions
# ---------------------------------------------------------------------------
_JOB_DESCRIPTIONS_DDL = """
CREATE TABLE IF NOT EXISTS job_descriptions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id    INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    created_by    INTEGER NOT NULL REFERENCES users(id),
    title         TEXT    NOT NULL,
    description   TEXT    NOT NULL,
    requirements  TEXT    DEFAULT '',
    is_active     INTEGER NOT NULL DEFAULT 0,
    resume_count  INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

# ---------------------------------------------------------------------------
# Resume Uploads (file tracking)
# ---------------------------------------------------------------------------
_RESUME_UPLOADS_DDL = """
CREATE TABLE IF NOT EXISTS resume_uploads (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id    INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    jd_id         INTEGER NOT NULL REFERENCES job_descriptions(id) ON DELETE CASCADE,
    uploaded_by   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename      TEXT    NOT NULL,
    file_path     TEXT    NOT NULL,
    file_size     INTEGER DEFAULT 0,
    file_hash     TEXT,
    status        TEXT    NOT NULL DEFAULT 'uploaded',
    error_message TEXT    DEFAULT '',
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------
_CANDIDATES_DDL = """
CREATE TABLE IF NOT EXISTS candidates (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id       INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    jd_id            INTEGER NOT NULL REFERENCES job_descriptions(id) ON DELETE CASCADE,
    upload_id        INTEGER REFERENCES resume_uploads(id) ON DELETE SET NULL,
    candidate_uid    TEXT    NOT NULL,
    name             TEXT    NOT NULL DEFAULT 'Unknown',
    email            TEXT    DEFAULT '',
    phone            TEXT    DEFAULT '',
    location         TEXT    DEFAULT '',
    current_title    TEXT    DEFAULT '',
    experience_years REAL    NOT NULL DEFAULT 0.0,
    summary          TEXT    DEFAULT '',
    github           TEXT    DEFAULT '',
    linkedin         TEXT    DEFAULT '',
    pipeline_stage   TEXT    NOT NULL DEFAULT 'NEW',
    is_shortlisted   INTEGER NOT NULL DEFAULT 0,
    is_rejected      INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

# ---------------------------------------------------------------------------
# Analysis Results
# ---------------------------------------------------------------------------
_ANALYSIS_RESULTS_DDL = """
CREATE TABLE IF NOT EXISTS analysis_results (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id      INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    jd_id             INTEGER NOT NULL REFERENCES job_descriptions(id) ON DELETE CASCADE,
    overall_score     REAL    NOT NULL DEFAULT 0.0,
    skill_match       REAL    NOT NULL DEFAULT 0.0,
    semantic_match    REAL    NOT NULL DEFAULT 0.0,
    experience_score  REAL    NOT NULL DEFAULT 0.0,
    education_score   REAL    NOT NULL DEFAULT 0.0,
    project_score     REAL    NOT NULL DEFAULT 0.0,
    ai_summary        TEXT    DEFAULT '',
    recommendation    TEXT    DEFAULT '',
    reasoning         TEXT    DEFAULT '',
    strengths         TEXT    DEFAULT '[]',
    weaknesses        TEXT    DEFAULT '[]',
    missing_skills    TEXT    DEFAULT '[]',
    status            TEXT    NOT NULL DEFAULT 'CLEAN',
    rank_position     INTEGER DEFAULT 0,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

# ---------------------------------------------------------------------------
# Candidate Skills
# ---------------------------------------------------------------------------
_CANDIDATE_SKILLS_DDL = """
CREATE TABLE IF NOT EXISTS candidate_skills (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id    INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    name            TEXT    NOT NULL,
    proficiency     TEXT    DEFAULT 'intermediate',
    duration_months INTEGER DEFAULT 0,
    is_verified     INTEGER NOT NULL DEFAULT 0
);
"""

# ---------------------------------------------------------------------------
# Candidate Experience
# ---------------------------------------------------------------------------
_CANDIDATE_EXPERIENCE_DDL = """
CREATE TABLE IF NOT EXISTS candidate_experience (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id    INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    company         TEXT    DEFAULT '',
    title           TEXT    DEFAULT '',
    duration_months INTEGER DEFAULT 0,
    description     TEXT    DEFAULT '',
    start_date      TEXT    DEFAULT '',
    end_date        TEXT    DEFAULT ''
);
"""

# ---------------------------------------------------------------------------
# Candidate Education
# ---------------------------------------------------------------------------
_CANDIDATE_EDUCATION_DDL = """
CREATE TABLE IF NOT EXISTS candidate_education (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id    INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    degree          TEXT    DEFAULT '',
    institution     TEXT    DEFAULT '',
    year            TEXT    DEFAULT '',
    score           TEXT    DEFAULT ''
);
"""

# ---------------------------------------------------------------------------
# Candidate Projects
# ---------------------------------------------------------------------------
_CANDIDATE_PROJECTS_DDL = """
CREATE TABLE IF NOT EXISTS candidate_projects (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id    INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    name            TEXT    DEFAULT '',
    description     TEXT    DEFAULT '',
    technologies    TEXT    DEFAULT ''
);
"""

# ---------------------------------------------------------------------------
# Candidate Certificates
# ---------------------------------------------------------------------------
_CANDIDATE_CERTIFICATES_DDL = """
CREATE TABLE IF NOT EXISTS candidate_certificates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id    INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    name            TEXT    NOT NULL,
    issuer          TEXT    DEFAULT '',
    year            TEXT    DEFAULT ''
);
"""

# ---------------------------------------------------------------------------
# Candidate Notes (recruiter notes)
# ---------------------------------------------------------------------------
_CANDIDATE_NOTES_DDL = """
CREATE TABLE IF NOT EXISTS candidate_notes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id    INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    note_text       TEXT    NOT NULL,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

# ---------------------------------------------------------------------------
# Candidate Timeline
# ---------------------------------------------------------------------------
_CANDIDATE_TIMELINE_DDL = """
CREATE TABLE IF NOT EXISTS candidate_timeline (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id    INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    user_id         INTEGER REFERENCES users(id),
    event_type      TEXT    NOT NULL,
    event_detail    TEXT    DEFAULT '',
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

# ---------------------------------------------------------------------------
# Recruitment Pipeline (interview scheduling)
# ---------------------------------------------------------------------------
_RECRUITMENT_PIPELINE_DDL = """
CREATE TABLE IF NOT EXISTS recruitment_pipeline (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id    INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    company_id      INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    jd_id           INTEGER NOT NULL REFERENCES job_descriptions(id) ON DELETE CASCADE,
    stage           TEXT    NOT NULL DEFAULT 'NEW',
    interview_date  TEXT    DEFAULT '',
    interview_time  TEXT    DEFAULT '',
    round_name      TEXT    DEFAULT '',
    interviewer     TEXT    DEFAULT '',
    meeting_link    TEXT    DEFAULT '',
    feedback        TEXT    DEFAULT '',
    rating          INTEGER DEFAULT 0,
    result          TEXT    DEFAULT '',
    updated_by      INTEGER REFERENCES users(id),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

# ---------------------------------------------------------------------------
# Shortlisted Candidates (sync table)
# ---------------------------------------------------------------------------
_SHORTLISTED_CANDIDATES_DDL = """
CREATE TABLE IF NOT EXISTS shortlisted_candidates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id    INTEGER NOT NULL UNIQUE REFERENCES candidates(id) ON DELETE CASCADE,
    company_id      INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    jd_id           INTEGER NOT NULL REFERENCES job_descriptions(id) ON DELETE CASCADE,
    shortlisted_by  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
_REPORTS_DDL = """
CREATE TABLE IF NOT EXISTS reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id      INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    jd_id           INTEGER REFERENCES job_descriptions(id) ON DELETE SET NULL,
    created_by      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    report_type     TEXT    NOT NULL,
    file_path       TEXT    NOT NULL,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

# ---------------------------------------------------------------------------
# Activity History
# ---------------------------------------------------------------------------
_ACTIVITY_HISTORY_DDL = """
CREATE TABLE IF NOT EXISTS activity_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id      INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    user_id         INTEGER REFERENCES users(id),
    action          TEXT    NOT NULL,
    entity_type     TEXT    DEFAULT '',
    entity_id       INTEGER DEFAULT 0,
    detail          TEXT    DEFAULT '',
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
_SETTINGS_DDL = """
CREATE TABLE IF NOT EXISTS settings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    theme           TEXT    NOT NULL DEFAULT 'light',
    language        TEXT    NOT NULL DEFAULT 'English (US)',
    notifications   TEXT    NOT NULL DEFAULT '{"email":true,"weekly":true,"reminders":false}',
    analysis_mode   TEXT    NOT NULL DEFAULT 'Balanced',
    ai_model        TEXT    NOT NULL DEFAULT 'Resume-Analyzer v3 (Recommended)',
    default_jd_id   INTEGER DEFAULT NULL,
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

# ---------------------------------------------------------------------------
# Indexes for performance
# ---------------------------------------------------------------------------
_INDEXES_DDL = [
    "CREATE INDEX IF NOT EXISTS idx_candidates_company_jd ON candidates(company_id, jd_id);",
    "CREATE INDEX IF NOT EXISTS idx_candidates_pipeline ON candidates(pipeline_stage);",
    "CREATE INDEX IF NOT EXISTS idx_analysis_candidate ON analysis_results(candidate_id);",
    "CREATE INDEX IF NOT EXISTS idx_analysis_score ON analysis_results(overall_score DESC);",
    "CREATE INDEX IF NOT EXISTS idx_uploads_company ON resume_uploads(company_id, jd_id);",
    "CREATE INDEX IF NOT EXISTS idx_uploads_status ON resume_uploads(status, created_at DESC);",
    "CREATE INDEX IF NOT EXISTS idx_timeline_candidate ON candidate_timeline(candidate_id);",
    "CREATE INDEX IF NOT EXISTS idx_notes_candidate ON candidate_notes(candidate_id);",
    "CREATE INDEX IF NOT EXISTS idx_skills_candidate ON candidate_skills(candidate_id);",
    "CREATE INDEX IF NOT EXISTS idx_jd_company ON job_descriptions(company_id);",
    "CREATE INDEX IF NOT EXISTS idx_jd_active_lookup ON job_descriptions(company_id, is_active, updated_at DESC);",
    "CREATE INDEX IF NOT EXISTS idx_pipeline_company_jd ON recruitment_pipeline(company_id, jd_id);",
]

# ---------------------------------------------------------------------------
# ALL_DDL — imported by db.init_db()
# ---------------------------------------------------------------------------
ALL_DDL: list[str] = [
    _COMPANIES_DDL,
    _USERS_DDL,
    _JOB_DESCRIPTIONS_DDL,
    _RESUME_UPLOADS_DDL,
    _CANDIDATES_DDL,
    _ANALYSIS_RESULTS_DDL,
    _CANDIDATE_SKILLS_DDL,
    _CANDIDATE_EXPERIENCE_DDL,
    _CANDIDATE_EDUCATION_DDL,
    _CANDIDATE_PROJECTS_DDL,
    _CANDIDATE_CERTIFICATES_DDL,
    _CANDIDATE_NOTES_DDL,
    _CANDIDATE_TIMELINE_DDL,
    _RECRUITMENT_PIPELINE_DDL,
    _SHORTLISTED_CANDIDATES_DDL,
    _REPORTS_DDL,
    _ACTIVITY_HISTORY_DDL,
    _SETTINGS_DDL,
] + _INDEXES_DDL
