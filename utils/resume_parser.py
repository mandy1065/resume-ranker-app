# utils/resume_parser.py

import re
import os
import tempfile
from PyPDF2 import PdfReader
import docx

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9.+_-]+@[a-zA-Z0-9._-]+\.[a-zA-Z]+")

def extract_text(path, extension):
    text = ""
    if extension == ".pdf":
        reader = PdfReader(path)
        for page in reader.pages:
            text += page.extract_text() or ""
    else:
        doc = docx.Document(path)
        text = "\n".join(para.text for para in doc.paragraphs)
    return text

def parse_resume(uploaded_file):
    # write to temp
    suffix = os.path.splitext(uploaded_file.name)[1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    # extract text
    text = extract_text(tmp_path, suffix)
    os.remove(tmp_path)

    # find first email
    match = EMAIL_REGEX.search(text)
    email = match.group(0) if match else None

    # derive name from filename if no email
    name = os.path.splitext(uploaded_file.name)[0]
    if not email:
        email = f"{name.replace(' ', '.').lower()}@example.com"

    return {
        "Name": name,
        "Email": email,
        "Resume Text": text
    }
