import nltk
import streamlit as st
import pandas as pd
import os
import tempfile
import smtplib
from docx import Document
from email.mime.text import MIMEText
from fuzzywuzzy import fuzz

nltk.download('stopwords')

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
        import fitz
        doc = fitz.open(file_path)
        return "\n".join([page.get_text() for page in doc])
    elif file_path.endswith(".docx"):
        doc = Document(file_path)
        return "\n".join([p.text for p in doc.paragraphs])
    return ""

def parse_resume(file_path):
    text = extract_text(file_path)
    lines = text.split("\n")
    name = lines[0].strip() if lines else os.path.basename(file_path)
    email = next((line for line in lines if "@" in line and "." in line), "")
    location = ""  # Could be improved with regex or LLM
    skills = [word.strip().lower() for word in text.split() if len(word) > 2]
    education = next((line for line in lines if "Bachelor" in line or "B.Tech" in line), "")
    experience = 3  # Placeholder

    return {
        "name": name,
        "email": email,
        "location": location,
        "skills": list(set(skills)),
        "education": education,
        "experience": experience
    }

# ---------- Improved OAATS Scoring ----------
def score_resume(parsed, job_keywords, min_experience=3):
    skills = parsed.get("skills", [])
    experience = parsed.get("experience", 0)
    education = parsed.get("education", "")

    skills = [s.lower() for s in skills]
    job_keywords = [k.lower() for k in job_keywords]

    match_score = 0
    for skill in skills:
        for keyword in job_keywords:
            if fuzz.partial_ratio(skill, keyword) > 80:
                match_score += 1
                break

    skills_match_pct = (match_score / len(job_keywords)) * 100 if job_keywords else 0
    exp_score = min((experience / min_experience) * 100, 100)
    edu_score = 100 if "bachelor" in education.lower() or "b.tech" in education.lower() else 50

    final_score = round((skills_match_pct * 0.6 + exp_score * 0.25 + edu_score * 0.15), 2)
    return final_score, skills_match_pct, exp_score, edu_score

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

# ---------- Step 4: Send Email ----------
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
