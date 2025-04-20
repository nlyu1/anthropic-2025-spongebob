import requests
import json
import argparse

# Default API endpoint URL
DEFAULT_URL = "http://localhost:8000/api/chat"

def debug_chat_request(url: str, message: str):
    """
    Sends a single message to the chat API and prints the final response.
    """
    request_body = {
        "messages": [
            {"role": "user", "content": message}
        ]
    }

    # Standard headers, no SSE
    headers = {
        "Content-Type": "application/json"
    }

    try:
        print(f"Sending request to {url} with message: '{message[:50]}...'")
        with requests.post(url, json=request_body, headers=headers, timeout=180) as response:
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

            print("--- Full Response ---")
            # Print the entire response text
            print(response.text)
            print("--------------------")

    except requests.exceptions.RequestException as e:
        print(f"\n[Error] Failed to connect or communicate with the API at {url}: {e}")
    except Exception as e:
        print(f"\n[Error] An unexpected error occurred: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Debug script for the chat API endpoint.")
    parser.add_argument("message", type=str, help="The message to send to the chat API.")
    parser.add_argument("--url", type=str, default=DEFAULT_URL,
                        help=f"The URL of the chat API endpoint (default: {DEFAULT_URL}).")

    args = parser.parse_args()

    # Call the renamed function
    debug_chat_request(args.url, args.message) 