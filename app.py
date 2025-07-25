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
# Setup & Session State Initialization
# -------------------------------------------------------------------
os.makedirs("data", exist_ok=True)
st.set_page_config(page_title="Recruiter Portal", layout="wide")

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
                parsed = [parse_resume(f) for f in files]
                df = pd.DataFrame(parsed)
                keywords = set(job["Description"].lower().split())
                df["Score"] = df["Resume Text"].apply(
                    lambda txt: sum(txt.lower().count(k) for k in keywords)
                )
                df["Matched Keywords"] = df["Resume Text"].apply(
                    lambda txt: [k for k in keywords if k in txt.lower()]
                )
                df = df.sort_values("Score", ascending=False)
                st.session_state.analysis_df = df

    # Show ranking & send requests
    if "analysis_df" in st.session_state:
        df = st.session_state.analysis_df
        st.subheader("Ranked Candidates")
        st.dataframe(
            df[["Name", "Email", "Score", "Matched Keywords"]],
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
                st.session_state.status_df.loc[
                    st.session_state.status_df["Email"] == email_to_update,
                    "Status"
                ] = new_status
                st.session_state.status_df.to_csv("data/status.csv", index=False)
                st.success(f"{email_to_update} updated to {new_status}!")
