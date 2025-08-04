import streamlit as st
import openai

st.set_page_config(page_title="Resume Q&A Chatbot", layout="wide")

st.title("🤖 Resume Analysis & Recruiter Chatbot")

# Load OpenAI API key
openai.api_key = st.secrets.get("openai_api_key", None)
if not openai.api_key:
    st.error("Please set your OpenAI API key in `.streamlit/secrets.toml` as `openai_api_key = \"...\"`")
    st.stop()

# Input fields
resume_text = st.text_area("📄 Paste Candidate Resume Text", height=300)
job_text = st.text_area("🧾 Paste Job Description (Optional)", height=200)

# Generate summary
if st.button("🔍 Generate Resume Summary & Enable Chatbot"):
    if not resume_text.strip():
        st.error("Please paste a resume first.")
        st.stop()

    with st.spinner("Generating detailed resume summary..."):
        summary_prompt = (
            f"Candidate Resume:\n{resume_text}\n\n"
            f"Job Description:\n{job_text if job_text else '(not provided)'}\n\n"
            "Please provide a professional summary highlighting candidate strengths, experience, skills, and job fit."
        )
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert resume reviewer and recruiter assistant."},
                    {"role": "user", "content": summary_prompt}
                ]
            )
            summary = response.choices[0].message["content"]
            st.subheader("📋 Resume Summary")
            st.markdown(summary)
        except Exception as e:
            st.error(f"OpenAI Error: {e}")
            st.stop()

    st.divider()
    st.subheader("💬 Ask a Question About This Resume")

    # Chatbot Q&A
    user_q = st.text_input("Type your question (e.g., How many years of QA experience?)")
    if user_q:
        with st.spinner("Analyzing..."):
            try:
                chat_response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant answering questions from recruiters about candidate resumes."},
                        {"role": "user", "content": f"Candidate Resume:\n{resume_text}"},
                        {"role": "user", "content": f"Question: {user_q}"}
                    ]
                )
                answer = chat_response.choices[0].message["content"]
                st.markdown(f"**Q:** {user_q}")
                st.markdown(f"**A:** {answer}")
            except Exception as e:
                st.error(f"Error: {e}")
