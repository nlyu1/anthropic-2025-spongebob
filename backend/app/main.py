import shutil
import os
import json
import asyncio
import logging # Import logging
from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from .orchestrator import chat_with_tools
from .tools.pdf_search import search_pdf # Import the tool function
from .settings import cors_origins, files_dir

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

@app.post("/api/chat")
async def chat_endpoint(req: Request):
    logger.info("POST /api/chat endpoint called")
    body = None
    try:
        body = await req.json()
        if "messages" not in body or not isinstance(body["messages"], list) or not body["messages"]:
             logger.warning("Invalid request body format in /api/chat")
             raise HTTPException(status_code=400, detail="Invalid request body: 'messages' field is missing, not a list, or empty.")
        first_message_role = body["messages"][0].get("role", "unknown")
        logger.info(f"Received chat request. First message role: {first_message_role}, Total messages: {len(body['messages'])}")
    except json.JSONDecodeError:
        logger.error("Failed to decode JSON body in /api/chat")
        raise HTTPException(status_code=400, detail="Invalid JSON body.")
    except Exception as e:
        logger.error(f"Error processing request body in /api/chat: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Error processing request: {e}")

    async def event_stream():
        logger.info("Starting SSE event stream for /api/chat")
        try:
            async for delta in chat_with_tools(body["messages"]):
                # Ensure delta is serializable before sending
                try:
                    if isinstance(delta, dict):
                        # Optional: Log specific delta types if needed for debugging
                        # if delta.get("type") == "tool_use":
                        #     logger.info(f"SSE sending tool_use: {delta.get('name')}")
                        yield f"data: {json.dumps(delta, ensure_ascii=False)}\n\n"
                    else:
                        logger.warning(f"Unexpected delta type in stream: {type(delta)}")
                        yield f"data: {json.dumps(str(delta), ensure_ascii=False)}\n\n"
                except TypeError as e:
                     logger.error(f"Error serializing delta: {delta}, Error: {e}", exc_info=True)
                     # Optionally send an error event to the client
                     # yield f"event: error\ndata: {json.dumps({'error': 'Serialization failed'})}\n\n"
                     continue # Skip this delta
            logger.info("SSE event stream completed successfully")
            yield "event: done\ndata: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Error during chat stream generation: {e}", exc_info=True)
            # Send an error event to the client
            error_payload = json.dumps({"error": "An error occurred during streaming.", "details": str(e)})
            yield f"event: error\ndata: {error_payload}\n\n"
            # Ensure the stream terminates even on error
            logger.info("SSE event stream closing after error")
            yield "event: done\ndata: [DONE]\n\n"

    return EventSourceResponse(event_stream())
