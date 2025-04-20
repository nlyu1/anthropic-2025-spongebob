import shutil
import os
import json
import asyncio
import logging # Import logging
from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import datetime
import hashlib

from .orchestrator import MCPClient
from .settings import cors_origins, files_dir
from .openai_echo import router as echo_router

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configure CORS - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # dev: allow all, tighten later if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include OpenAI compatible router
app.include_router(echo_router)

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


# OpenAI-compatible PDF upload endpoint for Open WebUI
@app.post("/api/v1/files/")
async def upload_openai_compatible(file: UploadFile = File(...), process: bool = True):
    logger.info(f"POST /api/v1/files/ endpoint called with filename: {file.filename}, process={process}")
    # Reuse existing upload logic
    abs_files_dir = os.path.abspath(files_dir)
    os.makedirs(abs_files_dir, exist_ok=True)
    filename = os.path.basename(file.filename)
    
    # Generate a unique ID instead of using filename
    file_id = hashlib.md5(f"{filename}-{datetime.datetime.now().isoformat()}".encode()).hexdigest()[:16]
    
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

    filesize = os.path.getsize(dst)
    current_time = int(datetime.datetime.utcnow().timestamp())
    
    # Enhanced response format matching Open WebUI's expected schema
    response = {
        "id": file_id,
        "user_id": "local-user",
        "hash": file_id,
        "filename": filename,
        "data": {},
        "meta": {
            "name": filename,
            "content_type": "application/pdf",
            "size": filesize
        },
        "created_at": current_time,
        "updated_at": current_time
    }
    
    logger.info(f"POST /api/v1/files/ returning: {response}")
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
