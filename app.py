import os
import json
import fitz  # PyMuPDF
import pandas as pd
import requests
import streamlit as st

# ================== CONFIG ==================
# Put your real endpoint here
API_URL = "https://brainyscout.com/api/rscore"  # <-- change if different

# Read token from Streamlit Secrets (Cloud) or env var (local)
AUTH_TOKEN = st.secrets.get("BRAINYSCOUT_API_TOKEN") or os.getenv("BRAINYSCOUT_API_TOKEN")

# ================== HELPERS ==================
def extract_text_from_pdf(file) -> str:
    """Return plain text from an uploaded PDF file-like object."""
    with fitz.open(stream=file.read(), filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)

def score_with_single_api(resume_text: str, job_description: str, functional_title: str) -> dict:
    """
    Calls your SINGLE API that takes resume + JD and returns the score/result.
    Payload is exactly as you showed:
    {
        "data": {
            "resumeText": "...",
            "jobdescription": "...",
            "functionaltitle": "..."
        }
    }
    """
    headers = {"Content-Type": "application/json"}
    if AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}"

    payload = {
        "data": {
            "resumeText": resume_text,
            "jobdescription": job_description,
            "functionaltitle": functional_title
        }
    }

    resp = requests.post(API_URL, headers=headers, data=json.dumps(payload))
    resp.raise_for_status()
    return resp.json()

def flatten(prefix: str, obj: dict, out: dict):
    """Flatten nested dicts (best-effort) for tabular display."""
    for k, v in obj.items():
        key = f"{prefix}{k}" if prefix == "" else f"{prefix}.{k}"
        if isinstance(v, dict):
            flatten(key, v, out)
        else:
            out[key] = v
    return out

# ================== UI ==================
st.set_page_config(page_title="Resume → JD Scorer (Single API)", layout="wide")
st.title("🤖 PDF Resume → JD Scorer (Single API)")

# ---- Inputs ----
st.header("1️⃣ Provide Job Inputs")
functional_title = st.text_input("Functional Title", placeholder="e.g., QA Analyst")
job_description = st.text_area("Paste Job Description", height=200)

st.header("2️⃣ Upload PDF Resumes")
pdf_files = st.file_uploader("Upload resumes (PDF only)", type=["pdf"], accept_multiple_files=True)

st.header("3️⃣ Run Scoring")
if st.button("🚀 Score"):
    if not functional_title or not job_description:
        st.warning("Please provide Functional Title and Job Description.")
    elif not pdf_files:
        st.warning("Please upload at least one PDF resume.")
    else:
        if not AUTH_TOKEN:
            st.info("ℹ️ No auth token found. If your API requires one, add it via Streamlit Secrets or env var.")

        rows = []

        for f in pdf_files:
            try:
                resume_text = extract_text_from_pdf(f)
                api_result = score_with_single_api(resume_text, job_description, functional_title)

                # Prepare a flat row for the table
                flat = {
                    "Candidate File": f.name,
                }
                if isinstance(api_result, dict):
                    flat = flatten("", api_result, flat)
                else:
                    flat["api_raw"] = str(api_result)

                rows.append(flat)

            except Exception as e:
                st.error(f"❌ Error with {f.name}: {e}")

        if rows:
            df = pd.DataFrame(rows)
            st.subheader("📊 Results")
            st.dataframe(df, use_container_width=True)
            st.download_button(
                "📥 Download CSV",
                df.to_csv(index=False),
                file_name="resume_scores.csv",
                mime="text/csv"
            )
