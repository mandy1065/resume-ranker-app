import os
import streamlit as st
import pandas as pd
from io import StringIO
from utils.resume_parser import parse_resume


# Ensure the data directory exists
os.makedirs("data", exist_ok=True)


st.set_page_config(page_title="Recruiter Portal", layout="wide")

# — Load or initialize data —
try:
    jobs_df = pd.read_csv("data/jobs.csv")
except FileNotFoundError:
    jobs_df = pd.DataFrame(columns=["Title", "Description", "Location"])
    jobs_df.to_csv("data/jobs.csv", index=False)

try:
    status_df = pd.read_csv("data/status.csv")
except FileNotFoundError:
    status_df = pd.DataFrame(columns=["Email", "Status"])
    status_df.to_csv("data/status.csv", index=False)

# — Sidebar navigation —
st.sidebar.title("Recruiter Portal")
page = st.sidebar.radio("Go to", [
    "Post Job (Form)",
    "View & Import Jobs",
    "Analyse & Email Candidates",
    "Dashboard"
])

# -------------------------------------------------------------------------------
# 1) Post a single job via form
# -------------------------------------------------------------------------------
if page == "Post Job (Form)":
    st.title("📝 Post One Job Manually")
    with st.form("job_form"):
        title       = st.text_input("Job Title")
        description = st.text_area("Job Description")
        location    = st.text_input("Location")
        submitted   = st.form_submit_button("Add Job")

    if submitted:
        if not title.strip() or not description.strip():
            st.error("Title & description are required.")
        else:
            new = pd.DataFrame([[title, description, location]],
                               columns=jobs_df.columns)
            jobs_df = pd.concat([jobs_df, new], ignore_index=True)
            jobs_df.to_csv("data/jobs.csv", index=False)
            st.success(f"Job `{title}` added!")
            st.experimental_rerun()

# -------------------------------------------------------------------------------
# 2) View existing jobs and bulk-import via CSV
# -------------------------------------------------------------------------------
elif page == "View & Import Jobs":
    st.title("📋 View & Bulk Import Jobs")

    st.subheader("Current Job Postings")
    st.dataframe(jobs_df, use_container_width=True)

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
                jobs_df = pd.concat([jobs_df, new_df], ignore_index=True)
                jobs_df.to_csv("data/jobs.csv", index=False)
                st.success(f"Imported {len(new_df)} job(s).")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Could not parse CSV: {e}")

    st.markdown("---")
    st.subheader("Or Upload a CSV File")
    uploaded = st.file_uploader("Upload jobs.csv", type="csv")
    if uploaded:
        df_file = pd.read_csv(uploaded)
        jobs_df = pd.concat([jobs_df, df_file], ignore_index=True)
        jobs_df.to_csv("data/jobs.csv", index=False)
        st.success(f"Uploaded {len(df_file)} job(s).")
        st.experimental_rerun()

# -------------------------------------------------------------------------------
# 3) Analyse resumes against a selected job, rank, and email
# -------------------------------------------------------------------------------
elif page == "Analyse & Email Candidates":
    st.title("🔍 Analyse & Email Candidates")

    if jobs_df.empty:
        st.warning("No jobs found. Please add a job first.")
    else:
        # 3.1 Select a job
        job_idx = st.selectbox(
            "Select a job to analyse",
            jobs_df.index,
            format_func=lambda i: jobs_df.at[i, "Title"]
        )
        job = jobs_df.loc[job_idx]
        st.write("**Description:**", job["Description"])
        st.write("**Location:**", job["Location"])
        st.markdown("---")

        # 3.2 Upload resumes
        files = st.file_uploader(
            "Upload multiple resumes",
            type=["pdf", "docx"],
            accept_multiple_files=True
        )

        if files:
            if st.button("Analyse Resumes"):
                parsed = [parse_resume(f) for f in files]
                df = pd.DataFrame(parsed)

                # 3.3 Compute keyword-match score
                keywords = set(job["Description"].lower().split())
                df["Score"] = df["Resume Text"].apply(
                    lambda txt: sum(txt.lower().count(k) for k in keywords)
                )
                df["Matched Keywords"] = df["Resume Text"].apply(
                    lambda txt: [k for k in keywords if k in txt.lower()]
                )
                df = df.sort_values("Score", ascending=False)

                # 3.4 Show ranking and useful info
                st.subheader("Ranked Candidates")
                st.dataframe(
                    df[["Name", "Email", "Score", "Matched Keywords"]],
                    use_container_width=True
                )

                # 3.5 Select and email top candidates
                selected = st.multiselect(
                    "Select candidates to send interview requests",
                    df["Email"].tolist()
                )
                if st.button("Send Interview Requests"):
                    for email in selected:
                        status_df = pd.concat([
                            status_df,
                            pd.DataFrame([[email, "Interview Requested"]],
                                         columns=status_df.columns)
                        ], ignore_index=True)
                    status_df.to_csv("data/status.csv", index=False)
                    st.success(f"Sent {len(selected)} interview request(s).")
                    st.experimental_rerun()

# -------------------------------------------------------------------------------
# 4) Dashboard: track statuses
# -------------------------------------------------------------------------------
elif page == "Dashboard":
    st.title("📊 Candidate Status Dashboard")
    st.dataframe(status_df, use_container_width=True)

    st.markdown("---")
    st.subheader("Update Candidate Status")
    if not status_df.empty:
        email_to_update = st.selectbox("Pick candidate", status_df["Email"].unique())
        new_status = st.selectbox("New status", ["Interview Requested", "Rejected", "Accepted"])
        if st.button("Update Status"):
            status_df.loc[status_df["Email"] == email_to_update, "Status"] = new_status
            status_df.to_csv("data/status.csv", index=False)
            st.success("Status updated!")
            st.experimental_rerun()
    else:
        st.info("No candidates tracked yet.")
