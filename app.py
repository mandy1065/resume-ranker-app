import streamlit as st
import pandas as pd
import PyPDF2
import docx
import re
import os
import openai
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ------------------------------
# Helper Functions
# ------------------------------
def extract_text_from_pdf(file):
    pdf = PyPDF2.PdfReader(file)
    return " ".join(page.extract_text() for page in pdf.pages if page.extract_text())

def extract_text_from_docx(file):
    doc = docx.Document(file)
    return " ".join(paragraph.text for paragraph in doc.paragraphs)

def preprocess_text(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text)

def extract_skills(text):
    common_skills = ["python", "java", "sql", "aws", "selenium", "appium", "jira", "aoda", "agile", "communication", "leadership"]
    found = [skill for skill in common_skills if skill.lower() in text.lower()]
    return found

def extract_years_experience(text):
    matches = re.findall(r"(\d+)[+]?\s+years?", text.lower())
    return max(map(int, matches)) if matches else 0

def get_openai_api_key():
    return st.secrets.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")

def summarize_with_openai(name, resume_text, jd_text):
    prompt = f"Candidate Name: {name}\nJob Description: {jd_text}\nResume: {resume_text}\n\nProvide a detailed summary comparing the candidate's experience, skills, and strengths against the job description. Highlight suitability, concerns, and strengths in bullet points."
    key = get_openai_api_key()
    if not key:
        return "OpenAI API key not set."

    try:
        openai.api_key = key
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": "You are a helpful recruitment assistant."},
                      {"role": "user", "content": prompt}],
            temperature=0.4,
        )
        return response.choices[0].message["content"]
    except Exception as e:
        return f"Error generating summary: {e}"

def ask_question_with_openai(resume_text, question):
    key = get_openai_api_key()
    if not key:
        return "OpenAI API key not set."
    try:
        openai.api_key = key
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": "You answer questions about candidate resumes."},
                      {"role": "user", "content": f"Resume: {resume_text}\n\nQuestion: {question}"}],
            temperature=0.4,
        )
        return response.choices[0].message["content"]
    except Exception as e:
        return f"Error answering question: {e}"

# ------------------------------
# Streamlit App UI
# ------------------------------
st.set_page_config(page_title="Resume Ranker & AI Recruiter", layout="wide")
st.title("Resume Ranker with AI Assistant")

# Job description input
job_description = st.text_area("Paste Job Description Here", height=200)
required_exp = st.number_input("Years of Experience Required", min_value=0, max_value=30, value=5)

# Add skills and weights
st.subheader("Define Required Skills and Weights")
if "skills_list" not in st.session_state:
    st.session_state.skills_list = [{"skill": "", "weight": 5.0}]

cols = st.columns([4, 2, 1])
if cols[2].button("âž• Add Skill"):
    st.session_state.skills_list.append({"skill": "", "weight": 5.0})

for i, s in enumerate(st.session_state.skills_list):
    cols = st.columns([4, 2, 1])
    s["skill"] = cols[0].text_input("Skill", s["skill"], key=f"skill_{i}")
    s["weight"] = cols[1].slider("Weight", 1, 10, int(s["weight"]), key=f"weight_{i}")
    if cols[2].button("ðŸ—‘ï¸", key=f"del_{i}"):
        st.session_state.skills_list.pop(i)
        st.experimental_rerun()

# Resume upload
uploaded_files = st.file_uploader("Upload Resumes", type=["pdf", "docx"], accept_multiple_files=True)

if uploaded_files and job_description:
    st.subheader("Candidate Analysis")
    summaries = {}
    resume_data = []

    jd_text = preprocess_text(job_description)
    jd_skills = [s["skill"].lower() for s in st.session_state.skills_list if s["skill"]]
    jd_weights = [s["weight"] for s in st.session_state.skills_list if s["skill"]]
    total_weight = sum(jd_weights) if jd_weights else 1
    norm_weights = [w / total_weight for w in jd_weights]

    for file in uploaded_files:
        ext = file.name.split(".")[-1]
        raw = extract_text_from_pdf(file) if ext == "pdf" else extract_text_from_docx(file)
        clean = preprocess_text(raw)
        found_skills = [s for s in jd_skills if s in clean]
        score = sum(norm_weights[i] for i, s in enumerate(jd_skills) if s in clean)
        years = extract_years_experience(clean)

        resume_data.append({
            "Name": file.name.split(".")[0],
            "Email": "N/A",
            "Skills Matched": ", ".join(found_skills),
            "Weighted Score": round(score, 3),
            "Years Exp": years,
            "Resume": clean
        })

    df = pd.DataFrame(resume_data)
    st.dataframe(df[["Name", "Weighted Score", "Skills Matched", "Years Exp"]])

    # Summarization and chat
    if st.button("ðŸ” Generate LLM Summaries & Enable Chat"):
        for row in resume_data:
            row["Summary"] = summarize_with_openai(row["Name"], row["Resume"], jd_text)
        st.session_state.candidates = resume_data

if "candidates" in st.session_state:
    st.subheader("ðŸ“‹ AI Summary & Chat for Candidates")
    names = [c["Name"] for c in st.session_state.candidates]
    selected = st.selectbox("Select Candidate", names)
    cand = next(c for c in st.session_state.candidates if c["Name"] == selected)

    st.markdown("### ðŸ“„ Summary")
    st.markdown(cand.get("Summary", "No summary available."))

    st.markdown("### ðŸ’¬ Ask a Question")
    question = st.text_input("Ask about resume content (e.g., What tools has the candidate used?)")
    if question:
        if st.button("Ask"):
            answer = ask_question_with_openai(cand["Resume"], question)
            st.markdown(f"**Answer:** {answer}")
