import os
import json
import base64
import fitz  # pip install PyMuPDF
from dotenv import load_dotenv
import anthropic
import re
from difflib import SequenceMatcher

# Load environment variables 
load_dotenv(override=True)

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
    doc = fitz.open(path)
    parts = []
    for page in doc:
        parts.append(page.get_text())      # 'text' is default; returns UTF‑8 str
    text = "\n".join(parts)
    print(f"{text=}")
    return text


def check_quote_in_text(text: str, quote: str) -> float:
    """
    Check if a quote exists in the given text.
    
    Args:
        text (str): The text to search in
        quote (str): The quote to search for
        
    Returns:
        float: A score between 0 and 1, where:
            - 1.0 means an exact match was found
            - Values between 0 and 1 represent similarity scores for partial matches
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
    
    text_norm  = normalise(text)
    quote_norm = normalise(quote)

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
    
    # Check if quote exists in text
    is_found = (
        clean_quote_lower in clean_text_lower
        or quote_lower in text_lower # quote is directly in text
        or quote_lower.strip() in text_lower
        or clean_quote_lower in clean_no_hyphen_text_lower 
        or quote_lower in no_hyphen_text_lower
        or quote_norm in text_norm
    )
    
    if is_found:
        return 1.0
    
    # If not found, calculate fuzzy match score
    # Use SequenceMatcher to find the best matching substring
    matcher = SequenceMatcher(None, clean_quote_lower, clean_text_lower)
    match = matcher.find_longest_match(0, len(clean_quote_lower), 0, len(clean_text_lower))
    
    if match.size > 0:
        # Calculate similarity score for the matching part
        matching_text = clean_text_lower[match.b:match.b + match.size]
        return SequenceMatcher(None, clean_quote_lower, matching_text).ratio()
    
    return 0.0


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
        dict: A dictionary containing the validation results for each quote
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
        print("Claude's response:")
        print(response)
        
        # Get PDF text for validation
        pdf_name = "unlearning.pdf"
        pdf_dir = "documents"
        pdf_path = os.path.join(pdf_dir, pdf_name)
        pdf_text = pdf_to_text(pdf_path)
        print("\n\n\npdf_text\n\n\n")
        print(pdf_text)
        print("\n\n\nend of pdf text\n\n")
        
        # Extract and validate quotes
        validation_results = extract_and_validate_quotes(response, pdf_text)
        print("\n\n\nPrinting Validation Resulsts\n\n")
        print(json.dumps(validation_results))
        
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