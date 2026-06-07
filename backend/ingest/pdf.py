import os
import pdfplumber


def get_pdf_text(file_path: str) -> str:
    """Extract text from a PDF file."""
    file_path = os.path.expanduser(file_path)
    file_path = os.path.abspath(file_path)

    if not os.path.exists(file_path):
        raise ValueError(f"File not found: {file_path}")

    text_pages = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_pages.append(page_text)

    if not text_pages:
        raise ValueError(f"Could not extract text from PDF: {file_path}")

    return "\n\n".join(text_pages)
