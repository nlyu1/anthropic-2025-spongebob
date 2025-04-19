import asyncio
import json
from anthropic import AsyncAnthropic

# Import the search_pdf function and the mcp object (for schema) from tools
from .tools.pdf_search import mcp, search_pdf
# Import specific variables needed from settings module
from .settings import anthropic_api_key, files_dir

# Initialize Anthropic client using the key from settings
# Handle potential missing key gracefully (though BaseSettings usually requires it)
try:
    client = AsyncAnthropic(api_key=anthropic_api_key)
except Exception as e:
    print(f"Error initializing Anthropic client: {e}")
    # Decide how to handle this - raise error, use a dummy client, etc.
    # For now, we'll let it potentially fail later if client is used without key.
    client = None # Or some placeholder if needed

# Get the tool schema from the mcp object
tool_descriptor = None
if hasattr(mcp, 'describe') and callable(mcp.describe):
    try:
        description = mcp.describe()
        if description and description.get("tools"):
            tool_descriptor = description["tools"][0] # Assumes search_pdf is the first/only tool
        else:
            print("Warning: MCP description format unexpected or empty.")
    except Exception as e:
        print(f"Error getting tool description from MCP: {e}")

if not tool_descriptor:
    print("Error: Could not obtain tool descriptor for search_pdf. Tool use will likely fail.")
    # Define a fallback or raise an error if the descriptor is critical
    # tool_descriptor = { ... manual schema ... }

SYSTEM = """You are an expert research assistant.
When sourcing facts from PDFs, call the search_pdf tool first before answering.
Use the search results to provide accurate and concise answers based *only* on the provided document content.
If the document doesn't contain the answer, state that explicitly.
"""

async def chat_with_tools(messages: list[dict]):
    """Handles the chat logic, calling Claude with the search_pdf tool."""
    if not client:
         # Handle the case where the client failed to initialize
         yield {"type": "error", "error": {"message": "Anthropic client not available."}}
         return
    if not tool_descriptor:
         yield {"type": "error", "error": {"message": "PDF search tool schema not available."}}
         return

    try:
        stream = await client.messages.create(
            model="claude-3-haiku-20240307", # Or sonnet, as in breakdown
            system=SYSTEM,
            tools=[tool_descriptor],
            messages=messages,
            stream=True,
            max_tokens=1024
        )
        async for part in stream:
            # Very basic streaming implementation for now
            # Follows the logic from breakdown.md
            if part.type == "content_block_delta":
                yield {"type": "content_block_delta", "delta": {"text": part.delta.text}}
            elif part.type == "message_delta":
                 # Yield stop reason etc if needed
                 yield {"type": "message_delta", "delta": {"stop_reason": part.delta.stop_reason}}
            elif part.type == "tool_use":
                tool_name = part.input.get('name')
                tool_input = part.input.get('input', {})
                tool_use_id = part.id

                yield {"type": "tool_use", "id": tool_use_id, "name": tool_name, "input": tool_input}

                if tool_name == 'search_pdf':
                     # Run the tool in a worker thread – non-blocking
                     # Pass the imported files_dir explicitly
                    result_dict = await asyncio.to_thread(search_pdf,
                                                        # Use imported files_dir
                                                        files_dir_override=files_dir,
                                                        **tool_input)
                    result_content = json.dumps(result_dict)

                    # Add tool result message back to the conversation history
                    messages.append({
                         "role": "user",
                         "content": [
                             {
                                 "type": "tool_result",
                                 "tool_use_id": tool_use_id,
                                 "content": result_content,
                                 # Include error status if present in result_dict
                                 "is_error": "error" in result_dict
                             }
                         ]
                     })

                     # Recurse: Feed result back to Claude for the next turn
                    async for delta in chat_with_tools(messages):
                        yield delta
                    return # Stop the outer generator after recursion finishes
                else:
                    # Handle unknown tool or potentially yield an error message
                    print(f"Warning: Received request for unhandled tool: {tool_name}")
                    # You might want to yield a specific error message back

            # Yield other event types if needed (e.g., message_start, message_stop)
            elif part.type == "message_start":
                yield {"type": "message_start", "message": part.message.to_dict()}
            elif part.type == "message_stop":
                yield {"type": "message_stop"}
            else:
                 print(f"Received unhandled stream part type: {part.type}")

    except Exception as e:
        print(f"Error during Claude API call or processing: {e}")
        # Yield a structured error event to the client
        yield {"type": "error", "error": {"message": f"Chat processing failed: {e}"}}

# Example of a simple placeholder if needed
# async def chat_with_tools(messages: list[dict]):
#     print("Orchestrator called with messages:", messages)
#     yield {"type": "content_block_delta", "delta": {"text": " Placeholder response."}}
#     await asyncio.sleep(0.1)
