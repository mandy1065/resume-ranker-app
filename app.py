import nltk
import streamlit as st
import pandas as pd
import os
import tempfile
import smtplib
from email.mime.text import MIMEText
from docx import Document
import fitz  # PyMuPDF
from nltk.corpus import stopwords

nltk.download('stopwords')
stop_words = set(stopwords.words('english'))

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

# ---------- Skill Extractor from Job Description ----------
def extract_job_skills(description):
    words = [word.strip().lower() for word in description.split() if word.lower() not in stop_words and word.isalpha() and len(word) > 2]
    return list(set(words))

# ---------- Resume Text Extraction ----------
def extract_text(file_path):
    if file_path.endswith(".pdf"):
        doc = fitz.open(file_path)
        return "\n".join([page.get_text() for page in doc])
    elif file_path.endswith(".docx"):
        doc = Document(file_path)
        return "\n".join([p.text for p in doc.paragraphs])
    return ""

# ---------- Parse Resume ----------
def parse_resume(file_path):
    text = extract_text(file_path).lower()
    tokens = [word for word in text.split() if word.isalpha() and len(word) > 2 and word not in stop_words]
    skills = list(set(tokens))
    return {
        "name": os.path.basename(file_path),
        "email": "",
        "location": "",
        "skills": skills,
        "education": [],
        "experience": 3  # Placeholder
    }

# ---------- OAATS Scoring ----------
def score_resume(parsed, job_skills, min_experience=3):
    resume_skills = set(parsed.get("skills", []))
    experience = parsed.get("experience", 0)
    education = parsed.get("education", [])

    matched_skills = resume_skills.intersection(set(job_skills))
    skills_match = (len(matched_skills) / len(job_skills)) * 100 if job_skills else 0
    exp_score = min((experience / min_experience) * 100, 100)
    edu_score = 100 if education else 50

    final_score = round((skills_match * 0.6 + exp_score * 0.25 + edu_score * 0.15), 2)
    return final_score, skills_match, exp_score, edu_score, matched_skills

# ---------- Step 3: Analyze Candidates ----------
st.header("3️⃣ Analyze Candidates")
results = []

if st.button("🚀 Analyze"):
    if not job_description or not job_title:
        st.warning("Please provide job title and description.")
    elif not resumes:
        st.warning("Please upload at least one resume.")
    else:
        job_skills = extract_job_skills(job_description)
        result_rows = []

        for resume_file in resumes:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf" if resume_file.name.endswith(".pdf") else ".docx") as tmp_file:
                tmp_file.write(resume_file.read())
                tmp_path = tmp_file.name

            try:
                parsed = parse_resume(tmp_path)
                score, skills_pct, exp_pct, edu_pct, matched_skills = score_resume(parsed, job_skills)
                result_rows.append({
                    "Candidate": parsed["name"],
                    "Email": parsed["email"],
                    "Location": parsed["location"],
                    "Experience (yrs)": parsed["experience"],
                    "Matched Skills": ", ".join(matched_skills),
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

# ---------- Step 4: Email Sender ----------
st.header("4️⃣ Interview Email Sender")
sender_email = st.text_input("Your Email Address", placeholder="you@gmail.com")
sender_password = st.text_input("App Password (Gmail/Outlook)", type="password")
email_provider = st.selectbox("Email Provider", ["Gmail", "Outlook"])

smtp_server = "smtp.gmail.com" if email_provider == "Gmail" else "smtp.office365.com"
smtp_port = 587

if results:
    df_all = pd.DataFrame(results)
    selected_name = st.selectbox("Select Candidate to Email", df_all["Candidate"].unique())
    candidate_row = df_all[df_all["Candidate"] == selected_name].iloc[0]

    st.subheader("📨 Compose Interview Message")
    default_message = f"""
Hi {candidate_row['Candidate']},

Thank you for applying for the {job_title} position.

We’d like to invite you to the next round of interviews. Please let us know your availability this week.

Best regards,  
[Your Name]
""".strip()

    email_body = st.text_area("Email Body", value=default_message, height=200)

    if st.button("📤 Send Email"):
        try:
            msg = MIMEText(email_body)
            msg["Subject"] = f"Interview Invitation - {job_title}"
            msg["From"] = sender_email
            msg["To"] = candidate_row["Email"]

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, candidate_row["Email"], msg.as_string())

            st.success(f"✅ Email sent to {candidate_row['Candidate']} at {candidate_row['Email']}")
        except Exception as e:
            st.error(f"❌ Failed to send email: {e}")
else:
    st.info("Please analyze resumes first to enable email feature.")
