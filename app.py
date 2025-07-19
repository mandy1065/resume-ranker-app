import nltk
import streamlit as st
import pandas as pd
import os
import tempfile
import smtplib
import spacy
import fitz  # PyMuPDF
from docx import Document
from email.mime.text import MIMEText

# Downloads required by NLTK
nltk.download('stopwords')

# Load SpaCy model (must be preinstalled in build)
nlp = spacy.load("en_core_web_sm")

# ---------- Streamlit Setup ----------
st.set_page_config(page_title="AI Resume Ranker", layout="wide")
st.title("🎯 Resume Ranker & Email Tool")

# ---------- Step 1: Paste Job Description ----------
st.header("1️⃣ Paste Job Description")
job_title = st.text_input("Job Title", placeholder="e.g. Data Analyst")
job_description = st.text_area("Paste Job Description", height=200)

# ---------- Step 2: Upload Resumes ----------
st.header("2️⃣ Upload Resumes")
resumes = st.file_uploader("Upload Resumes (PDF/DOCX)", type=["pdf", "docx"], accept_multiple_files=True)

# ---------- Resume Parser ----------
def extract_text(file_path):
    if file_path.endswith(".pdf"):
        doc = fitz.open(file_path)
        return "\n".join([page.get_text() for page in doc])
    elif file_path.endswith(".docx"):
        doc = Document(file_path)
        return "\n".join([p.text for p in doc.paragraphs])
    return ""

def parse_resume(file_path):
    text = extract_text(file_path)
    doc = nlp(text)
    skills = [token.text for token in doc if token.pos_ == "NOUN"]
    return {
        "name": next((ent.text for ent in doc.ents if ent.label_ == "PERSON"), os.path.basename(file_path)),
        "email": next((ent.text for ent in doc.ents if ent.label_ == "EMAIL"), ""),
        "location": next((ent.text for ent in doc.ents if ent.label_ == "GPE"), ""),
        "skills": list(set(skills)),
        "education": [ent.text for ent in doc.ents if ent.label_ == "ORG"],
        "experience": 3  # Placeholder — you can improve this with regex or LLM
    }

# ---------- OAATS Scoring ----------
def score_resume(parsed, job_keywords, min_experience=3):
    skills = parsed.get("skills", [])
    experience = parsed.get("experience", 0)
    education = parsed.get("education", [])

    skills_match = len(set(skills).intersection(set(job_keywords))) / len(job_keywords) * 100 if job_keywords else 0
    exp_score = min((experience / min_experience) * 100, 100)
    edu_score = 100 if education else 50

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
                    "Education": ", ".join(parsed["education"]),
                    "Skills": ", ".join(parsed["skills"]),
                    "Skill Match %": round(skills_pct, 2),
                    "Experience Score %": round(exp_pct, 2),
                    "Education Score %": round(edu_pct, 2),
                    "OAATS Score": score
                })
            except Exception as e:
                st.error(f"❌ Error parsing {
