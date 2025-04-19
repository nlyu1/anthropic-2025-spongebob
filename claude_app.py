#TODO
    # remove page numbers
    #
import os
import json
import base64
import fitz  # pip install PyMuPDF
from dotenv import load_dotenv
import anthropic
import re
import voyageai
import numpy as np
from difflib import SequenceMatcher
from collections import deque

# Load environment variables 
load_dotenv(override=True)

# Initialize Voyage AI client
vo = voyageai.Client()

def test_quote_extraction():
    """
    Test the extract_and_validate_quotes function with sample inputs.
    """
    # Sample PDF text (this would be a small excerpt from the actual PDF)
    sample_pdf_text = """
    Machine learning is a field of artificial intelligence that focuses on developing algorithms 
    that can learn from and make predictions on data. Deep learning is a subset of machine learning 
    that uses neural networks with many layers. The field has seen significant advances in recent years.
    """
    
    # Sample Claude response with quotes
    sample_response = """
    Here are some key points about machine learning:
    
    1. Machine learning is a field of AI
    <quote>Machine learning is a field of artificial intelligence</quote>
    
    2. Deep learning is a subset
    <quote>Deep learning is a subset of machine learning</quote>
    
    3. Recent advances
    <quote>The field has seen significant advances in recent years</quote>
    
    4. Invalid quote (this should fail validation)
    <quote>This quote does not exist in the text</quote>
    """
    
    print("\n=== Testing Quote Extraction and Validation ===")
    print("\nSample PDF Text:")
    print(sample_pdf_text)
    
    print("\nSample Claude Response:")
    print(sample_response)
    
    print("\nValidation Results:")
    results = extract_and_validate_quotes(sample_response, sample_pdf_text)
    
    print("\nDetailed Results:")
    for quote_num, data in results.items():
        status = "✅" if data["is_valid"] else "❌"
        print(f"\n{status} {quote_num}:")
        print(f"Quote: {data['quote']}")
        print(f"Valid: {data['is_valid']}")

def get_claude_response(prompt, doc_path="documents/unlearning.pdf", doc_url="https://arxiv.org/abs/2410.08827"):
    """
    Send a prompt to Claude 3.7 and get the response
    """
    # Initialize the Anthropic client
    api_key = os.getenv("ANTHROPIC_API_KEY")
    
    with open(doc_path, "rb") as f:
        b64_pdf = base64.b64encode(f.read()).decode()

    pdf_b64_block = {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": b64_pdf
        }
    }

    doc_block = pdf_b64_block

    client = anthropic.Anthropic(
        # defaults to os.environ.get("ANTHROPIC_API_KEY")
        api_key=api_key,
    )
    messages = [
        {
            "role": "user",
            "content": [
                doc_block,
                {
                    "type": "text",
                    "text": prompt
                }
            ]
        }
    ]

    message = client.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=1024,
        messages=messages
    )

    
    return message.content[0].text


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

def jaccard(a: list[str], b: list[str]) -> float:
    """
    Calculate Jaccard similarity between tjjjjjwo lists of strings.
    Jaccard similarity is the ratio of the size of the intersection to the size of the union.
    
    Args:
        a: First list of strings
        b: Second list of strings
        
    Returns:
        float: Jaccard similarity score between 0 and 1
    """
    # Convert lists to sets for efficient intersection/union operations
    sa, sb = set(a), set(b)
    # Calculate intersection and union
    inter = sa & sb
    union = sa | sb
    # Return 0 if union is empty, otherwise return ratio of intersection to union
    return 0.0 if not union else len(inter)/len(union)

def best_jaccard(quote: str, pdf: str, words_per_window: int = 10) -> float:
    """
    Find the best Jaccard similarity between a quote and any window of text in the PDF.
    Uses a sliding window approach with fixed window size.
    
    Args:
        quote: The quote to search for
        pdf: The text to search in
        words_per_window: Number of words in each window (default 10)
             
    Returns:
        float: The highest Jaccard similarity score found (between 0 and 1)
    """
    # Split both texts into words
    qtoks = quote.split()
    ptoks = pdf.split()
    
    # Create a sliding window with fixed size
    window = deque(maxlen=words_per_window)
    best = 0.0
    
    # Slide the window through the PDF text
    for tok in ptoks:
        window.append(tok)
        
        # Only start comparing once we have a full window
        if len(window) == words_per_window:
            # Calculate Jaccard similarity between quote and current window
            current_score = jaccard(qtoks, list(window))
            best = max(best, current_score)
            
            # Early exit if we find a perfect match
            if best == 1.0:
                break
                
    return best

def find_relevant_text(text: str, quote: str, matching_sequence_length: int = 4) -> str:
    """
    Find the relevant portion of text that contains the quote by matching sequences of words.
    
    Args:
        text: The full text to search in
        quote: The quote to find in the text
        matching_sequence_length: Number of words to use for matching sequences
        
    Returns:
        str: The relevant portion of text containing the quote, or empty string if not found
    """
    text_words = text.split()
    quote_words = quote.split()
    
    # If quote is empty or text is empty, return 0
    if not quote_words or not text_words:
        return ""
        
    # Need at least matching_sequence_length words in quote to use this method
    if len(quote_words) < matching_sequence_length:
        return ""
        
    # Create n-word sequences
    def get_sequences(words, n):
        return [' '.join(words[i:i+n]) for i in range(len(words)-n+1)]
        
    text_sequences = get_sequences(text_words, matching_sequence_length)
    quote_start_sequence = ' '.join(quote_words[:matching_sequence_length])
    quote_end_sequence = ' '.join(quote_words[-matching_sequence_length:])
    
    # Find the start sequence in the text
    try:
        start_idx = text_sequences.index(quote_start_sequence)
    except ValueError:
        return ""  # Start sequence not found
        
    # Find the end sequence in the text, starting from the start index
    try:
        end_idx = text_sequences.index(quote_end_sequence, start_idx)
    except ValueError:
        return ""  # End sequence not found
        
    # Get the relevant substring of text (convert from sequence index to word index)
    start_word_idx = start_idx
    end_word_idx = end_idx + (matching_sequence_length - 1)  # Add (n-1) to get the last word of the n-word sequence
    return ' '.join(text_words[start_word_idx:end_word_idx + 1])

def find_relevant_text_claude(text: str, quote: str, start_tag: str = "<quote>", end_tag: str = "</quote>") -> str:
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
    # Initialize the Anthropic client
    api_key = os.getenv("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)
    
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
        message = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        response = message.content[0].text.strip()
        
        # Check if response is "NOT FOUND"
        if response == "NOT FOUND":
            return ""
            
        # Extract text between start and end tags
        import re
        pattern = f'{re.escape(start_tag)}(.*?){re.escape(end_tag)}'
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()
        else:
            print(f"Warning: Could not find tags in Claude response: {response}")
            return ""
            
    except Exception as e:
        print(f"Error using Claude to find relevant text: {e}")
        return ""

def check_quote_to_text_ratio(text: str, quote: str, matching_sequence_length: int = 4, use_claude: bool = True) -> float:
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
    relevant_text = find_relevant_text_claude(text, quote) if use_claude else find_relevant_text(text, quote, matching_sequence_length)
    
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


def check_quote_in_text(text: str, quote: str) -> float:
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
    
    # Save cleaned versions to files
    parsed_dir = "parsed_pdfs"
    os.makedirs(parsed_dir, exist_ok=True)
    
    # Save cleaned text
    with open(os.path.join(parsed_dir, "cleaned_text.txt"), 'w', encoding='utf-8') as f:
        f.write(clean_text_norm)
    
    # Save cleaned quote
    with open(os.path.join(parsed_dir, "cleaned_quote.txt"), 'w', encoding='utf-8') as f:
        f.write(clean_quote_norm)
    
    # Check if quote exists in text
    is_found = (
        clean_quote_lower in clean_text_lower
        or quote_lower in text_lower # quote is directly in text
        or quote_lower.strip() in text_lower
        or clean_quote_lower in clean_no_hyphen_text_lower 
        or quote_lower in no_hyphen_text_lower
        or quote_norm in text_norm
        or clean_quote_norm in clean_text_norm 
    )
    
    check_quote_to_text_ratio(clean_text_norm, clean_quote_norm)

    if is_found:
        return True

    return check_quote_to_text_ratio(clean_text_norm, clean_quote_norm) > 0.9


def extract_and_validate_quotes(
    claude_response: str, 
    pdf_text: str,
    quote_start: str = "<quote>",
    quote_end: str = "</quote>"
) -> dict:
    """
    Extract quotes from Claude's response and validate them against the PDF text.
    
    Args:
        claude_response (str): The response from Claude
        pdf_text (str): The text extracted from the PDF
        quote_start (str): The string that marks the start of a quote
        quote_end (str): The string that marks the end of a quote
        
    Returns:
        dict: A dictionary where the key is a string containing a the quote 
        number and the value is another dictionary. This inner dictionary has 
        two keys `quote` which gives you the quote the claude had in its
        response, and `similarity_score` which gives you a float indicating the 
        similarity between claude's quote and the parsed pdf's text.
    """
    # Regular expression to find quotes with custom start/end markers
    quote_pattern = f'{re.escape(quote_start)}(.*?){re.escape(quote_end)}'
    
    # Find all quotes in the response
    quotes = re.findall(quote_pattern, claude_response, re.DOTALL)
    
    # Dictionary to store validation results
    validation_results = {}
    
    # Validate each quote
    for i, quote in enumerate(quotes, 1):
        # Clean the quote (remove extra whitespace)
        clean_quote = ' '.join(quote.split())
        
        # Check if the quote exists in the PDF text
        similarity_score = check_quote_in_text(pdf_text, clean_quote)
        
        # Store the result
        validation_results[f"Quote {i}"] = {
            "quote": clean_quote,
            "similarity_score": similarity_score,
        }
    
    
    return validation_results


def read_prompt_from_file(file_path: str):
    try:
        with open(file_path, 'r') as f:
            return f.read().strip()
    except Exception as e:
        print(f"Error reading prompt file: {e}")
        return None


def main():
    #* Test quote extraction
    # test_quote_extraction()
    # assert False
    
    #* Test claude api
    # Read prompt from file
    prompt_name = "prompt.txt"
    prompt_dir = "prompts"
    prompt_path = os.path.join(prompt_dir, prompt_name)
    prompt = read_prompt_from_file(prompt_path)
    if prompt is None:
        print("Failed to read prompt from file")
        return
        
    try:
        # Get response from Claude
        response = get_claude_response(prompt)
        
        # Get PDF text for validation
        pdf_name = "unlearning.pdf"
        pdf_dir = "documents"
        pdf_path = os.path.join(pdf_dir, pdf_name)
        pdf_text = pdf_to_text(pdf_path)
        
        
        # Extract and validate quotes
        validation_results = extract_and_validate_quotes(response, pdf_text)
        # Save results to JSON file
        output_dir = "results"
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, "validation_results.json")
        
        with open(output_file, 'w') as f:
            json.dump(validation_results, f, indent=2)
            
        print(f"\nResults saved to: {output_file}")
        
    except Exception as e:
        print(f"An error occurred: {e}")

    #* Test pdf parser
    # file_name = "unlearning.pdf"
    # file_dir = "documents"
    # file_path = os.path.join(file_dir, file_name)
    # pdf_to_text(file_path)

if __name__ == "__main__":
    main() 