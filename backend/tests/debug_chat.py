import requests
import json
import argparse

# Default API endpoint URL
DEFAULT_URL = "http://localhost:8000/api/chat"

def debug_chat_stream(url: str, message: str):
    """
    Sends a single message to the chat API and prints the streamed SSE response.
    """
    request_body = {
        "messages": [
            {"role": "user", "content": message}
        ]
    }

    headers = {
        "Accept": "text/event-stream"
    }

    try:
        print(f"Sending request to {url} with message: '{message[:50]}...'")
        with requests.post(url, json=request_body, headers=headers, stream=True, timeout=180) as response:
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

            print("--- Streaming Response ---")
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    # Process SSE lines
                    if decoded_line.startswith('data:'):
                        try:
                            # Extract JSON payload after "data: "
                            json_data = decoded_line[len('data: '):].strip()
                            if json_data == "[DONE]":
                                print("\n--- Stream Ended (DONE) ---")
                                break
                            # Avoid parsing empty data lines if any slip through
                            if json_data:
                                payload = json.loads(json_data)
                                # Pretty print the JSON payload
                                print(json.dumps(payload, indent=2))
                        except json.JSONDecodeError:
                            print(f"[Warning] Received non-JSON data line: {decoded_line}")
                        except Exception as e:
                            print(f"[Error] Could not process line: {decoded_line}, Error: {e}")
                    elif decoded_line.startswith('event: done'):
                        # Optional: Can log or handle this specific event marker
                        pass
                    elif decoded_line.startswith('event: error'):
                        # The error payload follows in the next 'data:' line
                        print(f"[Received Error Event] (Details in next data line)")
                    elif decoded_line.startswith(':'):
                         # SSE comment line, ignore
                         pass
                    # else:
                        # print(f"[Raw Line] {decoded_line}") # Uncomment for very raw debugging

            print("-------------------------")

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

    debug_chat_stream(args.url, args.message) 