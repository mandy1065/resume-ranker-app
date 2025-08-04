# app.py

import os
import re
import tempfile

import pandas as pd
import streamlit as st
from io import StringIO
from PyPDF2 import PdfReader
import docx
from utils.resume_parser import parse_resume  # your existing parser

# -------------------------------------------------------------------
# Skill Extraction Utilities
# -------------------------------------------------------------------
# To align the resume text and job description with the requirements of the
# external API, we extract only the skills (keywords) from both the job
# description and the resumes.  The API will receive these comma‑delimited
# skills strings instead of the full text.

# A small set of common words to exclude when parsing skills.  This list
# eliminates generic connectors and prepositions; you can expand it as needed.
COMMON_WORDS = {
    # Generic stopwords and connectives
    "and", "or", "the", "to", "a", "an", "with", "in", "of", "for",
    "on", "as", "by", "is", "are", "be", "will", "you", "your",
    "we", "our", "they", "their", "it", "this", "that", "from",
    # Generic job posting terms to exclude from skill tokens
    "years", "year", "yrs", "experience", "responsibilities", "responsibility",
    "skills", "requirements", "must", "have", "strong", "solid", "familiar",
    "familiarity", "communication", "problem", "solving", "problem‑solving",
    "team", "summary", "apply"
}

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def extract_job_skills(description: str) -> list:
    """Extract potential skill tokens from a job description.

    This function splits the job description on commas, slashes, whitespace
    and newlines, lowercases each token, strips punctuation, and filters
    out common words.  Duplicate skills are removed while preserving order.
    """
    # Replace various separators with spaces, then split
    tokens = re.split(r"[\s,\n\/\\]+", description.lower())
    clean = []
    seen = set()
    for token in tokens:
        # Remove any surrounding punctuation
        tok = re.sub(r"[^a-zA-Z0-9.+_-]", "", token).strip().strip('.')
        # Skip empty tokens
        if not tok:
            continue
        # Skip tokens containing any digits (to avoid '5+', '3yrs', etc.)
        if re.search(r"\d", tok):
            continue
        # Normalize plus signs (e.g., C++ becomes c++)
        tok_lower = tok.lower()
        if tok_lower in COMMON_WORDS:
            continue
        if tok_lower not in seen:
            clean.append(tok_lower)
            seen.add(tok_lower)
    return clean

def extract_resume_skills(resume_text: str, job_tokens: list) -> list:
    """Return the subset of job_tokens that appear in the resume text.

    Parameters
    ----------
    resume_text : str
        The full text extracted from the resume.
    job_tokens : list
        Tokens extracted from the job description to look for.
    Returns
    -------
    list
        Unique tokens from job_tokens that are present in the resume (order preserved).
    """
    text_lower = resume_text.lower()
    matched = []
    for token in job_tokens:
        if token in text_lower:
            matched.append(token)
    return matched

# -------------------------------------------------------------------
# Additional Feature Extraction Helpers
# -------------------------------------------------------------------
def parse_required_years(description: str) -> int:
    """Extract the first occurrence of a years‑of‑experience requirement from a job description."""
    m = re.search(r"(\d+)\s*(?:\+)?\s*(?:years|yrs)", description.lower())
    return int(m.group(1)) if m else 0

def parse_resume_years(text: str) -> int:
    """Estimate the candidate's experience (in years) from the resume text.

    This function searches for patterns like '5 years' or '3 yrs' and returns
    the maximum value found.  It's a heuristic and may not capture all cases.
    """
    years = [int(num) for num in re.findall(r"(\d+)\s*(?:years|yrs)", text.lower())]
    return max(years) if years else 0

def has_degree(text: str) -> bool:
    """Check if the resume mentions a degree or certification."""
    t = text.lower()
    degree_keywords = [
        "bachelor", "bachelors", "master", "masters", "phd", "associate",
        "degree", "certification", "certificate"
    ]
    return any(keyword in t for keyword in degree_keywords)

# -------------------------------------------------------------------
# Setup & Session State Initialization
# -------------------------------------------------------------------
os.makedirs("data", exist_ok=True)
st.set_page_config(page_title="Recruiter Portal", layout="wide")

# -------------------------------------------------------------------
# External Resume Scoring API Configuration Removed
# -------------------------------------------------------------------
# The earlier version of this application included a call to an external API to
# compute resume scores.  At the user's request, the API integration has been
# removed and the app now evaluates candidates using internal logic based on
# skills extracted from job descriptions and resumes.

# The external resume scoring function has been removed because the API is no
# longer used.  Resume ranking is now handled internally via skill matching.

# Load or init jobs_df
if "jobs_df" not in st.session_state:
    try:
        st.session_state.jobs_df = pd.read_csv("data/jobs.csv")
    except FileNotFoundError:
        st.session_state.jobs_df = pd.DataFrame(
            columns=["Title", "Description", "Location"]
        )
        st.session_state.jobs_df.to_csv("data/jobs.csv", index=False)

# Load or init status_df
if "status_df" not in st.session_state:
    try:
        st.session_state.status_df = pd.read_csv("data/status.csv")
    except FileNotFoundError:
        st.session_state.status_df = pd.DataFrame(
            columns=["Email", "Status", "Job"]
        )
        st.session_state.status_df.to_csv("data/status.csv", index=False)

# -------------------------------------------------------------------
# Sidebar Navigation
# -------------------------------------------------------------------
page = st.sidebar.radio("Go to", [
    "Post Job (Form)",
    "View & Import Jobs",
    "Analyse & Email Candidates",
    "Dashboard"
])

# -------------------------------------------------------------------
# 1) Post Job (Form)
# -------------------------------------------------------------------
if page == "Post Job (Form)":
    st.title("📝 Post One Job Manually")
    with st.form("job_form"):
        title       = st.text_input("Job Title")
        description = st.text_area("Job Description")
        location    = st.text_input("Location")
        submitted   = st.form_submit_button("Add Job")

    if submitted:
        if not title.strip() or not description.strip():
            st.error("Title & Description are required.")
        else:
            new = pd.DataFrame([[title, description, location]],
                               columns=st.session_state.jobs_df.columns)
            st.session_state.jobs_df = pd.concat(
                [st.session_state.jobs_df, new], ignore_index=True
            )
            st.session_state.jobs_df.to_csv("data/jobs.csv", index=False)
            st.success(f"Job '{title}' added!")
            st.experimental_rerun()

# -------------------------------------------------------------------
# 2) View & Import Jobs
# -------------------------------------------------------------------
elif page == "View & Import Jobs":
    st.title("📋 View & Bulk Import Jobs")

    st.subheader("Current Job Postings")
    st.dataframe(st.session_state.jobs_df, use_container_width=True)

    st.markdown("---")
    st.subheader("Bulk Import via Pasted CSV")
    csv_text = st.text_area(
        "Paste CSV here (columns: Title,Description,Location)",
        height=150
    )
    if st.button("Import Pasted CSV"):
        if not csv_text.strip():
            st.error("Please paste valid CSV.")
        else:
            try:
                new_df = pd.read_csv(StringIO(csv_text))
                st.session_state.jobs_df = pd.concat(
                    [st.session_state.jobs_df, new_df], ignore_index=True
                )
                st.session_state.jobs_df.to_csv("data/jobs.csv", index=False)
                st.success(f"Imported {len(new_df)} job(s).")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Could not parse CSV: {e}")

    st.markdown("---")
    st.subheader("Or Upload a CSV File")
    uploaded = st.file_uploader("Upload jobs.csv", type="csv")
    if uploaded:
        df_file = pd.read_csv(uploaded)
        st.session_state.jobs_df = pd.concat(
            [st.session_state.jobs_df, df_file], ignore_index=True
        )
        st.session_state.jobs_df.to_csv("data/jobs.csv", index=False)
        st.success(f"Uploaded {len(df_file)} job(s).")
        st.experimental_rerun()

# -------------------------------------------------------------------
# 3) Analyse & Email Candidates
# -------------------------------------------------------------------
elif page == "Analyse & Email Candidates":
    st.title("🔍 Analyse & Email Candidates")

    if st.session_state.jobs_df.empty:
        st.warning("No jobs found. Please add a job first.")
        st.stop()

    # Select a job
    job_idx = st.selectbox(
        "Select a job to analyse",
        st.session_state.jobs_df.index,
        format_func=lambda i: st.session_state.jobs_df.at[i, "Title"]
    )
    job = st.session_state.jobs_df.loc[job_idx]
    st.write("**Description:**", job["Description"])
    st.write("**Location:**", job["Location"])
    st.markdown("---")


    # Recruiter-defined skills and weights with dynamic fields
    st.subheader("Define Key Skills & Weights (Optional)")
    st.write("Enter each skill and assign a weight from 1 (least important) to 10 (most important). "
             "Use the 'Add Skill' button to add more skills. Weights will be normalized automatically.")

    # Initialize dynamic skill list in session state
    if "skills_list" not in st.session_state:
        st.session_state.skills_list = [{"skill": "", "weight": 1}]

    # Display input rows for each skill
    for idx, entry in enumerate(st.session_state.skills_list):
        cols = st.columns([4, 1])
        entry["skill"] = cols[0].text_input(
            f"Skill {idx+1}", value=entry["skill"], key=f"skill_{idx}"
        )
        entry["weight"] = cols[1].number_input(
            f"Weight {idx+1}", min_value=1, max_value=10, value=entry["weight"], key=f"weight_{idx}"
        )

    # Button to add another skill
    if st.button("Add Skill"):
        st.session_state.skills_list.append({"skill": "", "weight": 1})

    # Input for required years of experience
    required_exp_input = st.number_input(
        "Required years of experience (optional)", min_value=0, max_value=50, value=0, step=1, key="req_exp"
    )

    # Upload resumes
    files = st.file_uploader(
        "Upload multiple resumes",
        type=["pdf", "docx"],
        accept_multiple_files=True
    )

    # Analyse in a form so uploader state persists
    if files:
        with st.form("analyse_form", clear_on_submit=False):
            analyse_btn = st.form_submit_button("Analyse Resumes")
            if analyse_btn:
                # Parse each uploaded resume file to extract name, email and text
                parsed = [parse_resume(f) for f in files]
                df = pd.DataFrame(parsed)
                # Extract the set of skills from the selected job description
                job_tokens = extract_job_skills(job["Description"])
                # Determine which of the job skills appear in each resume
                df["Matched Skills"] = df.apply(
                    lambda row: extract_resume_skills(row["Resume Text"], job_tokens), axis=1
                )

                # Retrieve recruiter-defined skills and weights from session state
                user_skills = []
                user_weights = []
                for entry in st.session_state.skills_list:
                    if entry.get("skill"):
                        user_skills.append(entry["skill"].strip().lower())
                        user_weights.append(float(entry.get("weight", 1)))

                # Normalize weights if any skills provided
                if user_skills:
                    total_w = sum(user_weights)
                    user_weights = [w / total_w for w in user_weights]

                # If recruiter provided skills, compute weighted skill scores and rank accordingly
                if user_skills:
                    weighted_scores = []
                    matched_user_skills = []
                    for _, row in df.iterrows():
                        resume_lower = row["Resume Text"].lower()
                        score = 0.0
                        matched = []
                        for skill, weight in zip(user_skills, user_weights):
                            if skill and skill in resume_lower:
                                score += weight
                                matched.append(skill)
                        weighted_scores.append(score)
                        matched_user_skills.append(matched)
                    df["Score"] = weighted_scores
                    df["Matched Skills"] = matched_user_skills
                    df["Analysis"] = [
                        (
                            f"Weighted skill hits: {len(matched)}/{len(user_skills)} | "
                            f"Skills: {', '.join(matched)}"
                            if matched else
                            f"Weighted skill hits: 0/{len(user_skills)}"
                        )
                        for matched in matched_user_skills
                    ]
                    df = df.sort_values("Score", ascending=False)
                    st.session_state.analysis_df = df
                else:
                    # No recruiter-defined skills; use composite scoring based on job description
                    with st.spinner("Evaluating candidates..."):
                        scores = []
                        analyses = []
                        # Use recruiter-specified required years if provided
                        if required_exp_input > 0:
                            required_years = int(required_exp_input)
                        else:
                            required_years = parse_required_years(job["Description"])
                        job_requires_degree = any(word in job["Description"].lower() for word in ["bachelor", "master", "degree", "certification"])
                        # Semantic similarity: job description vs resumes
                        docs_semantic = [job["Description"]] + df["Resume Text"].tolist()
                        vectorizer_sem = TfidfVectorizer(stop_words="english")
                        tfidf_sem = vectorizer_sem.fit_transform(docs_semantic)
                        sem_job_vec = tfidf_sem[0]
                        sem_resume_vecs = tfidf_sem[1:]
                        sem_similarities = cosine_similarity(sem_job_vec, sem_resume_vecs)[0]
                        # Title similarity: job title vs resumes
                        docs_title = [job["Title"]] + df["Resume Text"].tolist()
                        vectorizer_title = TfidfVectorizer(stop_words="english")
                        tfidf_title = vectorizer_title.fit_transform(docs_title)
                        title_job_vec = tfidf_title[0]
                        title_resume_vecs = tfidf_title[1:]
                        title_similarities = cosine_similarity(title_job_vec, title_resume_vecs)[0]
                        for idx, (_, row) in enumerate(df.iterrows()):
                            matched_skills = row["Matched Skills"]
                            skill_ratio = (len(matched_skills) / len(job_tokens)) if job_tokens else 0.0
                            semantic_sim = float(sem_similarities[idx])
                            title_sim = float(title_similarities[idx])
                            candidate_years = parse_resume_years(row["Resume Text"])
                            if required_years > 0:
                                experience_ratio = min(candidate_years / required_years, 1.0)
                            else:
                                experience_ratio = 1.0
                            candidate_has_degree = has_degree(row["Resume Text"])
                            if job_requires_degree:
                                education_match = 1.0 if candidate_has_degree else 0.0
                            else:
                                education_match = 1.0
                            score = (
                                0.40 * skill_ratio +
                                0.20 * semantic_sim +
                                0.15 * experience_ratio +
                                0.10 * title_sim +
                                0.10 * education_match +
                                0.05 * 1.0
                            )
                            scores.append(score)
                            analysis_parts = [
                                f"Skills matched: {len(matched_skills)}/{len(job_tokens)}",
                                f"Semantic sim: {semantic_sim:.2f}",
                                f"Title sim: {title_sim:.2f}",
                                f"Experience: {candidate_years}/{required_years if required_years else 'n/a'}",
                                f"Degree match: {'Y' if candidate_has_degree else 'N'}"
                            ]
                            if matched_skills:
                                analysis_parts.append(f"Matched skills: {', '.join(matched_skills)}")
                            analyses.append(" | ".join(analysis_parts))
                        df["Score"] = scores
                        df["Analysis"] = analyses
                        df = df.sort_values("Score", ascending=False)
                        st.session_state.analysis_df = df

    # Show ranking & send requests
    if "analysis_df" in st.session_state:
        df = st.session_state.analysis_df
        st.subheader("Ranked Candidates")
        st.dataframe(
            df[["Name", "Email", "Score", "Matched Skills", "Analysis"]],
            use_container_width=True
        )

        to_request = st.multiselect(
            "Select candidates to send interview requests",
            options=df["Email"].tolist()
        )
        if st.button("Send Interview Requests", key="send_requests"):
            new_rows = [
                [email, "Interview Requested", job["Title"]]
                for email in to_request
            ]
            if new_rows:
                updated = pd.concat([
                    st.session_state.status_df,
                    pd.DataFrame(new_rows, columns=st.session_state.status_df.columns)
                ], ignore_index=True)
                st.session_state.status_df = updated
                st.session_state.status_df.to_csv("data/status.csv", index=False)
            st.success(f"Marked {len(new_rows)} candidate(s) for '{job['Title']}'")
            del st.session_state["analysis_df"]

# -------------------------------------------------------------------
# 4) Dashboard
# -------------------------------------------------------------------
elif page == "Dashboard":
    st.title("📊 Candidate Status Dashboard")
    df = st.session_state.status_df

    if df.empty:
        st.info("No candidates tracked yet.")
    else:
        st.dataframe(df, use_container_width=True)
        st.markdown("---")
        st.subheader("Update Candidate Status")

        with st.form("update_status_form", clear_on_submit=False):
            email_to_update = st.selectbox(
                "Pick candidate",
                options=df["Email"].unique()
            )
            new_status = st.selectbox(
                "New status",
                options=["Interview Requested", "Rejected", "Accepted"]
            )
            submitted = st.form_submit_button("Update Status")

            if submitted:
                # Persist the status change
                st.session_state.status_df.loc[
                    st.session_state.status_df["Email"] == email_to_update,
                    "Status"
                ] = new_status
                st.session_state.status_df.to_csv("data/status.csv", index=False)
                st.success(f"{email_to_update} updated to {new_status}!")
                # Force a rerun so the updated table appears immediately
                st.experimental_rerun()

# --- Resume Chatbot Assistant Feature ---
import openai

st.markdown("## 🤖 Resume Chat Assistant")

openai.api_key = st.secrets.get("openai_api_key", None)
if not openai.api_key:
    st.warning("⚠️ Please set your OpenAI API key in `.streamlit/secrets.toml` as `openai_api_key = 'your-key'`")

resume_chat_text = st.text_area("📄 Paste Resume Text", height=250)
jd_chat_text = st.text_area("🧾 Job Description (Optional)", height=150)

if st.button("Analyze Resume with ChatGPT"):
    if not resume_chat_text.strip():
        st.error("Please paste a resume.")
    else:
        st.subheader("📋 Resume Summary")
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a recruiter assistant analyzing resumes."},
                    {"role": "user", "content": f"Resume:\n{resume_chat_text}\n\nJob Description:\n{jd_chat_text}\n\nPlease give a professional summary."}
                ]
            )
            st.markdown(response.choices[0].message["content"])
        except Exception as e:
            st.error(f"OpenAI error: {e}")

    st.subheader("💬 Resume Q&A")
    question = st.text_input("Ask about this resume")
    if question:
        try:
            qa_response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You answer recruiter questions based on a resume."},
                    {"role": "user", "content": f"Resume:\n{resume_chat_text}"},
                    {"role": "user", "content": f"Question: {question}"}
                ]
            )
            st.markdown(f"**Answer:** {qa_response.choices[0].message['content']}")
        except Exception as e:
            st.error(f"OpenAI error: {e}")
