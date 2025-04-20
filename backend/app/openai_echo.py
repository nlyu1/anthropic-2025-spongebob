from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
import json, asyncio, uuid, datetime, logging

router = APIRouter()
logger = logging.getLogger(__name__)

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