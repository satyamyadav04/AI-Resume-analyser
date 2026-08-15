# 🚀 AI Resume Analyzer & Ranker

> **An AI-powered Resume Analyzer and Candidate Ranking System built using Python, Streamlit, FAISS, and Sentence Transformers to automate resume screening and candidate ranking.**

---

# 📌 Project Overview

The **AI Resume Analyzer & Ranker** is an intelligent recruitment solution that helps recruiters and HR professionals efficiently screen, analyze, and rank resumes based on a given Job Description (JD).

Using **Natural Language Processing (NLP)** and **semantic similarity search**, the system evaluates candidate profiles, calculates match scores, and ranks applicants according to their relevance.

This significantly reduces manual effort while improving hiring accuracy and efficiency.

# 📌 Demo Link:- https://ai-resume-analyser-qqgobjjmq8vodtjvqvahyd.streamlit.app/
---

# ✨ Features

### 🤖 AI-Powered Resume Ranking
- Semantic resume matching using Sentence Transformers
- FAISS vector similarity search
- Automatic match percentage calculation
- Intelligent candidate ranking

### 📄 Resume Parsing
- Supports PDF resumes
- Supports DOCX resumes
- Extracts candidate information
- Batch resume processing

### 📊 Interactive Dashboard
- Total resumes uploaded
- Average match score
- Top-ranked candidates
- KPI cards
- Charts and visual insights

### 🔍 Candidate Insights
- Resume preview
- Match percentage
- Skill comparison
- Experience analysis
- Individual candidate details

### ⚡ Fast & Efficient
- AI-powered resume analysis
- High-speed vector search
- Optimized processing pipeline

---

# 🛠️ Tech Stack

| **Category** | **Technology** |
|--------------|----------------|
| **Frontend** | Streamlit |
| **Backend** | Python |
| **Data Processing** | Pandas |
| **AI / NLP** | Sentence Transformers |
| **Vector Search** | FAISS |
| **PDF Parser** | PyMuPDF |
| **DOCX Parser** | python-docx |

---

# 📂 Project Structure

```text
AI-Resume-Analyzer/
│
├── backend/
│   ├── ranking.py
│   ├── scoring.py
│   └── parser.py
│
├── frontend/
│   ├── app.py
│   └── pages/
│
├── data/
├── assets/
├── requirements.txt
├── README.md
└── LICENSE
```

---

# ⚙️ Installation

## **1️⃣ Clone the Repository**

```bash
git clone https://github.com/your-username/AI-Resume-Analyzer.git

cd AI-Resume-Analyzer
```

## **2️⃣ Create a Virtual Environment**

### Windows

```bash
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

## **3️⃣ Install Dependencies**

```bash
pip install -r requirements.txt
```

---

# 🚀 Run the Application

```bash
python -m streamlit run frontend/app.py
```

or

```bash
streamlit run frontend/app.py
```

## Gmail SMTP Setup

Interview scheduling ke time candidate ko email bhejne ke liye Gmail SMTP use kar sakte hain.

1. `.streamlit/secrets.toml.example` ko `.streamlit/secrets.toml` naam se copy karein.
2. `user`, `from_email` me apna Gmail address daalein.
3. `password` me normal Gmail password nahi, Google App Password daalein.
4. App restart karein.

Example:

```toml
[smtp]
host = "smtp.gmail.com"
port = 587
user = "yourgmail@gmail.com"
password = "your-16-char-gmail-app-password"
from_email = "yourgmail@gmail.com"
from_name = "Your Company Recruitment"
use_tls = true
```

---

# 📈 Workflow

1. Upload resumes (PDF/DOCX)
2. Enter the Job Description
3. AI extracts resume information
4. Generate resume embeddings
5. Compare resumes with JD using FAISS
6. Calculate similarity scores
7. Rank candidates automatically
8. View insights through the dashboard

---

# 📸 Screenshots

> Add screenshots of your application here.

```md
![Dashboard](assets/dashboard.png)

![Candidate Ranking](assets/ranking.png)

![Resume Analysis](assets/analysis.png)
```

---

# 🎯 Future Enhancements

- ATS Compatibility Score
- AI Interview Question Generator
- Resume Keyword Highlighting
- Skill Gap Analysis
- Recruiter Login System
- Export Reports (PDF & Excel)
- Database Integration
- Cloud Deployment
- Email Notifications

---

# 🤝 Contributing

Contributions are always welcome!

```bash
git checkout -b feature-name
git commit -m "Added new feature"
git push origin feature-name
```

Then open a Pull Request.

---

# 📝 License

This project is licensed under the **MIT License**.

---

# 👩‍💻 Author

## **Unknown**
# ⭐ Support

If you found this project helpful, **please give it a ⭐ Star on GitHub!**
