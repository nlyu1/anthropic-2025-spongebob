import shutil
import os
import json
import asyncio
import logging # Import logging
from typing import List, Optional, Dict, Any, AsyncGenerator
import uuid, datetime
from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.responses import PlainTextResponse, StreamingResponse # Added PlainTextResponse and StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel # Added pydantic
from starlette.background import BackgroundTask

from .orchestrator import MCPClient
from .settings import cors_origins, files_dir

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# REMOVED: Default values based on existing code
# DEFAULT_CLAUDE_ARGS = {'model': 'claude-3-7-sonnet-latest', 'max_tokens': 5000}
# DEFAULT_PDF_ROOT = "./files"

# Pydantic model for the benchmark request body
class BenchmarkRequest(BaseModel):
    messages: List[Dict[str, Any]]
    claude_args: Optional[Dict[str, Any]] = None
    pdf_root: Optional[str] = None
    pdf_files: Optional[List[str]] = None
    max_rounds: Optional[int] = None # Added max_rounds

# OpenAI‑style chat completion request (streaming supported)
class ChatCompletionRequest(BaseModel):
    messages: List[Dict[str, Any]]
    claude_args: Optional[Dict[str, Any]] = None
    pdf_root: Optional[str] = None
    pdf_files: Optional[List[str]] = None
    max_rounds: Optional[int] = None
    stream: Optional[bool] = True

# Configure CORS
origins = [
    origin.strip()
    for origin in cors_origins.split(',')
    if origin.strip()
]
if not origins:
    # Default if CORS_ORIGINS is empty or not set
    origins = ["http://localhost:3210"] # Default from breakdown

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("FastAPI application starting up...")

@app.get("/check")
async def check_endpoint():
    logger.info("GET /check endpoint called")
    response = {"message": "hello world"}
    logger.info(f"GET /check returning: {response}")
    return response


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    logger.info(f"POST /api/upload endpoint called with filename: {file.filename}")
    abs_files_dir = os.path.abspath(files_dir)
    os.makedirs(abs_files_dir, exist_ok=True)
    # Basic security check for filename (avoid path traversal)
    filename = os.path.basename(file.filename)
    if not filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    dst = os.path.join(abs_files_dir, filename)
    logger.info(f"Attempting to save file to: {dst}")

    try:
        with open(dst, "wb") as f:
            shutil.copyfileobj(file.file, f)
        logger.info(f"Successfully saved file: {dst}")
    except Exception as e:
         logger.error(f"Failed to save file {dst}: {e}", exc_info=True)
         raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
    finally:
        file.file.close()

    # Return filename without .pdf extension, as per breakdown
    response = {"pdf_name": filename[:-4]}
    logger.info(f"POST /api/upload returning: {response}")
    return response

@app.post("/benchmark")
async def benchmark_endpoint(request_data: BenchmarkRequest):
    """
    Runs the chat process with customizable parameters for benchmarking.

    Accepts a JSON body with:
    - messages (List[Dict]): The conversation history, required.
    - claude_args (Optional[Dict]): Overrides for Anthropic API call (e.g., model, max_tokens).
                                     Defaults to {'model': 'claude-3-7-sonnet-latest', 'max_tokens': 5000}.
    - pdf_root (Optional[str]): Directory to search for PDFs. Defaults to './files'.
    - pdf_files (Optional[List[str]]): Specific PDF filenames (no extension) to load.
                                       Defaults to None (load all PDFs in pdf_root).
    - max_rounds (Optional[int]): Maximum internal tool-use rounds. Defaults to 10 (from orchestrator).

    Returns:
        PlainTextResponse: The final aggregated text response from the orchestrator.
    """
    logger.info(f"POST /benchmark endpoint called with data: {request_data.model_dump(exclude_unset=True)}") # Log provided data

    # Define defaults locally
    default_claude_args = {'model': 'claude-3-7-sonnet-latest', 'max_tokens': 5000}
    default_pdf_root = "./files"
    # Default max_rounds is handled by process_query if None is passed

    # Use provided claude_args or the default
    request_claude_args = request_data.claude_args if request_data.claude_args is not None else default_claude_args

    # Instantiate client with potentially customized claude_args
    client = MCPClient(claude_args=request_claude_args)

    # Determine pdf_root and pdf_files, using defaults if not provided
    pdf_root_to_use = request_data.pdf_root if request_data.pdf_root is not None else default_pdf_root
    pdf_files_to_use = request_data.pdf_files # Can be None, handled by process_query
    max_rounds_to_use = request_data.max_rounds # Can be None, handled by process_query

    try:
        logger.info(f"Connecting to server for benchmark...")
        await client.connect_to_server('./mcp_server/server.py')

        logger.info(f"Processing query for benchmark with pdf_root='{pdf_root_to_use}', pdf_files={pdf_files_to_use}, max_rounds={max_rounds_to_use or 'default'}")
        response_text = await client.process_query(
            messages=request_data.messages,
            pdf_root=pdf_root_to_use,
            pdf_files=pdf_files_to_use,
            max_rounds=max_rounds_to_use # Pass None or the value
        )

        logger.info(f"Cleaning up benchmark connection...")
        await client.cleanup()

        logger.info(f"Benchmark response length: {len(response_text)}")
        return PlainTextResponse(content=response_text)

    except HTTPException as e:
        # Re-raise HTTP exceptions directly (e.g., from MCPClient connection issues handled internally)
        logger.error(f"HTTP Exception during benchmark: {e.detail}", exc_info=True)
        if client and client.session: # Attempt cleanup
            await client.cleanup()
        raise e # Re-raise the original HTTPException
    except Exception as e:
        logger.error(f"Error during benchmark processing: {e}", exc_info=True)
        if client and client.session: # Attempt cleanup
            await client.cleanup()
        # Return a 500 error for internal server issues
        raise HTTPException(status_code=500, detail=f"Error during benchmark processing: {e}")

# ---------------------------------------------------------------------------
# Streaming chat endpoint (OpenAI compatible)
# ---------------------------------------------------------------------------

async def _openai_stream_payload(generator: AsyncGenerator[str, None]):
    """Wrap raw text tokens from ``MCPClient.stream_query`` into minimal
    OpenAI‑style SSE JSON payloads (one per yielded token)."""
    chunk_id = str(uuid.uuid4())
    created = int(datetime.datetime.utcnow().timestamp())
    async for token in generator:
        payload = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "choices": [
                {
                    "delta": {"content": token},
                    "index": 0,
                    "finish_reason": None,
                }
            ],
            "model": "claude-3-7-sonnet-latest",
        }
        yield f"data: {json.dumps(payload)}\n\n"

    # When exhausted, send the termination message per OpenAI protocol
    yield "data: [DONE]\n\n"


@app.post("/v1/chat/completions")
async def chat_completions(request_data: ChatCompletionRequest):
    """OpenAI compatible streaming chat completions endpoint."""
    logger.info("POST /v1/chat/completions called")

    # Defaults
    default_claude_args = {"model": "claude-3-7-sonnet-latest", "max_tokens": 5000}
    claude_args = request_data.claude_args or default_claude_args

    client = MCPClient(claude_args=claude_args)

    try:
        # Get the loop *before* potentially entering a different task context
        loop = asyncio.get_running_loop()

        await client.connect_to_server('./mcp_server/server.py')

        # Choose streaming or non‑streaming
        if request_data.stream:
            gen = client.stream_query(
                messages=request_data.messages,
                pdf_root=request_data.pdf_root or "./files",
                pdf_files=request_data.pdf_files,
                max_rounds=request_data.max_rounds or 10,
            )

            # Wrap generator into OpenAI payload SSE
            async def event_generator():
                try:
                    async for chunk in _openai_stream_payload(gen):
                        yield chunk.encode()
                finally:
                    # Ensure cleanup runs in the same event‑loop that
                    # created the MCP connection to avoid cross‑loop errors.
                    # Schedule cleanup on the original loop
                    loop.call_soon_threadsafe(lambda: asyncio.create_task(client.cleanup()))

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={"X-Accel-Buffering": "no"},  # disable proxy buffering
            )
        else:
            # Fallback to blocking process_query
            text = await client.process_query(
                messages=request_data.messages,
                pdf_root=request_data.pdf_root or "./files",
                pdf_files=request_data.pdf_files,
                max_rounds=request_data.max_rounds or 10,
            )
            await client.cleanup()
            return PlainTextResponse(content=text)

    except Exception as e:
        logger.error(f"Error in chat_completions: {e}", exc_info=True)
        if client and client.session:
            await client.cleanup()
        raise HTTPException(status_code=500, detail=str(e))