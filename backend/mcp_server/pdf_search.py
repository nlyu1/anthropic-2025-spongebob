import os
import re
from io import StringIO
from typing import Dict, List, Any

from pdfminer.high_level import extract_text_to_fp
from pdfminer.layout import LAParams

DEFAULT_FILES_DIR = "./files"

from pdfminer.high_level import extract_text
from rapidfuzz import fuzz      # much faster drop‑in for fuzzywuzzy

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

# External deps ───────────────────────────────────────────────────────────────
#   pip install pdfminer.six rapidfuzz
from pdfminer.high_level import extract_text
from rapidfuzz import fuzz

DEFAULT_FILES_DIR = "./files"          # change to suit your project‑wide default
FUZZ_THRESHOLD   = 0.70                  # similarity (0‑1) needed to accept a match


def _cleanup_pdf_text(text: str) -> str:
    """Undo common PDF artefacts: hyphen line‑breaks, stray newlines, etc."""
    text = re.sub(r'(\w+)-\s*\n(\w+)', r'\1\2', text)  # join syllable‑breaks
    text = re.sub(r'\s+', ' ', text)                   # collapse whitespace
    return text.strip()


def search_pdf_content(
    pdf_name: str,
    query: str,
    context_length: int = 0,
    topk: int = 10,
    files_dir: str = DEFAULT_FILES_DIR,
) -> Dict[str, Any]:
    """Searches for a query within a PDF file located in the specified directory.

    Args:
        pdf_name: The name of the PDF file (without extension).
        query: The text query to search for (case-insensitive).
        context_length: Approximate character length of context around each match.
        topk: Maximum number of matches to return.
        files_dir: The directory containing the PDF files.

    Returns:
        A dictionary containing search results:
        {
            "file_exists": bool,
            "query_exists": bool,
            "matches": List[str],
            "error": Optional[str]
        }
    """
    result: Dict[str, Any] = {
        "file_exists": False,
        "query_exists": False,
        "matches": [],
    }

    pdf_path = Path(files_dir) / f"{pdf_name}.pdf"

    # ------------------------------------------------------------------ guard
    if not pdf_path.exists():
        result["error"] = f"File '{pdf_path}' not found."
        return result

    result["file_exists"] = True

    # ------------------------------------------------------ extract & pre‑parse
    try:
        raw_text = extract_text(str(pdf_path))
    except Exception as exc:
        result["error"] = f"Could not read PDF: {exc}"
        return result

    pages = raw_text.split("\f")                  # pdfminer inserts \f between pages
    query_lower = query.lower()

    matches: List[str] = []

    # ---------------------------------------------------------- fuzzy search
    for page_num, page in enumerate(pages, start=1):
        page = _cleanup_pdf_text(page)

        # crude paragraph split; fall back to whole page if no blank‑line breaks
        paragraphs = re.split(r'\n\s*\n', page) or [page]
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        for para in paragraphs:
            score = fuzz.token_set_ratio(query_lower, para.lower()) / 100.0
            if score >= FUZZ_THRESHOLD:
                # build context snippet
                if context_length > 0:
                    # find fuzzy location by simple substring fallback
                    pos = para.lower().find(query_lower.split()[0])
                    if pos != -1:
                        start = max(0, pos - context_length // 2)
                        end   = min(len(para), pos + len(query) + context_length // 2)
                        snippet = para[start:end].strip()
                    else:
                        snippet = para[: context_length].strip()
                else:
                    snippet = para

                # include provenance hint
                matches.append(f"[p.{page_num}] …{snippet}…")

                if len(matches) >= topk:
                    break       # stop inner loop
        if len(matches) >= topk:
            break               # stop outer loop

    result["query_exists"] = bool(matches)
    result["matches"] = matches

    return result

# def search_pdf_content(
#     pdf_name: str,
#     query: str,
#     context_length: int = 2000,
#     topk: int = 10,
#     files_dir: str = DEFAULT_FILES_DIR,
# ) -> Dict[str, Any]:
#     """Searches for a query within a PDF file located in the specified directory.

#     Args:
#         pdf_name: The name of the PDF file (without extension).
#         query: The text query to search for (case-insensitive).
#         context_length: Approximate character length of context around each match.
#         topk: Maximum number of matches to return.
#         files_dir: The directory containing the PDF files.

#     Returns:
#         A dictionary containing search results:
#         {
#             "file_exists": bool,
#             "query_exists": bool,
#             "matches": List[str],
#             "error": Optional[str]
#         }
#     """
#     pdf_path = os.path.join(files_dir, f"{pdf_name}.pdf")
#     # raise RuntimeError(f'Reached here, {os.path.abspath(pdf_path)}')
#     # Use os.path.abspath() to print the absolute path. Also use the 'files_dir' argument instead of the global constant for accuracy.
#     result: Dict[str, Any] = {
#         "file_exists": False,
#         "query_exists": False,
#         "matches": [],
#         "error": None,
#     }

#     if not os.path.exists(pdf_path):
#         result["error"] = f"File not found: {pdf_path}"
#         return result

#     result["file_exists"] = True

#     try:
#         # Extract text from PDF
#         output_string = StringIO()
#         with open(pdf_path, 'rb') as fin:
#             extract_text_to_fp(fin, output_string, laparams=LAParams(),
#                                output_type='text', codec=None) # Use None for auto-detection, often utf-8
#         pdf_text = output_string.getvalue()
#         output_string.close()

#         if not pdf_text:
#              result["error"] = "Extracted text is empty. The PDF might be image-based or corrupted."
#              return result

#     except Exception as e:
#         result["error"] = f"Failed to parse PDF: {e}"
#         return result

#     # Search for query (case-insensitive)
#     matches_found = []
#     half_context = context_length // 2
#     try:
#         # Use re.finditer for non-overlapping matches and their positions
#         for match in re.finditer(query, pdf_text, re.IGNORECASE):
#             if len(matches_found) >= topk:
#                 break

#             start_index = max(0, match.start() - half_context)
#             end_index = min(len(pdf_text), match.end() + half_context)

#             # Extract context, ensuring match is centered as much as possible
#             context = pdf_text[start_index:end_index]

#             # Clean up context (optional: replace multiple whitespaces/newlines)
#             context = re.sub(r'\s+', ' ', context).strip()

#             matches_found.append(context)

#     except Exception as e:
#         # Handle potential regex errors, although unlikely with simple strings
#         result["error"] = f"Error during search: {e}"
#         return result


#     if matches_found:
#         result["query_exists"] = True
#         result["matches"] = matches_found
#     else:
#         # File exists, parsing succeeded, but query not found
#         result["query_exists"] = False


#     # Remove error field if no error occurred
#     if result["error"] is None:
#         del result["error"]

#     return result

# Example usage (for testing purposes)
if __name__ == '__main__':
    try:
        # Check if pdfminer is installed
        from pdfminer.high_level import extract_text_to_fp # Test import

        print("PDF Search Debugger")
        print(f"Looking for PDFs in: {os.path.abspath(DEFAULT_FILES_DIR)}")
        print("Enter 'quit' for pdf name or query to exit.")

        if not os.path.exists(DEFAULT_FILES_DIR):
            print(f"\nWarning: Directory '{DEFAULT_FILES_DIR}' does not exist. Creating it.")
            try:
                os.makedirs(DEFAULT_FILES_DIR)
                print(f"Created directory: {os.path.abspath(DEFAULT_FILES_DIR)}")
                print("Please add your PDF files to this directory.")
            except OSError as e:
                print(f"Error creating directory {DEFAULT_FILES_DIR}: {e}")
                print("Please create the directory manually and add PDF files.")
                exit(1)
        else:
            print("Found files directory.")

        while True:
            pdf_name = input("\nEnter PDF name (without .pdf extension, or 'quit'): ").strip()
            if pdf_name.lower() == 'quit':
                break

            query = input("Enter search query (or 'quit'): ").strip()
            if query.lower() == 'quit':
                break

            if not pdf_name or not query:
                print("PDF name and query cannot be empty.")
                continue

            print(f"\nSearching for '{query}' in '{pdf_name}.pdf'...")
            result = search_pdf_content(pdf_name, query)

            print("\n--- Result ---")
            import json
            print(json.dumps(result, indent=2))
            print("------------")

    except ImportError:
         print("\nError: pdfminer.six is not installed.")
         print("Please install dependencies: uv pip install pdfminer.six")
         # Or install all dependencies from pyproject.toml: uv pip sync pyproject.toml

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

    print("\nExiting PDF Search Debugger.") 