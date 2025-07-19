import streamlit as st
import pandas as pd
import nltk
import spacy
import fitz  # PyMuPDF
from docx import Document
import tempfile
import os
import smtplib
from email.mime.text import MIMEText

# NLTK setup
nltk.download('stopwords')

# Load SpaCy model
nlp = spacy.load("en_core_web_sm")

# Streamlit UI setup
st.set_page_config(page_title="Resume Ranker", layout="wide")
st.title("🎯 Resume Ranker & Interview Outreach")

# Job description input
st.header("1️⃣ Job Description")
job_title = st.text_input("Job Title")
job_description = st.text_area("Paste the job description", height=200)

# Resume upload
st.header("2️⃣ Upload Resumes")
resumes = st.file_uploader("Upload PDF or DOCX resumes", type=["pdf", "docx"], accept_multiple_files=True)

# Helper functions
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
        "experience": 3  # Placeholder
    }

def score_resume(parsed, job_keywords, min_experience=3):
    skills = parsed.get("skills", [])
    experience = parsed.get("experience", 0)
    education = parsed.get("education", [])

    skills_match = len(set(skills).intersection(set(job_keywords))) / len(job_keywords) * 100 if job_keywords else 0
    exp_score = min((experience / min_experience) * 100, 100)
    edu_score = 100 if education else 50

    final_score = round((skills_match * 0.5 + exp_score * 0.3 + edu_score * 0.2), 2)
    return final_score, skills_match, exp_score, edu_score

# Analyze resumes
st.header("3️⃣ Analyze Candidates")
results = []

if st.button("🚀 Analyze"):
    if not job_description or not job_title:
        st.warning("Please enter a job title and description.")
    elif not resumes:
        st.warning("Please upload at least one resume.")
    else:
        job_keywords = list(set(job_description.lower().split()))
        for resume in resumes:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf" if resume.name.endswith(".pdf") else ".docx") as tmp:
                tmp.write(resume.read())
                tmp_path = tmp.name
            try:
                parsed = parse_resume(tmp_path)
                score, skills_pct, exp_pct, edu_pct = score_resume(parsed, job_keywords)
                results.append({
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
                st.error(f"❌ Error parsing {resume.name}: {e}")
            finally:
                os.unlink(tmp_path)

        df_result = pd.DataFrame(results)
        st.dataframe(df_result)
        st.download_button("📥 Download Results", df_result.to_csv(index=False), "results.csv", "text/csv")

# Email sender
st.header("4️⃣ Send Interview Email")
sender_email = st.text_input("Your Email", placeholder="you@gmail.com")
sender_password = st.text_input("App Password", type="password")
provider = st.selectbox("Email Provider", ["Gmail", "Outlook"])
smtp_server = "smtp.gmail.com" if provider == "Gmail" else "smtp.office365.com"
smtp_port = 587

if results:
    selected = st.selectbox("Select Candidate", [r["Candidate"] for r in results])
    candidate = next(r for r in results if r["Candidate"] == selected)

    default_msg = f"""
Hi {candidate['Candidate']},

Thanks for applying to the {job_title} role.
We’d like to invite you to an interview.

Regards,
[Your Name]
""".strip()

    message = st.text_area("Compose Email", default_msg, height=200)
    if st.button("📤 Send Email"):
        try:
            msg = MIMEText(message)
            msg["Subject"] = f"Interview Invitation - {job_title}"
            msg["From"] = sender_email
            msg["To"] = candidate["Email"]

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, candidate["Email"], msg.as_string())

            st.success(f"✅ Email sent to {candidate['Candidate']} at {candidate['Email']}")
        except Exception as e:
            st.error(f"❌ Failed to send email: {e}")
else:
    st.info("Analyze resumes to enable this feature.")
