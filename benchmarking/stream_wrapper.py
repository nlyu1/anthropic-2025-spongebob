# benchmarking/stream_wrapper.py
import requests
import json
import time
from typing import List, Optional, Dict, Any

# Target the new streaming endpoint
STREAM_URL = "http://localhost:8000/v1/chat/completions"

def run_stream_test(
    messages: List[Dict[str, Any]],
    claude_args: Optional[Dict[str, Any]] = None,
    pdf_root: Optional[str] = None,
    pdf_files: Optional[List[str]] = None,
    max_rounds: Optional[int] = None,
    timeout: int = 180 # Timeout for the *initial connection*
) -> None:
    """
    Calls the /v1/chat/completions endpoint with stream=True and prints tokens.

    Args:
        messages: The conversation history (required).
        claude_args: Optional overrides for Anthropic API call.
        pdf_root: Optional directory to search for PDFs.
        pdf_files: Optional specific PDF filenames (no extension) to load.
        max_rounds: Optional maximum internal tool-use rounds.
        timeout: Request timeout in seconds for establishing the connection.
                 The stream itself can run for longer.
    """
    request_body = {
        "messages": messages,
        "stream": True, # Explicitly request streaming
        # Only include optional fields if they are not None
        **( { "claude_args": claude_args } if claude_args is not None else {} ),
        **( { "pdf_root": pdf_root } if pdf_root is not None else {} ),
        **( { "pdf_files": pdf_files } if pdf_files is not None else {} ),
        **( { "max_rounds": max_rounds } if max_rounds is not None else {} ),
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream" # Important for SSE
    }

    print(f"Connecting to streaming endpoint {STREAM_URL}...")
    # print(f"Request body: {json.dumps(request_body, indent=2)}") # Uncomment for debug

    full_response_text = ""
    start_time = time.time()

    try:
        # Use stream=True for requests library to handle streaming connection
        with requests.post(
            STREAM_URL,
            json=request_body,
            headers=headers,
            timeout=timeout,
            stream=True
        ) as response:

            # Raise an exception for bad status codes (4xx or 5xx)
            response.raise_for_status()
            print("Connection successful. Receiving stream...\n---")

            # Iterate over the stream content line by line
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    # Check for the SSE data prefix
                    if decoded_line.startswith('data: '):
                        data_content = decoded_line[len('data: '):]

                        # Check for the OpenAI standard termination signal
                        if data_content.strip() == '[DONE]':
                            print("\n--- Stream finished ([DONE] received).")
                            break

                        try:
                            # Parse the JSON payload
                            payload = json.loads(data_content)
                            # Extract the token from the expected structure
                            if (payload.get('choices') and
                                len(payload['choices']) > 0 and
                                payload['choices'][0].get('delta') and
                                'content' in payload['choices'][0]['delta']):

                                token = payload['choices'][0]['delta']['content']
                                print(token, end='', flush=True) # Print token immediately
                                full_response_text += token
                            else:
                                # Log unexpected structure if needed
                                # print(f"\n[DEBUG] Unexpected payload structure: {payload}")
                                pass

                        except json.JSONDecodeError:
                            print(f"\n[ERROR] Failed to decode JSON: {data_content}")
                            continue # Skip malformed lines

            end_time = time.time()
            print(f"\n---\nStream completed in {end_time - start_time:.2f} seconds.")

    except requests.exceptions.Timeout:
        print(f"Error: Connection timed out after {timeout} seconds.")
        raise
    except requests.exceptions.ConnectionError as e:
        print(f"Error: Could not connect to the server at {STREAM_URL}. Ensure the server is running. Details: {e}")
        raise
    except requests.exceptions.HTTPError as e:
        print(f"Error: Server returned status {e.response.status_code}. Response: {e.response.text}")
        raise ValueError(f"Server error {e.response.status_code}: {e.response.text}") from e
    except requests.exceptions.RequestException as e:
        print(f"Error: An unexpected error occurred during the request: {e}")
        raise

    # Optionally return the full assembled text (though the primary goal is printing tokens)
    # return full_response_text


if __name__ == "__main__":
    # Use the same prompt and setup as benchmark_wrapper.py for comparison
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
        {"role": "user", "content": prompt}
    ]
    sample_claude_args = {
        'model': 'claude-3-7-sonnet-latest',
        'max_tokens': 5000,
        # 'system': "", # System prompt if needed
    }

    # Call the streaming test function
    run_stream_test(
        messages=sample_messages,
        claude_args=sample_claude_args,
        pdf_root='./files', # Relative to where this script is run (./benchmarking)
        pdf_files=['gettysburg_address'],
        max_rounds=10,
    )

    print("\n--- Stream Wrapper Demonstration Finished ---") 