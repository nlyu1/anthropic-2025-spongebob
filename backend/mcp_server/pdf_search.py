from typing import Dict, Any
import time
import openai
import os
import json
import base64
import fitz  # pip install PyMuPDF
from dotenv import load_dotenv
import re
from difflib import SequenceMatcher
from collections import deque

load_dotenv(override=True)
DEFAULT_FILES_DIR="./files"

def pdf_to_text(path: str) -> str:
    """
    Extract text from a PDF file and save it to a text file.
    
    Args:
        path: Path to the PDF file
        
    Returns:
        str: The extracted text
    """
    # Extract text from PDF
    doc = fitz.open(path)
    parts = []
    for page in doc:
        parts.append(page.get_text())      # 'text' is default; returns UTF‑8 str
    text = "\n".join(parts)
    
    # Create parsed_pdfs directory if it doesn't exist
    parsed_dir = "parsed_pdfs"
    os.makedirs(parsed_dir, exist_ok=True)
    
    # Get PDF filename without extension
    pdf_name = os.path.splitext(os.path.basename(path))[0]
    
    # Save text to file
    output_path = os.path.join(parsed_dir, f"{pdf_name}.txt")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(text)
    
    return text

def find_relevant_text_llm(text: str, quote: str, start_tag: str = "<quote>", end_tag: str = "</quote>") -> str:
    """
    Find the relevant portion of text that contains the quote using Claude.
    
    Args:
        text: The full text to search in
        quote: The quote to find in the text
        start_tag: The tag that marks the start of the relevant text (default: "<start>")
        end_tag: The tag that marks the end of the relevant text (default: "<end>")
        
    Returns:
        str: The relevant portion of text containing the quote, or empty string if not found
    """
    start_time = time.time()
    
    # Initialize the Anthropic client
    api_key = os.getenv("FIREWORKS_API_KEY")
    client = openai.OpenAI(
        base_url = "https://api.fireworks.ai/inference/v1",
        api_key=api_key,
    )
    
    # Create a prompt that asks Claude to find the relevant text
    prompt = f"""Given the following text and quote, find the exact portion of text that contains the quote.
If the quote appears multiple times, return the first occurrence.
If the quote is not found, return "NOT FOUND".

Text:
{text}

Quote to find:
{quote}

Return the exact portion of text that contains the quote in {start_tag} {end_tag} tags, or "NOT FOUND" if not found."""

    try:
        message = client.chat.completions.create(
            model="accounts/fireworks/models/llama-v3p1-8b-instruct",
            messages=[{
                "role": "user",
                "content": prompt,
            }],
        )
        
        response = message.choices[0].message.content.strip()
        
        # Check if response is "NOT FOUND"
        if response == "NOT FOUND":
            end_time = time.time()
            print(f"Function execution time: {end_time - start_time:.2f} seconds")
            return ""
            
        # Extract text between start and end tags
        import re
        pattern = f'{re.escape(start_tag)}(.*?){re.escape(end_tag)}'
        match = re.search(pattern, response, re.DOTALL)
        if match:
            result = match.group(1).strip()
            end_time = time.time()
            print(f"Function execution time: {end_time - start_time:.2f} seconds")
            return result
        else:
            print(f"Warning: Could not find tags in Claude response: {response}")
            end_time = time.time()
            print(f"Function execution time: {end_time - start_time:.2f} seconds")
            return ""
            
    except Exception as e:
        print(f"Error using Claude to find relevant text: {e}")
        end_time = time.time()
        print(f"Function execution time: {end_time - start_time:.2f} seconds")
        return ""

def check_quote_to_text_ratio(text: str, quote: str, matching_sequence_length: int = 4, use_llm: bool = True) -> float:
    """
    Calculate the ratio of words in the quote that appear in the relevant portion of text.
    
    Args:
        text: The full text to search in
        quote: The quote to find in the text
        matching_sequence_length: Number of words to use for matching sequences
        use_claude: Whether to use Claude to find the relevant text (default: False)
        
    Returns:
        float: Ratio between 0 and 1 representing how many words from the quote appear in the relevant text
    """
    relevant_text = find_relevant_text_llm(text, quote) 
    
    if not relevant_text:
        return 0.0
        
    print(
        f"{relevant_text=}\n\n",
        f"{quote=}\n\n\n\n"
    )
    
    # Now compare quote against this substring
    text_set = set(relevant_text.split())
    quote_set = set(quote.split())
    
    elements_in_both = 0
    for elm in quote_set:
        elements_in_both += 1 if elm in text_set else 0
    
    return elements_in_both / len(quote_set)


def keep_only_lowercase_letters(text: str) -> str:
    """
    Filters a string to keep only lowercase alphabetical letters.
    
    Args:
        text (str): The input text to filter
        
    Returns:
        str: The filtered text containing only lowercase letters
        
    Example:
        >>> keep_only_lowercase_letters("Hello, World! 123")
        'helloworld'
    """
    return ''.join(char for char in text.lower() if char.isalpha())

def check_quote_in_text(text: str, quote: str, do_letters_only=True) -> bool:
    """
    Check if a quote exists in the given text by splitting it into chunks
    and finding the minimum similarity score across all chunks.
    
    Args:
        text (str): The text to search in
        quote (str): The quote to search for
        
    Returns:
        float: A score between 0 and 1, where:
            - 1.0 means an exact match was found
            - Values between 0 and 1 represent the minimum similarity score across chunks
    """
    # Convert both to lowercase for case-insensitive search
    text_lower = text.lower()
    quote_lower = quote.lower()

    def remove_hyphen_breaks(text: str) -> str:
        # collapse patterns like 'pro-\npose' -> 'propose'
        return re.sub(r'(\w+)-\s+(\w+)', r'\1\2', text)    
    
    def normalise(text: str) -> str:
        text = remove_hyphen_breaks(text)      # collapse line‑break hyphens
        text = re.sub(r'[\u00AD\-]', '', text)  # strip any remaining hyphens/soft‑hyphens
        return " ".join(text.split()).lower()
    
    text_norm  = normalise(text.lower())
    quote_norm = normalise(quote.lower())

    no_hyphen_text_lower = remove_hyphen_breaks(text_lower)
    
    # Clean both texts by:
    # 1. Removing extra whitespace
    # 2. Replacing multiple spaces with single space
    # 3. Removing line breaks
    def clean_text(t: str) -> str:
        return ' '.join(t.split())
    
    clean_no_hyphen_text_lower = clean_text(no_hyphen_text_lower)
    clean_text_lower = clean_text(text_lower)
    clean_quote_lower = clean_text(quote_lower)
    clean_text_norm = clean_text(text_norm)
    clean_quote_norm = clean_text(quote_norm)
    only_letters_text = keep_only_lowercase_letters(text)
    only_letters_quote = keep_only_lowercase_letters(quote)
    # Save cleaned versions to files
    
    letters_only_match = only_letters_quote in only_letters_text if do_letters_only else False

    # Check if quote exists in text
    is_found = (
        clean_quote_lower in clean_text_lower
        or quote_lower in text_lower # quote is directly in text
        or quote_lower.strip() in text_lower
        or clean_quote_lower in clean_no_hyphen_text_lower 
        or quote_lower in no_hyphen_text_lower
        or quote_norm in text_norm
        or clean_quote_norm in clean_text_norm 
        or letters_only_match
    )
    

    if is_found:
        return True

    return False
    # return check_quote_to_text_ratio(clean_text_norm, clean_quote_norm) 


def search_pdf_content(
    pdf_name: str,
    query: str,
    context_length: int = 0,
    topk: int = 10,
    pdf_dir: str = DEFAULT_FILES_DIR,
) -> Dict[str, Any]:
    pdf_path = os.path.join(pdf_dir, f"{pdf_name}.pdf")
    pdf_text = pdf_to_text(pdf_path)

    # Check if file exists first
    if not os.path.exists(pdf_path):
        return {
            "file_exists": False,
            "query_exists": False,
            "matches": [],
        }


    # validate quote

    query_exists = check_quote_in_text(pdf_text, query)

    result: Dict[str, Any] = {
        "file_exists": True,
        "query_exists": query_exists,
        "matches": [query],
    }

    return result
# import os
# import repd
# from io import StringIO
# from typing import Dict, List, Any

# from pdfminer.high_level import extract_text_to_fp
# from pdfminer.layout import LAParams

# DEFAULT_FILES_DIR = "./files"

# from pdfminer.high_level import extract_text
# from rapidfuzz import fuzz      # much faster drop‑in for fuzzywuzzy

# import re
# from pathlib import Path
# from typing import Any, Dict, List, Optional

# # External deps ───────────────────────────────────────────────────────────────
# #   pip install pdfminer.six rapidfuzz
# from pdfminer.high_level import extract_text
# from rapidfuzz import fuzz

# DEFAULT_FILES_DIR = "./files"          # change to suit your project‑wide default
# FUZZ_THRESHOLD   = 0.70                  # similarity (0‑1) needed to accept a match


# def _cleanup_pdf_text(text: str) -> str:
#     """Undo common PDF artefacts: hyphen line‑breaks, stray newlines, etc."""
#     text = re.sub(r'(\w+)-\s*\n(\w+)', r'\1\2', text)  # join syllable‑breaks
#     text = re.sub(r'\s+', ' ', text)                   # collapse whitespace
#     return text.strip()


# def search_pdf_content(
#     pdf_name: str,
#     query: str,
#     context_length: int = 0,
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
#     result: Dict[str, Any] = {
#         "file_exists": False,
#         "query_exists": False,
#         "matches": [],
#     }

#     pdf_path = Path(files_dir) / f"{pdf_name}.pdf"

#     # ------------------------------------------------------------------ guard
#     if not pdf_path.exists():
#         result["error"] = f"File '{pdf_path}' not found."
#         return result

#     result["file_exists"] = True

#     # ------------------------------------------------------ extract & pre‑parse
#     try:
#         raw_text = extract_text(str(pdf_path))
#     except Exception as exc:
#         result["error"] = f"Could not read PDF: {exc}"
#         return result

#     pages = raw_text.split("\f")                  # pdfminer inserts \f between pages
#     query_lower = query.lower()

#     matches: List[str] = []

#     # ---------------------------------------------------------- fuzzy search
#     for page_num, page in enumerate(pages, start=1):
#         page = _cleanup_pdf_text(page)

#         # crude paragraph split; fall back to whole page if no blank‑line breaks
#         paragraphs = re.split(r'\n\s*\n', page) or [page]
#         paragraphs = [p.strip() for p in paragraphs if p.strip()]

#         for para in paragraphs:
#             score = fuzz.token_set_ratio(query_lower, para.lower()) / 100.0
#             if score >= FUZZ_THRESHOLD:
#                 # build context snippet
#                 if context_length > 0:
#                     # find fuzzy location by simple substring fallback
#                     pos = para.lower().find(query_lower.split()[0])
#                     if pos != -1:
#                         start = max(0, pos - context_length // 2)
#                         end   = min(len(para), pos + len(query) + context_length // 2)
#                         snippet = para[start:end].strip()
#                     else:
#                         snippet = para[: context_length].strip()
#                 else:
#                     snippet = para

#                 # include provenance hint
#                 matches.append(f"[p.{page_num}] …{snippet}…")

#                 if len(matches) >= topk:
#                     break       # stop inner loop
#         if len(matches) >= topk:
#             break               # stop outer loop

#     result["query_exists"] = bool(matches)
#     result["matches"] = matches

#     return result

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