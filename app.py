# app.py

import os
import streamlit as st
import pandas as pd
from io import StringIO
from utils.resume_parser import parse_resume

# -------------------------------------------------------------------
# — Boilerplate: load jobs & status_df into session_state once
# -------------------------------------------------------------------
os.makedirs("data", exist_ok=True)
st.set_page_config(page_title="Recruiter Portal", layout="wide")

if "jobs_df" not in st.session_state:
    try:
        st.session_state.jobs_df = pd.read_csv("data/jobs.csv")
    except FileNotFoundError:
        st.session_state.jobs_df = pd.DataFrame(
            columns=["Title", "Description", "Location"]
        )
        st.session_state.jobs_df.to_csv("data/jobs.csv", index=False)

if "status_df" not in st.session_state:
    try:
        st.session_state.status_df = pd.read_csv("data/status.csv")
    except FileNotFoundError:
        st.session_state.status_df = pd.DataFrame(
            columns=["Email", "Status", "Job"]
        )
        st.session_state.status_df.to_csv("data/status.csv", index=False)

# -------------------------------------------------------------------
# — Sidebar & Pages
# -------------------------------------------------------------------
page = st.sidebar.radio("Go to", [
    "Post Job (Form)",
    "View & Import Jobs",
    "Analyse & Email Candidates",
    "Dashboard"
])

# … your existing “Post Job” and “View & Import Jobs” code stays exactly the same …

# -------------------------------------------------------------------
# 3) Analyse & Email Candidates
# -------------------------------------------------------------------
elif page == "Analyse & Email Candidates":
    st.title("🔍 Analyse & Email Candidates")

    if st.session_state.jobs_df.empty:
        st.warning("No jobs found. Please add a job first.")
        st.stop()

    # 3.1 Select a job
    job_idx = st.selectbox(
        "Select a job to analyse",
        st.session_state.jobs_df.index,
        format_func=lambda i: st.session_state.jobs_df.at[i, "Title"]
    )
    job = st.session_state.jobs_df.loc[job_idx]

    st.write("**Description:**", job["Description"])
    st.write("**Location:**", job["Location"])
    st.markdown("---")

    # 3.2 Upload resumes (this state survives because we use a form below)
    files = st.file_uploader(
        "Upload multiple resumes", type=["pdf", "docx"], accept_multiple_files=True
    )

    # 3.3 Analyse form
    if files:
        with st.form("analyse_form", clear_on_submit=False):
            analyse_btn = st.form_submit_button("Analyse Resumes")
            if analyse_btn:
                parsed = [parse_resume(f) for f in files]
                df = pd.DataFrame(parsed)

                # compute keyword-match score
                keywords = set(job["Description"].lower().split())
                df["Score"] = df["Resume Text"].apply(
                    lambda txt: sum(txt.lower().count(k) for k in keywords)
                )
                df["Matched Keywords"] = df["Resume Text"].apply(
                    lambda txt: [k for k in keywords if k in txt.lower()]
                )
                df = df.sort_values("Score", ascending=False)

                # store into session_state so it survives rerun
                st.session_state["analysis_df"] = df

    # 3.4 If we have an analysis_df, show it + allow sending requests
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
            # update status_df in session_state
            new_rows = []
            for email in to_request:
                new_rows.append([email, "Interview Requested", job["Title"]])

            if new_rows:
                updated = pd.concat([
                    st.session_state.status_df,
                    pd.DataFrame(new_rows, columns=st.session_state.status_df.columns)
                ], ignore_index=True)

                st.session_state.status_df = updated
                st.session_state.status_df.to_csv("data/status.csv", index=False)

            st.success(f"Marked {len(new_rows)} candidates for '{job['Title']}'")
            # clear the analysis_df so UI resets
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
        email_to_update = st.selectbox("Pick candidate", df["Email"].unique())
        new_status = st.selectbox(
            "New status", ["Interview Requested", "Rejected", "Accepted"]
        )
        if st.button("Update Status"):
            df.loc[df["Email"] == email_to_update, "Status"] = new_status
            st.session_state.status_df = df
            df.to_csv("data/status.csv", index=False)
            st.success("Status updated!")

