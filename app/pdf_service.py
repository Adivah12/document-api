from pathlib import Path
from pypdf import PdfReader

def extract_pdf_text(storage_path: str) -> str:
    with Path(storage_path).open("rb") as pdf_file:
        reader = PdfReader(pdf_file)
        page_texts = []

        for page in reader.pages:
            text =page.extract_text() or ""
            page_texts.append(text.strip())

    return "\n\n".join(page_texts).strip()