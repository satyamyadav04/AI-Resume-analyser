"""
demo_data.py
Static placeholder data. No backend, no parsing, no AI calls —
purely illustrative values so every page renders fully populated.
"""

CANDIDATES = [
    {"rank": 1, "name": "Ananya Sharma", "role": "Senior Frontend Engineer", "score": 92,
     "skills_match": 94, "experience_match": 90, "education": "M.Tech, CS",
     "skills": ["React", "TypeScript", "GraphQL", "Next.js"], "recommendation": "Strong Fit",
     "experience": "6 yrs"},
    {"rank": 2, "name": "Rohan Mehta", "role": "Full Stack Developer", "score": 87,
     "skills_match": 88, "experience_match": 85, "education": "B.E, IT",
     "skills": ["Node.js", "React", "MongoDB", "AWS"], "recommendation": "Strong Fit",
     "experience": "5 yrs"},
    {"rank": 3, "name": "Priya Nair", "role": "Frontend Engineer", "score": 81,
     "skills_match": 83, "experience_match": 78, "education": "B.Tech, CSE",
     "skills": ["Vue.js", "JavaScript", "Figma", "CSS"], "recommendation": "Good Fit",
     "experience": "4 yrs"},
    {"rank": 4, "name": "Karan Verma", "role": "Software Engineer", "score": 74,
     "skills_match": 76, "experience_match": 70, "education": "B.Sc, Comp Sci",
     "skills": ["Python", "Django", "SQL"], "recommendation": "Good Fit",
     "experience": "3 yrs"},
    {"rank": 5, "name": "Ishita Rao", "role": "UI Engineer", "score": 68,
     "skills_match": 70, "experience_match": 64, "education": "B.Des",
     "skills": ["React", "Tailwind", "Figma"], "recommendation": "Possible Fit",
     "experience": "2 yrs"},
    {"rank": 6, "name": "Aditya Kulkarni", "role": "Junior Developer", "score": 55,
     "skills_match": 58, "experience_match": 48, "education": "B.C.A",
     "skills": ["HTML", "CSS", "JavaScript"], "recommendation": "Possible Fit",
     "experience": "1 yr"},
    {"rank": 7, "name": "Meera Iyer", "role": "QA cum Developer", "score": 41,
     "skills_match": 45, "experience_match": 36, "education": "B.Tech, ECE",
     "skills": ["Selenium", "Java"], "recommendation": "Not a Fit",
     "experience": "1 yr"},
]

BEST_CANDIDATE = CANDIDATES[0]

KPIS = {
    "resumes_uploaded": {"value": "128", "delta": "12 today", "up": True},
    "analyses_completed": {"value": "112", "delta": "8 today", "up": True},
    "best_score": {"value": "92%", "delta": "Ananya Sharma", "up": True},
    "avg_score": {"value": "71.2%", "delta": "3.4% vs last wk", "up": True},
}

SKILL_BREAKDOWN = [
    {"label": "Technical Skills", "pct": 88},
    {"label": "Experience", "pct": 76},
    {"label": "Education", "pct": 82},
    {"label": "Projects", "pct": 71},
    {"label": "Soft Skills", "pct": 65},
]

MISSING_SKILLS = ["Kubernetes", "GraphQL", "System Design", "CI/CD", "Redis"]

SCORE_DISTRIBUTION = {
    "buckets": ["0-20", "21-40", "41-60", "61-80", "81-100"],
    "counts": [3, 9, 24, 46, 30],
}

SKILLS_COVERAGE = {
    "skills": ["React", "Python", "SQL", "AWS", "Node.js", "Docker", "TypeScript", "GraphQL"],
    "coverage": [82, 74, 68, 55, 71, 48, 60, 33],
}

EXPERIENCE_DISTRIBUTION = {
    "labels": ["0-1 yrs", "1-3 yrs", "3-5 yrs", "5-8 yrs", "8+ yrs"],
    "counts": [14, 38, 41, 24, 11],
}

EDUCATION_BREAKDOWN = {
    "labels": ["B.Tech / B.E", "M.Tech / M.S", "B.Sc / B.C.A", "MBA", "Other"],
    "counts": [58, 27, 22, 9, 12],
}

TOP_TECHNOLOGIES = {
    "tech": ["React", "Python", "Node.js", "AWS", "SQL", "Docker", "TypeScript", "Java"],
    "count": [64, 58, 47, 43, 39, 31, 29, 24],
}

JD_PLACEHOLDER = (
    "We are looking for a Senior Frontend Engineer with 4+ years of experience "
    "in React, TypeScript, and modern component architecture. Experience with "
    "GraphQL, testing frameworks, and design systems is a strong plus. "
    "The ideal candidate has excellent collaboration skills and a track record "
    "of shipping production-grade UI at scale."
)
