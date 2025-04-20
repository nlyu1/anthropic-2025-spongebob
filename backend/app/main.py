import shutil
import os
import json
import asyncio
import logging # Import logging
from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from .orchestrator import MCPClient
from .settings import cors_origins, files_dir

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
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

    try:
        client = MCPClient()
        await client.connect_to_server('./mcp_server/server.py')
        response = await client.process_query(body["messages"])
        await client.cleanup()
        # logger.info(f"[DEBUG] Chat response: {response}")
        return response
    except Exception as e:
        logger.error(f"Error in chat loop: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error in chat loop: {e}")
