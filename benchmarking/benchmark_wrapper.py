# To run: just python benchmark_wrapper.py
import requests
import json
from typing import List, Optional, Dict, Any

# Assuming the FastAPI server runs on the default localhost:8000
BENCHMARK_URL = "http://localhost:8000/benchmark"

def run_benchmark(
    messages: List[Dict[str, Any]],
    claude_args: Optional[Dict[str, Any]] = None,
    pdf_root: Optional[str] = None,
    pdf_files: Optional[List[str]] = None,
    max_rounds: Optional[int] = None,
    timeout: int = 180 # Timeout for the request in seconds
) -> str:
    """
    Calls the /benchmark endpoint of the local FastAPI server.

    Args:
        messages: The conversation history (required).
        claude_args: Optional overrides for Anthropic API call.
        pdf_root: Optional directory to search for PDFs.
        pdf_files: Optional specific PDF filenames (no extension) to load.
        max_rounds: Optional maximum internal tool-use rounds.
        timeout: Request timeout in seconds.

    Returns:
        The plain text response from the benchmark endpoint.

    Raises:
        requests.exceptions.RequestException: If the network request fails.
        ValueError: If the server returns an error status code.
    """
    request_body = {
        "messages": messages,
        # Only include optional fields if they are not None
        # The endpoint handles defaults if fields are missing
        **( { "claude_args": claude_args } if claude_args is not None else {} ),
        **( { "pdf_root": pdf_root } if pdf_root is not None else {} ),
        **( { "pdf_files": pdf_files } if pdf_files is not None else {} ),
        **( { "max_rounds": max_rounds } if max_rounds is not None else {} ),
    }

    headers = {
        "Content-Type": "application/json"
    }

    print(f"Sending benchmark request to {BENCHMARK_URL}...")
    # print(f"Request body: {json.dumps(request_body, indent=2)}") # Uncomment for debug

    try:
        response = requests.post(
            BENCHMARK_URL,
            json=request_body,
            headers=headers,
            timeout=timeout
        )

        # Raise an exception for bad status codes (4xx or 5xx)
        response.raise_for_status()

        print("Benchmark request successful.")
        # Return the plain text content
        return response.text

    except requests.exceptions.Timeout:
        print(f"Error: Request timed out after {timeout} seconds.")
        raise
    except requests.exceptions.ConnectionError as e:
        print(f"Error: Could not connect to the server at {BENCHMARK_URL}. Ensure the server is running. Details: {e}")
        raise
    except requests.exceptions.HTTPError as e:
        # More specific error for HTTP errors (like 4xx, 5xx)
        print(f"Error: Server returned status {e.response.status_code}. Response: {e.response.text}")
        # Raise a more informative ValueError
        raise ValueError(f"Server error {e.response.status_code}: {e.response.text}") from e
    except requests.exceptions.RequestException as e:
        # Catch other potential request errors
        print(f"Error: An unexpected error occurred during the request: {e}")
        raise


if __name__ == "__main__":
    prompt = """GOAL  
• Read the attached PDF of name gettysburg_address.
• Produce a concise, integrated summary of its key ideas.  
• Support every claim with accurately transcribed quotations from the PDF by using the MCP tool **search_pdf(file, query)**.
• Do not call the tool search_pdf just to verify that the file exists. You can assume that it exists. 

MANDATORY WORKFLOW  
1. **Plan step‑by‑step.** Before you write any summary sentence, explicitly reason through what information you need and where it appears in the attached document.  
2. For each quotation you intend to use:  
   a. Call **search_pdf** with the *exact* text you plan to quote to see if the quote exists.  
   b. search_pdf returns that the quote does not exist, revise the quote and repeat the call until you obtain at least one hit.  
3. If any re‑check fails, immediately correct or remove the quotation.  
4. **Output format**:  
   • Present the summary in coherent paragraphs.  
   • Quotes begin with <quote> and end with <\quote>.  
   • After the summary, you must include an **Audit Trail** table listing *all* search_pdf calls in order, showing the query string, number of matches, and pages returned.

CONSTRAINTS  
• Do not fabricate or alter quotations.  
• Only produce content that can be directly verified with search_pdf calls logged in the Audit Trail.  
• Stay within 400 words for the main summary (citations excluded).

Summarize the file gettysburg_address"""

    sample_messages = [
        {"role": "user", 
         "content": prompt}
    ]
    sample_claude_args = {
        'model': 'claude-3-7-sonnet-latest', 
        'max_tokens': 5000,
        'system': "call search_pdf with pdf_dir=../benchmarking/files", 

    }
    # This will be fed to:
    # self.anthropic.messages.create(
    #         messages=messages,
    #         tools=available_tools,
    #         **self.claude_args 
    #     )

    # Call the function
    final_text_response = run_benchmark(
        messages=sample_messages,
        claude_args=sample_claude_args,
        pdf_root='./files', # This is ./benchmarking/files
        pdf_files=['gettysburg_address'],
        max_rounds=10, # maximum number of round trips between Anthropic and MCP servers
    )

    print("\n--- Benchmark Result (Final Text) ---")
    print(final_text_response)
    print("-------------------------------------")

    print("\n--- Benchmark Wrapper Demonstration Finished ---") 