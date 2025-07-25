import streamlit as st
import pandas as pd
from utils.resume_parser import parse_resume
import smtplib

st.set_page_config(page_title="Recruiter Portal", layout="wide")

# Load data
jobs_df = pd.read_csv("data/jobs.csv")
candidates_df = pd.read_csv("data/candidates.csv")
status_df = pd.read_csv("data/status.csv")

# Sidebar navigation
st.sidebar.title("Recruiter Portal")
page = st.sidebar.radio("Go to", ["Post Job", "Upload Resumes", "Rank Candidates", "Dashboard"])

# Post Job
if page == "Post Job":
    st.title("📝 Post a Job")
    title = st.text_input("Job Title")
    description = st.text_area("Job Description")
    location = st.text_input("Location")
    if st.button("Submit Job"):
        new_job = pd.DataFrame([[title, description, location]], columns=["Title", "Description", "Location"])
        jobs_df = pd.concat([jobs_df, new_job], ignore_index=True)
        jobs_df.to_csv("data/jobs.csv", index=False)
        st.success("Job posted!")

# Upload Resumes
elif page == "Upload Resumes":
    st.title("📄 Upload Resumes")
    uploaded_files = st.file_uploader("Upload multiple resumes", type=["pdf", "docx"], accept_multiple_files=True)
    if uploaded_files:
        for file in uploaded_files:
            parsed = parse_resume(file)
            candidates_df = pd.concat([candidates_df, pd.DataFrame([parsed])], ignore_index=True)
        candidates_df.to_csv("data/candidates.csv", index=False)
        st.success("Resumes uploaded and parsed!")

# Rank Candidates
elif page == "Rank Candidates":
    st.title("🏆 Ranked Candidates")
    if jobs_df.empty or candidates_df.empty:
        st.warning("Please post a job and upload resumes first.")
    else:
        job = jobs_df.iloc[-1]
        st.write(f"Matching candidates for: **{job['Title']}**")
        keywords = job["Description"].lower().split()
        candidates_df["Score"] = candidates_df["Resume Text"].apply(
            lambda text: sum([text.lower().count(k) for k in keywords])
        )
        ranked = candidates_df.sort_values(by="Score", ascending=False)
        st.dataframe(ranked)

        selected = st.multiselect("Select candidates to send interview email", ranked["Email"].tolist())
        if st.button("Send Interview Request"):
            for email in selected:
                status_df = pd.concat([status_df, pd.DataFrame([[email, "Interview Requested"]], columns=["Email", "Status"])], ignore_index=True)
            status_df.to_csv("data/status.csv", index=False)
            st.success("Interview requests sent!")

# Dashboard
elif page == "Dashboard":
    st.title("📊 Candidate Status Dashboard")
    st.dataframe(status_df)
    update_email = st.selectbox("Select candidate to update status", status_df["Email"].unique())
    new_status = st.selectbox("New Status", ["Interview Requested", "Rejected", "Accepted"])
    if st.button("Update Status"):
        status_df.loc[status_df["Email"] == update_email, "Status"] = new_status
        status_df.to_csv("data/status.csv", index=False)
        st.success("Status updated!")
