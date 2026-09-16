# Deployment guide

This is a Streamlit application backed by PostgreSQL. Deploy it with the app entry point:

```text
frontend/app.py
```

Use Python 3.11 and install dependencies from `requirements.txt`. The app creates its tables automatically on first launch.

## Database configuration

For Streamlit Community Cloud, open the app dashboard, select **Settings** ->
**Secrets**, and add a root-level `DATABASE_URL` entry:

```toml
DATABASE_URL = "postgresql://USER:PASSWORD@PUBLIC_HOST:5432/ai_resume_analyzer?sslmode=require"
```

Use the **external/public** connection string supplied by Render. A Render
internal URL only works for services deployed in Render's private network, so
it cannot be reached by an app running on Streamlit Community Cloud. Never
commit production credentials to `.streamlit/secrets.toml`; that filename is
intentionally ignored by Git.

The repository includes the small challenge dataset sample used by **Resume Analysis → Use Challenge Dataset**. It is intentionally used when the larger `candidates.jsonl` file is not bundled, so imports remain deploy-safe. The full local `candidates.jsonl` is ignored by Git because it is large; Streamlit Cloud cannot access it unless it is supplied through external storage, a database, or Git LFS.

For persistent user uploads, attach persistent storage or use object storage in production. Ephemeral hosts can process resumes, but locally written files can disappear after a redeploy.

Optional email notifications require the `ATS_SMTP_*` variables shown in `.env.example`. Do not commit actual credentials.
