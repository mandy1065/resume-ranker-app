import os
import re
import tempfile

import pandas as pd
import streamlit as st
from PyPDF2 import PdfReader
import docx

# ---------------------
# Config & Constants
# ---------------------
EMAIL_REGEX = re.compile(r"[A-Za-z0-9.+_-]+@[A-Za-z0-9._-]+\.[A-Za-z]+")
STATUS_CSV   = os.path.join("data", "status.csv")
os.makedirs("data", exist_ok=True)

# ---------------------
# Load or Init Status DF
# ---------------------
if "status_df" not in st.session_state:
    try:
        st.session_state.status_df = pd.read_csv(STATUS_CSV)
    except FileNotFoundError:
        st.session_state.status_df = pd.DataFrame(columns=["Email", "Status"])

# ---------------------
# Helper: Extract Text
# ---------------------
def extract_text(path: str, ext: str) -> str:
    text = ""
    if ext == ".pdf":
        reader = PdfReader(path)
        for p in reader.pages:
            text += p.extract_text() or ""
    else:
        doc = docx.Document(path)
        text = "\n".join(para.text for para in doc.paragraphs)
    return text

# ---------------------
# Helper: Parse Resume
# ---------------------
def parse_resume(uploaded_file) -> dict:
    suffix = os.path.splitext(uploaded_file.name)[1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    text = extract_text(tmp_path, suffix)
    os.remove(tmp_path)

    match = EMAIL_REGEX.search(text)
    email = match.group(0) if match else None
    name  = os.path.splitext(uploaded_file.name)[0]

    if not email:
        email = f"{name.replace(' ', '.').lower()}@example.com"

    return {"Name": name, "Email": email, "Resume Text": text}

# ---------------------
# UI: Title & Upload
# ---------------------
st.title("📋 Candidate Dashboard & Interview Requests")

uploaded_files = st.file_uploader(
    "Upload resumes (PDF or DOCX)", type=["pdf", "docx"], accept_multiple_files=True
)

# When new resumes arrive, parse them and add “Applied” statuses
if uploaded_files:
    parsed = [parse_resume(f) for f in uploaded_files]
    df_parsed = pd.DataFrame(parsed)
    st.subheader("Parsed Resumes")
    st.dataframe(df_parsed[["Name", "Email"]], height=200)

    existing = set(st.session_state.status_df["Email"])
    new_emails = set(df_parsed["Email"]) - existing
    if new_emails:
        new_rows = pd.DataFrame({
            "Email":  list(new_emails),
            "Status": ["Applied"] * len(new_emails)
        })
        st.session_state.status_df = pd.concat(
            [st.session_state.status_df, new_rows],
            ignore_index=True
        )
        st.session_state.status_df.to_csv(STATUS_CSV, index=False)
        st.success(f"Added {len(new_emails)} new candidate(s).")

# ---------------------
# UI: Send Interview Requests
# ---------------------
all_emails = st.session_state.status_df["Email"].tolist()
to_request = st.multiselect(
    "Select candidate(s) to mark as ‘Interview Requested’",
    options=all_emails
)

if st.button("Send Interview Requests"):
    df = st.session_state.status_df.copy()

    # 1) Update existing rows
    mask = df["Email"].isin(to_request)
    df.loc[mask, "Status"] = "Interview Requested"

    # 2) Append any truly new emails (rare if you loaded from CSV)
    missing = set(to_request) - set(df.loc[mask, "Email"])
    if missing:
        extra = pd.DataFrame({
            "Email":  list(missing),
            "Status": ["Interview Requested"] * len(missing)
        })
        df = pd.concat([df, extra], ignore_index=True)

    # 3) Persist
    st.session_state.status_df = df
    df.to_csv(STATUS_CSV, index=False)

    st.success(f"Updated status for {len(to_request)} candidate(s).")

# ---------------------
# UI: Live Dashboard
# ---------------------
st.subheader("Current Candidate Status")
st.dataframe(st.session_state.status_df, height=300)
