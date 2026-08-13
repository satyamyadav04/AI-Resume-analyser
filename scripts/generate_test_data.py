"""
scripts/generate_test_data.py — Synthetic dataset generator
============================================================
Generates a ``candidates.jsonl.gz`` file for local smoke-testing.

Embeds deliberate traps:
  • 20 % Title Traps  (Marketing Manager, HR Manager, etc.)
  • 5  % Honeypots    (expert skill, 0 months experience)

Usage
-----
    python scripts/generate_test_data.py --n 100000 --out data/candidates.jsonl.gz
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
import string
import sys
from typing import Any


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_TECHNICAL_TITLES = [
    "Senior AI Engineer", "Machine Learning Engineer", "Data Scientist",
    "NLP Engineer", "Computer Vision Engineer", "ML Platform Engineer",
    "Research Scientist", "Backend Engineer", "MLOps Engineer",
]

_TRAP_TITLES = [
    "Marketing Manager", "HR Manager", "Operations Manager",
    "Accountant", "Sales Representative", "Business Development Manager",
    "Recruiter", "Customer Service Manager", "Logistics Coordinator",
]

_SKILLS_POOL = [
    "Python", "PyTorch", "TensorFlow", "Scikit-learn", "NLP",
    "Computer Vision", "Kubernetes", "Docker", "SQL", "Spark",
    "FastAPI", "MLflow", "LangChain", "CUDA", "Transformers",
    "HuggingFace", "RAG", "LLM", "Feature Engineering", "Data Engineering",
    "JavaScript", "React", "Excel", "SAP", "PowerPoint",
]

_PROFICIENCY_LEVELS = ["beginner", "intermediate", "advanced", "expert"]
_UNIVERSITIES = ["MIT", "Stanford", "CMU", "IIT Bombay", "UC Berkeley", "Oxford"]
_COMPANIES = ["Google", "Meta", "Amazon", "Microsoft", "OpenAI", "Startup Inc."]


def _random_id(rng: random.Random, idx: int) -> str:
    return f"CAND_{idx:06d}"


def _random_skills(rng: random.Random, is_honeypot: bool = False) -> list[dict]:
    n_skills = rng.randint(3, 8)
    chosen = rng.sample(_SKILLS_POOL, min(n_skills, len(_SKILLS_POOL)))
    skills = []
    for i, skill in enumerate(chosen):
        proficiency = rng.choice(_PROFICIENCY_LEVELS)
        if is_honeypot and i == 0:
            proficiency = rng.choice(["expert", "advanced"])
            duration = 0
        else:
            duration = rng.randint(1, 60)
        skills.append({
            "name": skill,
            "proficiency": proficiency,
            "duration_months": duration,
        })
    return skills


def _random_experience(rng: random.Random) -> list[dict]:
    n_jobs = rng.randint(1, 4)
    jobs = []
    for _ in range(n_jobs):
        months = rng.randint(6, 48)
        jobs.append({
            "company": rng.choice(_COMPANIES),
            "title": rng.choice(_TECHNICAL_TITLES[:4]),
            "duration_months": months,
            "description": "Worked on ML models and data pipelines.",
        })
    return jobs


def generate_candidate(idx: int, rng: random.Random) -> dict[str, Any]:
    is_trap = rng.random() < 0.20        # 20% title traps
    is_honeypot = rng.random() < 0.05   # 5% honeypots

    title = rng.choice(_TRAP_TITLES if is_trap else _TECHNICAL_TITLES)
    experience = _random_experience(rng)
    total_months = sum(e["duration_months"] for e in experience)

    return {
        "candidate_id": _random_id(rng, idx),
        "name": f"Candidate {''.join(rng.choices(string.ascii_uppercase, k=4))}",
        "profile": {
            "current_title": title,
            "summary": (
                "Experienced AI engineer with expertise in deep learning and NLP."
                if not is_trap else
                "Professional with strong communication and leadership skills."
            ),
            "github": f"https://github.com/cand{idx}" if rng.random() > 0.4 else "",
            "linkedin": f"https://linkedin.com/in/cand{idx}" if rng.random() > 0.3 else "",
        },
        "skills": _random_skills(rng, is_honeypot=is_honeypot),
        "experience": experience,
        "experience_years": round(total_months / 12, 1),
        "education": [
            {
                "institution": rng.choice(_UNIVERSITIES),
                "degree": "B.Tech" if rng.random() > 0.4 else "M.S.",
                "field": "Computer Science",
                "graduation_year": rng.randint(2010, 2023),
            }
        ],
        "projects": [],
        "certifications": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic candidate data")
    parser.add_argument("--n", type=int, default=10_000, help="Number of candidates")
    parser.add_argument("--out", default="data/candidates.jsonl.gz", help="Output path")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed")
    args = parser.parse_args()

    import os
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)

    rng = random.Random(args.seed)
    print(f"Generating {args.n:,} synthetic candidates → {args.out} …")

    with gzip.open(args.out, "wt", encoding="utf-8") as fh:
        for i in range(1, args.n + 1):
            candidate = generate_candidate(i, rng)
            fh.write(json.dumps(candidate) + "\n")
            if i % 10_000 == 0:
                print(f"  {i:,} / {args.n:,} written …")

    print(f"✅  Done — {args.n:,} candidates written to {args.out}")


if __name__ == "__main__":
    main()
