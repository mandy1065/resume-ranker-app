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

# Third party library for making HTTP requests
# We import requests here rather than at the top‑level within a function so that
# the library is only required when the API integration is used.  If you
# haven't already, ensure `requests` is listed in your requirements.txt.
import requests
from requests.auth import HTTPBasicAuth

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
    "and", "or", "the", "to", "a", "an", "with", "in", "of", "for",
    "on", "as", "by", "is", "are", "be", "will", "you", "your",
    "we", "our", "they", "their", "it", "this", "that", "from"
}

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
        tok = re.sub(r"[^a-zA-Z0-9.+_-]", "", token).strip()
        if not tok or tok in COMMON_WORDS:
            continue
        if tok not in seen:
            clean.append(tok)
            seen.add(tok)
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
# Setup & Session State Initialization
# -------------------------------------------------------------------
os.makedirs("data", exist_ok=True)
st.set_page_config(page_title="Recruiter Portal", layout="wide")

# -------------------------------------------------------------------
# External Resume Scoring API Configuration
# -------------------------------------------------------------------
# This application can optionally call an external API to score each resume.
# The endpoint expects a JSON body with the candidate's resume text, the
# job description, and the candidate email.  Basic authentication is used to
# protect the endpoint.  Credentials should be provided via environment
# variables (API_USERNAME and API_PASSWORD) to avoid hard‑coding secrets.
#
# If the API credentials are not configured, the app will fall back to the
# internal keyword matching logic defined later in the "Analyse & Email
# Candidates" section.
API_URL = os.environ.get("RANKER_API_URL", "https://brainyscout.com/api/rscore")
# Use a pre‑encoded Basic auth token for API authentication.  The token below
# has been provided directly by the user and will be sent in the
# Authorization header.  If you wish to override it with an environment
# variable, set API_AUTH_TOKEN in your environment.
API_AUTH_TOKEN = os.environ.get("API_AUTH_TOKEN", "xHw1vCqkEUwerwerwe")
API_USERNAME = None  # Not used when a token is provided
API_PASSWORD = None  # Not used when a token is provided

def get_resume_score_via_api(resume_text: str, job_description: str, email: str) -> float:
    """
    Call an external resume scoring API with the provided details.

    Parameters
    ----------
    resume_text : str
        The full text extracted from a candidate's resume.
    job_description : str
        The job description for which resumes are being evaluated.
    email : str
        Candidate's email address (used by the API; may be optional depending on implementation).

    Returns
    -------
    float
        The score returned by the API.  If the API fails or does not
        provide a score, 0.0 is returned.
    """
    # Construct payload according to API specification
    payload = {
        "resume": resume_text,
        "jobDescription": job_description,
        "email": email,
    }
    # Prepare authentication.  If a pre‑encoded token is provided, use it in
    # the Authorization header.  Otherwise, fall back to HTTPBasicAuth when
    # username and password are available.  If no credentials are supplied, the
    # request is sent without an Authorization header.
    auth = None
    headers = {}
    if API_AUTH_TOKEN:
        headers["Authorization"] = f"Basic {API_AUTH_TOKEN}"
    elif API_USERNAME and API_PASSWORD:
        auth = HTTPBasicAuth(API_USERNAME, API_PASSWORD)
    try:
        response = requests.post(API_URL, json=payload, auth=auth, headers=headers or None, timeout=30)
        response.raise_for_status()
        data = response.json()
        # The API might return different field names for the score.  Try common ones.
        for key in ["score", "rscore", "resumeScore", "ResumeScore"]:
            if key in data:
                return float(data[key])
    except Exception as e:
        # Log to the console for debugging; the UI will continue gracefully.
        print(f"Error calling resume score API: {e}")
    return 0.0

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
                job_skills_str = ",".join(job_tokens)
                # Determine which of the job skills appear in each resume
                df["Matched Skills"] = df.apply(
                    lambda row: extract_resume_skills(row["Resume Text"], job_tokens), axis=1
                )
                # Score resumes using external API; fallback to keyword frequency
                with st.spinner("Scoring resumes via API..."):
                    scores = []
                    for _, row in df.iterrows():
                        resume_skills_str = ",".join(row["Matched Skills"]) if row["Matched Skills"] else ""
                        # Call external scoring API using only skills strings
                        api_score = get_resume_score_via_api(
                            resume_text=resume_skills_str,
                            job_description=job_skills_str,
                            email=row["Email"]
                        )
                        # If the API returns a falsy value (0, None, etc.),
                        # fall back to counting occurrences of skills in the resume
                        if api_score:
                            scores.append(api_score)
                        else:
                            fallback = sum(row["Resume Text"].lower().count(tok) for tok in job_tokens)
                            scores.append(fallback)
                df["Score"] = scores
                # Sort candidates by score descending
                df = df.sort_values("Score", ascending=False)
                st.session_state.analysis_df = df

    # Show ranking & send requests
    if "analysis_df" in st.session_state:
        df = st.session_state.analysis_df
        st.subheader("Ranked Candidates")
        st.dataframe(
            df[["Name", "Email", "Score", "Matched Skills"]],
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
