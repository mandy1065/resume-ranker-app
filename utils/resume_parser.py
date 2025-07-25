import os
import tempfile
from PyPDF2 import PdfReader

def parse_resume(uploaded_file):
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_file.write(uploaded_file.read())
        tmp_path = tmp_file.name

    text = ""
    if uploaded_file.name.endswith(".pdf"):
        reader = PdfReader(tmp_path)
        for page in reader.pages:
            text += page.extract_text()
    elif uploaded_file.name.endswith(".docx"):
        import docx
        doc = docx.Document(tmp_path)
        text = "\n".join([para.text for para in doc.paragraphs])

    os.remove(tmp_path)

    return {
        "Name": "Unknown",
        "Email": f"{uploaded_file.name.split('.')[0]}@example.com",
        "Skills": "Python, Streamlit",
        "Resume Text": text[:1000]
    }
