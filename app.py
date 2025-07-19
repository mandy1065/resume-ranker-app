import streamlit as st
import pandas as pd
import os
import tempfile
import re
import pdfplumber
from docx import Document

# Sample skill keywords list (expand as needed)
SKILL_KEYWORDS = ["python", "sql", "excel", "aws", "machine learning", "java", "c++", "javascript", "react", "testing", "automation"]

# ---------- Streamlit Setup ----------
st.set_page_config(page_title="Resume Ranker (No spaCy)", layout="wide")
st.title("🎯 Resume Ranker Without spaCy")

# ---------- Step 1: Paste Job Description ----------
st.header("1️⃣ Paste Job Description")
job_title = st.text_input("Job Title", placeholder="e.g. Data Analyst")
job_description = st.text_area("Paste Job Description", height=200)

# ---------- Step 2: Upload Resumes ----------
st.header("2️⃣ Upload Resumes")
resumes = st.file_uploader("Upload Resumes (PDF/DOCX)", type=["pdf", "docx"], accept_multiple_files=True)

# ---------- Text Extraction ----------
def extract_text_from_pdf(path):
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

def extract_text_from_docx(path):
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs)

# ---------- Simple Resume Parser ----------
def parse_resume(file_path):
    text = ""
    if file_path.endswith(".pdf"):
        text = extract_text_from_pdf(file_path)
    elif file_path.endswith(".docx"):
        text = extract_text_from_docx(file_path)

    email = re.search(r'[\w\.-]+@[\w\.-]+', text)
    name = text.split("\n")[0] if text else "Unknown"
    skills = [kw for kw in SKILL_KEYWORDS if kw.lower() in text.lower()]
    location = re.search(r'\b(Toronto|Vancouver|New York|San Francisco|London|Delhi|Mumbai)\b', text, re.I)

    return {
        "name": name,
        "email": email.group(0) if email else "",
        "location": location.group(0) if location else "Unknown",
        "skills": list(set(skills)),
        "education": "Bachelor" if "bachelor" in text.lower() else "",
        "experience": 3  # Placeholder
    }

# ---------- Scoring ----------
def score_resume(parsed, job_keywords, min_experience=3):
    skills = parsed["skills"]
    experience = parsed["experience"]
    edu = parsed["education"]

    skills_match = len(set(skills).intersection(set(job_keywords))) / len(job_keywords) * 100 if job_keywords else 0
    exp_score = min((experience / min_experience) * 100, 100)
    edu_score = 100 if edu else 50

    final_score = round((skills_match * 0.5 + exp_score * 0.3 + edu_score * 0.2), 2)
    return final_score, skills_match, exp_score, edu_score

# ---------- Step 3: Analyze ----------
st.header("3️⃣ Analyze Candidates")
results = []

if st.button("🚀 Analyze"):
    if not job_description or not job_title:
        st.warning("Please provide job title and description.")
    elif not resumes:
        st.warning("Please upload at least one resume.")
    else:
        job_keywords = list(set(job_description.lower().split()))
        result_rows = []

        for resume_file in resumes:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf" if resume_file.name.endswith(".pdf") else ".docx") as tmp_file:
                tmp_file.write(resume_file.read())
                tmp_path = tmp_file.name

            try:
                parsed = parse_resume(tmp_path)
                score, skills_pct, exp_pct, edu_pct = score_resume(parsed, job_keywords)
                result_rows.append({
                    "Candidate": parsed["name"],
                    "Email": parsed["email"],
                    "Location": parsed["location"],
                    "Experience (yrs)": parsed["experience"],
                    "Education": parsed["education"],
                    "Skills": ", ".join(parsed["skills"]),
                    "Skill Match %": round(skills_pct, 2),
                    "Experience Score %": round(exp_pct, 2),
                    "Education Score %": round(edu_pct, 2),
                    "OAATS Score": score
                })
            except Exception as e:
                st.error(f"❌ Error parsing {resume_file.name}: {e}")
            finally:
                os.unlink(tmp_path)

        df_result = pd.DataFrame(result_rows)
        st.dataframe(df_result, use_container_width=True)
        st.download_button("📥 Download Results", df_result.to_csv(index=False), "ranked_candidates.csv", "text/csv")
        results = result_rows
