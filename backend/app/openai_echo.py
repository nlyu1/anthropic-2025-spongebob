from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
import json, asyncio, uuid, datetime, logging
import os
from anthropic import Anthropic
import sys
import re

# Import PDF search functionality
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from mcp_server.pdf_search import search_pdf_content

# Import settings for API key
from .settings import anthropic_api_key, files_dir

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize Anthropic client
anthropic_client = Anthropic(api_key=anthropic_api_key)

# System prompt for PDF processing
SYSTEM_PROMPT = """You are a helpful AI assistant specialized in answering questions based on PDF documents.
When answering questions, always refer to the contents of the provided PDF and avoid making up information.
If the information cannot be found in the PDF, clearly state that fact.
Use direct quotes from the PDF when appropriate and cite page numbers or sections if available."""

@router.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [{
            "id": "pdf-master",                 # shown in WebUI dropdown
            "object": "model",
            "created": int(datetime.datetime.utcnow().timestamp()),
            "owned_by": "local"
        }]
    }

# Single-model detail route
@router.get("/v1/models/{model_id}")
async def get_model(model_id: str):
    return {
        "id": model_id,
        "object": "model",
        "created": 0,
        "owned_by": "local"
    }

async def process_pdf_query(user_query: str, pdf_file_id: str) -> str:
    """
    Process a user query against a specific PDF file.
    
    Args:
        user_query: The user's question about the PDF
        pdf_file_id: The ID of the PDF file
        
    Returns:
        A response string with information from the PDF
    """
    logger.info(f"Processing PDF query: '{user_query}' for file ID: {pdf_file_id}")
    
    # Get filename from file_id (in production, you'd have a DB mapping file_ids to filenames)
    # For now, we'll use the directory listing since you mentioned we should assume only 1 PDF
    pdf_files = [f for f in os.listdir(files_dir) if f.endswith('.pdf')]
    
    if not pdf_files:
        return "No PDF files found in the system. Please upload a PDF file first."
    
    # Assume the first PDF in the directory is the one we want (as per the requirement)
    pdf_file = pdf_files[0]
    pdf_name = pdf_file.replace('.pdf', '')
    
    logger.info(f"Using PDF file: {pdf_file}")
    
    # Extract keywords from the user query
    # This is a simple approach that can be improved with NLP techniques
    stop_words = {'a', 'an', 'the', 'in', 'on', 'at', 'is', 'are', 'was', 'were', 'be', 'been', 'being'}
    words = [word.lower() for word in re.findall(r'\b\w+\b', user_query) if word.lower() not in stop_words]
    
    # Create a list to store all search results
    all_results = []
    
    # Search for the entire query first
    search_result = search_pdf_content(pdf_name, user_query)
    if search_result.get("query_exists", False):
        all_results.extend(search_result.get("matches", []))
    
    # If no direct matches, try with individual keywords
    if not all_results:
        for word in words:
            if len(word) < 4:  # Skip very short words
                continue
            
            result = search_pdf_content(pdf_name, word)
            if result.get("query_exists", False):
                all_results.extend(result.get("matches", []))
            
            # Limit the number of results to avoid token overload
            if len(all_results) >= 5:
                break
    
    # If no results found at all
    if not all_results:
        return f"I couldn't find any relevant information about '{user_query}' in the PDF. Please try rephrasing your question or ask about a different topic covered in the document."
    
    # Prepare context for Claude
    context = "\n\n".join(all_results[:5])  # Limit to top 5 results
    
    # Prepare messages for Claude
    messages = [
        {
            "role": "user",
            "content": f"Here are sections from a PDF document:\n\n{context}\n\nBased ONLY on the above content, please answer this question: {user_query}"
        }
    ]
    
    # Get Claude's response
    try:
        response = anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            system=SYSTEM_PROMPT,
            messages=messages,
            max_tokens=2000
        )
        
        return response.content[0].text
    except Exception as e:
        logger.error(f"Error calling Anthropic API: {e}")
        return f"I encountered an error while processing your request: {str(e)}"

@router.post("/v1/chat/completions")
async def completions(req: Request):
    body = await req.json()  # {"messages":[...], "stream":true, "files":[...]}
    user_msg = body["messages"][-1]["content"]
    stream_mode = body.get("stream", True)
    
    # Check if files are included in the request
    files = body.get("files", [])
    file_info = ""
    if files:
        file_info = "\nFile references: " + ", ".join([f"{file.get('type', 'file')}: {file.get('id', 'unknown')}" for file in files])
        logger.info(f"Chat completion request includes files: {files}")
    
    # Simple echo response - keep this as a dummy for now
    reply_text = f"Echo: {user_msg}{file_info}"
    
    message_id = str(uuid.uuid4())
    created_time = int(datetime.datetime.utcnow().timestamp())
    model = body.get("model", "pdf-master")
    
    # For non-streaming mode, return the complete response
    if not stream_mode:
        return {
            "id": message_id,
            "object": "chat.completion",
            "created": created_time,
            "model": model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": reply_text
                },
                "finish_reason": "stop"
            }]
        }
    
    # For streaming mode
    async def event_stream():
        # Split by words for demonstration
        for word in reply_text.split():
            chunk = {
                "id": message_id,
                "object": "chat.completion.chunk",
                "created": created_time,
                "model": model,
                "choices": [{
                    "delta": {"content": word + " "},
                    "index": 0,
                    "finish_reason": None
                }]
            }
            yield json.dumps(chunk)
            await asyncio.sleep(0.05)   # simulate latency
        
        # Send final chunk with finish_reason: "stop"
        final_chunk = {
            "id": message_id,
            "object": "chat.completion.chunk",
            "created": created_time,
            "model": model,
            "choices": [{
                "delta": {},
                "index": 0,
                "finish_reason": "stop"
            }]
        }
        yield json.dumps(final_chunk)
        yield "[DONE]"

    return EventSourceResponse(event_stream(),
                               media_type="text/event-stream") 