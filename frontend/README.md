# AI Resume Analyzer — Premium Dashboard (Frontend Only)

A polished, enterprise-grade Streamlit dashboard UI for an AI Resume Analyzer.
This is **frontend only** — every value on screen is placeholder/demo data.
No parsing, embeddings, or ranking logic is implemented; that's left for
backend integration later.

## Run it

```bash
pip install streamlit plotly
streamlit run app.py
```

## Structure

```
app.py               entry point / router
theme.py              light + dark color tokens, theme state
styles.py             global CSS injection (restyles all of Streamlit)
components.py         reusable UI: metric cards, score ring, progress bars,
                       skill badges, pills, candidate card, ranked table
sidebar.py            nav rail, upgrade card, storage, user footer
header.py             top bar: search, theme toggle, notifications, avatar
demo_data.py          all placeholder/demo data in one place
dashboard.py          Dashboard page
resume_analysis.py    Resume Analysis page
job_description.py    Job Description page
ranking.py             Ranked Candidates page
analytics.py           Analytics page (6 Plotly charts)
shortlisted.py         Shortlisted page
settings.py             Settings page
assets/                (reserved for logos/icons if added later)
```

## Notes for backend integration

- Replace the contents of `demo_data.py` with real API responses.
- The file uploader in `dashboard.py` already captures the uploaded file —
  wire its `uploaded` object into your parsing pipeline.
- The "Analyze Resume" button in `job_description.py` is a no-op placeholder —
  attach your analysis call to its `st.button(...)` conditional.
- Theme state lives in `st.session_state.theme_mode` (`"light"` / `"dark"`).
