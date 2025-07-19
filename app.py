import streamlit as st
import pandas as pd
import os
import tempfile
import smtplib
from email.mime.text import MIMEText
from pyresparser import ResumeParser

# ---------- Streamlit Setup ----------
st.set_page_config(page_title="AI Resume Ranker", layout="wide")
st.title("🎯 End-to-End Talent Evaluation & Interview Outreach Tool")

# ---------- Step 1: Upload Job Descriptions ----------
st.header("1️⃣ Upload Job Descriptions")
job_files = st.file_uploader("Upload Job Descriptions (TXT format)", type=["txt"], accept_multiple_files=True)

job_map = {}
for job_file in job_files:
    job_text = job_file.read().decode("utf-8")
    job_title = job_file.name.replace(".txt", "")
    job_map[job_title] = {"description": job_text, "resumes": []}

# ---------- Step 2: Upload Resumes for Each Job ----------
st.header("2️⃣ Upload Resumes for Each Job")
for job_title in job_map:
    st.subheader(f"📌 {job_title}")
    resumes = st.file_uploader(f"Upload resumes for '{job_title}'", type=["pdf", "docx"], accept_multiple_files=True, key=job_title)
    job_map[job_title]["resumes"] = resumes

# ---------- Helper: OAATS Scoring ----------
def score_resume(parsed, job_keywords, min_experience=3):
    skills = parsed.get("skills", [])
    education = parsed.get("education", [])
    experience = parsed.get("total_experience", 0)

    skills_match = len(set(skills).intersection(set(job_keywords))) / len(job_keywords) * 100 if job_keywords else 0
    exp_score = min((experience / min_experience) * 100, 100) if min_experience > 0 else 0
    edu_score = 100 if any("bachelor" in e.lower() or "b.tech" in e.lower() for e in education) else 50

    final_score = round((skills_match * 0.5 + exp_score * 0.3 + edu_score * 0.2), 2)
    return final_score, skills_match, exp_score, edu_score

# ---------- Step 3: Analyze Resumes ----------
st.header("3️⃣ Analyze & Rank Candidates")
all_results = []
if st.button("🚀 Analyze All"):
    for job_title, job_data in job_map.items():
        resumes = job_data["resumes"]
        if not resumes:
            continue
        st.markdown(f"### 🧾 Results for: {job_title}")
        job_keywords = list(set(job_data["description"].lower().split()))

        result_rows = []
        for resume_file in resumes:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf" if resume_file.name.endswith(".pdf") else ".docx") as tmp_file:
                tmp_file.write(resume_file.read())
                tmp_path = tmp_file.name

            try:
                parsed = ResumeParser(tmp_path).get_extracted_data()
                score, skills_pct, exp_pct, edu_pct = score_resume(parsed, job_keywords)
                result_rows.append({
                    "Job Title": job_title,
                    "Candidate": parsed.get("name", resume_file.name),
                    "Email": parsed.get("email", ""),
                    "Location": parsed.get("location", ""),
                    "Experience (yrs)": parsed.get("total_experience", 0),
                    "Education": ", ".join(parsed.get("education", [])),
                    "Skills": ", ".join(parsed.get("skills", [])),
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
        st.download_button(f"📥 Download {job_title} Results", df_result.to_csv(index=False), f"{job_title}_results.csv", "text/csv")
        all_results.extend(result_rows)

# ---------- Step 4: Send Email ----------
st.header("4️⃣ Interview Email Sender")
sender_email = st.text_input("Your Email Address", placeholder="you@gmail.com")
sender_password = st.text_input("App Password (Gmail/Outlook)", type="password")
email_provider = st.selectbox("Email Provider", ["Gmail", "Outlook"])

smtp_server = "smtp.gmail.com" if email_provider == "Gmail" else "smtp.office365.com"
smtp_port = 587

if all_results:
    df_all = pd.DataFrame(all_results)
    selected_name = st.selectbox("Select Candidate to Email", df_all["Candidate"].unique())
    candidate_row = df_all[df_all["Candidate"] == selected_name].iloc[0]

    st.subheader("📨 Compose Interview Message")
    default_message = f"""
Hi {candidate_row['Candidate']},

Thank you for applying for the {candidate_row['Job Title']} position.

We’d like to invite you to the next round of interviews. Please let us know your availability this week.

Best regards,  
[Your Name]
    """.strip()

    email_body = st.text_area("Email Body", value=default_message, height=200)

    if st.button("📤 Send Email"):
        try:
            msg = MIMEText(email_body)
            msg["Subject"] = f"Interview Invitation - {candidate_row['Job Title']}"
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
