import os
import re
from io import StringIO
from typing import Dict, List, Any, Optional

from pdfminer.high_level import extract_text_to_fp
from pdfminer.layout import LAParams
from mcp.server.fastmcp import FastMCP

from .. import settings # Import settings module

# Instantiate FastMCP
mcp = FastMCP("pdf_tools")

@mcp.tool()
def search_pdf(
    pdf_name: str,
    query: str,
    context_length: int = 2000,
    topk: int = 10,
    files_dir_override: Optional[str] = None, # Allow overriding files_dir
) -> Dict[str, Any]:
    """Searches for a query within a PDF file located in the specified directory.

    Args:
        pdf_name: The name of the PDF file (without extension).
        query: The text query to search for (case-insensitive).
        context_length: Approximate character length of context around each match.
        topk: Maximum number of matches to return.
        files_dir_override: Optional override for the directory containing PDF files.

    Returns:
        A dictionary containing search results:
        {
            "file_exists": bool,
            "query_exists": bool,
            "matches": List[str],
            "error": Optional[str]
        }
    """
    # Determine the directory to use
    target_files_dir = files_dir_override if files_dir_override is not None else settings.files_dir

    # Resolve the files_dir relative to the project root (where .env is)
    # If an absolute path is in settings or passed, it will be used as is.
    pdf_path = os.path.abspath(os.path.join(target_files_dir, f"{pdf_name}.pdf"))

    result: Dict[str, Any] = {
        "file_exists": False,
        "query_exists": False,
        "matches": [],
        "error": None,
    }

    if not os.path.exists(pdf_path):
        result["error"] = f"File not found: {pdf_path}"
        return result

    result["file_exists"] = True

    try:
        # Extract text from PDF
        output_string = StringIO()
        with open(pdf_path, 'rb') as fin:
            extract_text_to_fp(fin, output_string, laparams=LAParams(),
                               output_type='text', codec=None)
        pdf_text = output_string.getvalue()
        output_string.close()

        if not pdf_text:
             result["error"] = "Extracted text is empty. The PDF might be image-based or corrupted."
             return result

    except Exception as e:
        result["error"] = f"Failed to parse PDF ({pdf_path}): {e}"
        return result

    # Search for query (case-insensitive)
    matches_found = []
    half_context = context_length // 2
    try:
        # Use re.finditer for non-overlapping matches and their positions
        for match in re.finditer(query, pdf_text, re.IGNORECASE):
            if len(matches_found) >= topk:
                break

            start_index = max(0, match.start() - half_context)
            end_index = min(len(pdf_text), match.end() + half_context)

            # Extract context
            context = pdf_text[start_index:end_index]

            # Clean up context
            context = re.sub(r'\s+', ' ', context).strip()

            matches_found.append(context)

    except Exception as e:
        result["error"] = f"Error during search: {e}"
        return result

    if matches_found:
        result["query_exists"] = True
        result["matches"] = matches_found
    else:
        result["query_exists"] = False

    # Remove error field if no error occurred
    if result["error"] is None:
        del result["error"]

    return result

# The CLI block (`if __name__ == '__main__':`) from the original file is removed.
