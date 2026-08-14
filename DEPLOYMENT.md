# Deployment guide

This is a Streamlit application backed by PostgreSQL. Deploy it with the app entry point:

```text
frontend/app.py
```

Use Python 3.11 and install dependencies from `requirements.txt`. In the deployment dashboard, set `DATABASE_URL` to a PostgreSQL connection string. The app creates its tables automatically on first launch.

The repository includes the small challenge dataset sample used by **Resume Analysis → Use Challenge Dataset**. It is intentionally used when the larger `candidates.jsonl` file is not bundled, so imports remain deploy-safe.

For persistent user uploads, attach persistent storage or use object storage in production. Ephemeral hosts can process resumes, but locally written files can disappear after a redeploy.

Optional email notifications require the `ATS_SMTP_*` variables shown in `.env.example`. Do not commit actual credentials.
