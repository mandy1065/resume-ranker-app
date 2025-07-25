import os
import tempfile
from PyPDF2 import PdfReader

def parse_resume(uploaded_file):
    # Write to temp file
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(uploaded_file.read())
        path = tmp.name

    text = ""
    name, _ = os.path.splitext(uploaded_file.name)
    if uploaded_file.name.lower().endswith(".pdf"):
        reader = PdfReader(path)
        for page in reader.pages:
            text += page.extract_text() or ""
    else:
        import docx
        doc = docx.Document(path)
        text = "\n".join(p.text for p in doc.paragraphs)

    os.remove(path)

    # Basic parsing: Use filename as Name & create dummy email
    return {
        "Name": name,
        "Email": f"{name.replace(' ', '.').lower()}@example.com",
        "Skills": "N/A",
        "Resume Text": text[:2000]  # preview
    }
