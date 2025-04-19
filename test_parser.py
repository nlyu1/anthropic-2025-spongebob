# pip install pymupdf tiktoken nltk
import fitz  # PyMuPDF
from pathlib import Path
from textwrap import wrap

CHUNK_SIZE = 800   # characters
OVERLAP    = 100   # characters

def pdf_to_chunks(path: str) -> list[str]:
    doc  = fitz.open(path)
    full = " ".join(page.get_text() for page in doc)

    # optional clean‑up (remove double spaces/newlines)
    full = " ".join(full.split())

    chunks = []
    start  = 0
    while start < len(full):
        end = min(len(full), start + CHUNK_SIZE)
        # expand to nearest word boundary
        while end < len(full) and full[end] != " ":
            end += 1
        chunks.append(full[start:end].strip())
        start = end - OVERLAP  # small overlap helps retrieval
    return chunks

if __name__ == "__main__":
    for i, chunk in enumerate(pdf_to_chunks("documents/unlearning.pdf")):
        print(f"\n--- chunk {i} ---\n")
        print(chunk[:300], "…")
