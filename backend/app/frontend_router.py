from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
import json, asyncio, uuid, datetime, logging
import os
from anthropic import Anthropic
import sys
import re

import shutil
import os
import json
import asyncio
import logging # Import logging
from typing import List, Optional, Dict, Any # Added typing imports
from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.responses import PlainTextResponse # Added PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel # Added pydantic
import datetime
import hashlib

from .orchestrator import MCPClient
from .settings import cors_origins, files_dir

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
SYSTEM_PROMPT = """You are connected to a MCP tool `pdf_search`. The current conversation pipeline works as follows:
1. Whenever you return a message of type 'text', it is displayed to the user. 
2. Whenever you return a message of type 'tool_use', it is passed to the `pdf_search` tool. The output of the tool is given back to you. However, make sure to vocally acknowledge the result / success of the tool call results, since the tool-use response will not be streamed to the client.
3. Your round ends and control is yielded back to the user for input, when you output message only containing type `text`. 
4. **Make at most 20 tool calls**. Make sure to check the number of tool calls you have made, and output. 
5. The frontend has rich markdown formatting capabilities.
6. When asked to reason about relevant documents, make sure to use the `pdf_search` tool to verify key claims. It searches the entire document for string-matches and returns the surrounding context. 

When asked for summaries, your instructions are as follows: 
GOAL  
• Read the attached PDF. 
• Produce a concise, integrated summary of its key ideas.  
• Support key claims in the summary with accurately transcribed quotations from the PDF by using the MCP tool **search_pdf(file, query)**. Output the quotes after they have been verified, since the tool-use results will not be streamed to the client.
• Do not call the tool search_pdf just to verify that the file exists. You can assume that it exists. 

MANDATORY WORKFLOW  
1. **Plan step‑by‑step.** Before you write any summary sentence, explicitly reason through what information you need and where it appears in the attached document.  
2. First output a candidate summary, together with a list of quotations you intend to use (check). 
2. For each quotation you intend to use:  
   a. Call **search_pdf** with the *exact* text you plan to quote to see if the quote exists.  
   b. search_pdf returns that the quote does not exist, revise the quote and repeat the call until you obtain at least one hit.  
3. If any re‑check fails, acknowledge the failure and immediately correct or remove the quotation.  
4. **Output format**:  
   • Present the summary in coherent paragraphs.  
   • Quotes begin with <quote> and end with <\quote>.  
   • After the summary, you must include an **Audit Trail** table listing *all* search_pdf calls in order, showing the query string, number of matches, and relevant matched content, if it exists. 

CONSTRAINTS  
• Do not fabricate or alter quotations.  
• Only finalize the summary based on information that can be directly verified with search_pdf calls logged in the Audit Trail.  
• Stay within 400 words for the final main summary (citations excluded). 
"""

@router.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [{
            "id": "Claude-trusted",                 # shown in WebUI dropdown
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
            model="claude-3.7-latest",
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
    claude_args = {
        'model': 'claude-3-7-sonnet-latest', 
        'max_tokens': 5000, 
        'system': SYSTEM_PROMPT
    }
    
    # Check if files are included in the request
    files = body.get("files", [])
    file_info = ""
    if files:
        file_info = "\nFile references: " + ", ".join([f"{file.get('type', 'file')}: {file.get('id', 'unknown')}" for file in files])
        logger.info(f"Chat completion request includes files: {files}")
    
    # Simple echo response - keep this as a dummy for now
    # reply_text = f"Echo: {user_msg}{file_info}"
    logger.info("POST /api/chat endpoint called")
    body = None
    try:
        body = await req.json()
        logger.info(f"[DEBUG] Received chat request: {body}")
        if "messages" not in body or not isinstance(body["messages"], list) or not body["messages"]:
             logger.warning("Invalid request body format in /api/chat")
             raise HTTPException(status_code=400, detail="Invalid request body: 'messages' field is missing, not a list, or empty.")
    except json.JSONDecodeError:
        logger.error("Failed to decode JSON body in /api/chat")
        raise HTTPException(status_code=400, detail="Invalid JSON body.")
    except Exception as e:
        logger.error(f"Error processing request body in /api/chat: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Error processing request: {e}")

    # Define default claude_args locally
    client = MCPClient(claude_args=claude_args) # Pass default args

    reply_text = "Error"
    try:
        await client.connect_to_server('./mcp_server/server.py')
        # MCPClient's process_query uses its own defaults for pdf_root and pdf_files if not passed
        reply_text = await client.process_query(body["messages"])
        await client.cleanup()
        # logger.info(f"[DEBUG] Chat response: {response}")
        # Return the raw response text for standard chat
    except Exception as e:
        logger.error(f"Error in chat loop: {e}", exc_info=True)
        if client and client.session: # Attempt cleanup if client exists
            await client.cleanup()
        # raise HTTPException(status_code=500, detail=f"Error in chat loop: {e}")
    
    message_id = str(uuid.uuid4())
    created_time = int(datetime.datetime.utcnow().timestamp())
    model = body.get("model", "Claude-trusted")
    
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
        # Send the response character by character to preserve formatting
        for char in reply_text:
            chunk = {
                "id": message_id,
                "object": "chat.completion.chunk",
                "created": created_time,
                "model": model,
                "choices": [{
                    "delta": {"content": char},  # Send the character directly
                    "index": 0,
                    "finish_reason": None
                }]
            }
            yield json.dumps(chunk)
            await asyncio.sleep(0.00)  # Optional: adjust delay if needed

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