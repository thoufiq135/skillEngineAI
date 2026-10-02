from pypdf import PdfReader
from docx import Document


def extract_text(file_path):

    if file_path.lower().endswith(".pdf"):

        reader = PdfReader(file_path)
        text = ""

        for page in reader.pages:
            text += page.extract_text() or ""

    elif file_path.lower().endswith(".docx"):

        document = Document(file_path)
        text = ""

        for paragraph in document.paragraphs:
            text += paragraph.text + "\n"

    else:
        raise ValueError("Only PDF and DOCX files are supported")

    return text


if __name__ == "__main__":

    resume_text = extract_text("Meghanjani_Resume.pdf")

    print("========== RESUME ==========")
    print(resume_text)