import streamlit as st
import pandas as pd
import os
import tempfile
import requests

# ---------- Streamlit Setup ----------
st.set_page_config(page_title="Resume Ranker - BrainyScout API", layout="wide")
st.title("🤖 Resume Ranker with BrainyScout API")

# ---------- Step 1: Paste Job Description ----------
st.header("1️⃣ Paste Job Description")
job_title = st.text_input("Job Title", placeholder="e.g. Data Analyst")
job_description = st.text_area("Paste Job Description", height=200)

# ---------- Step 2: Upload Resumes ----------
st.header("2️⃣ Upload Resumes")
resumes = st.file_uploader("Upload Resumes (TXT format preferred)", type=["txt"], accept_multiple_files=True)

# ---------- API Function ----------
API_URL = "https://brainyscout.com/api/rscore"

def parse_resume_via_brainyscout(resume_text, job_description):
    data = {
        "resume": resume_text,
        "jobDescription": job_description,
        "email": "test@example.com"  # Required dummy email
    }
    response = requests.post(API_URL, data=data)
    response.raise_for_status()
    return response.json()

# ---------- Step 3: Analyze Candidates ----------
st.header("3️⃣ Analyze Candidates")
results = []

if st.button("🚀 Analyze"):
    if not job_description or not job_title:
        st.warning("Please provide job title and description.")
    elif not resumes:
        st.warning("Please upload at least one resume.")
    else:
        result_rows = []

        for resume_file in resumes:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp_file:
                tmp_file.write(resume_file.read())
                tmp_path = tmp_file.name

            with open(tmp_path, "r", encoding="utf-8", errors="ignore") as f:
                resume_text = f.read()

            try:
                response_data = parse_resume_via_brainyscout(resume_text, job_description)
                score = response_data.get("OverallScore", 0)
                soft_score = response_data.get("SoftSkillScore", 0)
                hard_score = response_data.get("HardSkillScore", 0)
                matched_skills = response_data.get("ResumeMatchedHardSkills", "").split(",") + \
                                 response_data.get("ResumeMatchedSoftSkills", "").split(",")

                result_rows.append({
                    "Candidate": resume_file.name,
                    "Matched Hard Skills": response_data.get("ResumeMatchedHardSkills", ""),
                    "Matched Soft Skills": response_data.get("ResumeMatchedSoftSkills", ""),
                    "Skill Match %": round((soft_score + hard_score) / 2, 2),
                    "OAATS Score": round(score, 2)
                })

            except Exception as e:
                st.error(f"❌ Error parsing {resume_file.name}: {e}")
            finally:
                os.unlink(tmp_path)

        df_result = pd.DataFrame(result_rows)
        st.dataframe(df_result, use_container_width=True)
        st.download_button("📥 Download Results", df_result.to_csv(index=False), "ranked_candidates.csv", "text/csv")
