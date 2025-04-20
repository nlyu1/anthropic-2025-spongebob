Below is a **“step‑zero → step‑N” migration map** that turns your current repo into a clean, three‑layered layout:

```
root/
│
├── frontend/                ← all Lobe Chat code lives here
│   └── (clone of lobehub/lobe-chat, no edits in‑tree)
│
├── backend/                 ← every line of server‑side Python
│   ├── app/                 ← FastAPI application package
│   │   ├── __init__.py
│   │   ├── main.py          ← *scaffolding* (routes, SSE, CORS)
│   │   ├── orchestrator.py  ← *prompt‑injection + Claude tool loop*
│   │   ├── tools/           ← logical home for **every** MCP tool
│   │   │   ├── __init__.py  (imports search_pdf and re‑exports mcp.tools)
│   │   │   └── pdf_search.py← pure search logic (99 % of your current file)
│   │   ├── schema.py        ← pulls JSON schema from FastMCP decorator
│   │   └── settings.py      ← Pydantic‑Settings / environs
│   │
│   ├── requirements.txt / pyproject.toml
│   └── README.md
│
└── files/                   ← uploaded PDFs land here
```

---

## 1  Frontend folder (`frontend/`)

TBD

---

## 2  Python backend (`backend/app`)

### 2.1  **Pure implementation layer** – `tools/pdf_search.py`

* **Goal:** zero dependencies on FastAPI / Anthropic.  
* **Keep** everything from today’s `pdf_search.py` except the CLI debugger at bottom.  
* Provide exactly **one** public function:

  ```python
  def search_pdf(pdf_name: str, query: str,
                 context_length: int = 2000, topk: int = 10,
                 files_dir: str = FILES_DIR) -> dict:
      ...
  ```

* Keep the FastMCP decorator if you like the automatic JSON‑schema:

  ```python
  from mcp.server.fastmcp import FastMCP
  mcp = FastMCP("pdf_tools")
  @mcp.tool()
  def search_pdf(...): ...        # wraps the pure function
  ```

  > **Pattern B twist:** you do **not** call `mcp.run()` anywhere; this file is imported by FastAPI.

### 2.2  **Prompt & Orleans‑logic layer** – `orchestrator.py`

```python
from anthropic import AsyncAnthropic
from .tools.pdf_search import mcp, search_pdf

client = AsyncAnthropic()
tool_descriptor = mcp.describe()["tools"][0]      # JSON schema

SYSTEM = """You are an expert research assistant.
When sourcing facts from PDFs, call the search_pdf tool first ..."""

async def chat_with_tools(messages: list[dict]):
    stream = await client.messages.create(
        model="claude-3-sonnet-20240229",
        system=SYSTEM,
        tools=[tool_descriptor],
        messages=messages,
        stream=True,
        max_tokens=1024
    )
    async for part in stream:
        if part.type == "tool_use":
            # run the tool in a worker thread – non‑blocking
            result = await asyncio.to_thread(search_pdf, **part.input)
            yield {"type": "tool_result", "id": part.id, "content": result}
            # recurse: feed result back to Claude
            messages += [
                {"role": "tool", "tool_call_id": part.id, "content": json.dumps(result)}
            ]
            async for delta in chat_with_tools(messages):
                yield delta
            return    # stop outer generator
        else:
            yield part
```

### 2.3  **Scaffolding layer** – `main.py`

```python
from fastapi import FastAPI, UploadFile, File, Request
from sse_starlette.sse import EventSourceResponse
from .orchestrator import chat_with_tools
from .tools.pdf_search import FILES_DIR
import shutil, os, json, asyncio

app = FastAPI()

@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    os.makedirs(FILES_DIR, exist_ok=True)
    dst = os.path.join(FILES_DIR, file.filename)
    with open(dst, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"pdf_name": file.filename[:-4]}        # strip .pdf

@app.post("/api/chat")
async def chat_endpoint(req: Request):
    body = await req.json()
    async def event_stream():
        async for delta in chat_with_tools(body["messages"]):
            yield f"data: {json.dumps(delta, ensure_ascii=False)}\n\n"
        yield "event: done\ndata: [DONE]\n\n"
    return EventSourceResponse(event_stream())
```

`main.py` knows **nothing** about pdfminer, Claude prompts, etc.; it just routes HTTP, manages SSE chunking, and calls the orchestrator.

---

## 3  Settings (`settings.py`)

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_key: str
    cors_origins: str = "http://localhost:3210"
    class Config: env_file = ".env"
```

Import `Settings()` wherever you need secrets; keep one `.env` at the repo root.

---

## 4  Running everything

```bash
# 1. start backend
cd backend
uvicorn app.main:app --reload --port 8000

# 2. start frontend
cd ../frontend
pnpm dev     # default :3210

# 3. point browser at http://localhost:3210
```

---

## 5  What lives where (cheat‑sheet)

| Concern | Folder | File | Notes |
|---------|--------|------|-------|
| **Raw PDF parsing / search** | `backend/app/tools/pdf_search.py` | pure function, no network |
| **Tool JSON schema** | same file (`mcp.tool()` decorator) | even in Pattern B we keep decorator for schema generation |
| **Claude / tool orchestration** | `backend/app/orchestrator.py` | system prompt, retry, token budgeting |
| **HTTP + streaming** | `backend/app/main.py` | Upload route, SSE chat, CORS |
| **Secrets / conf** | `backend/app/settings.py` + `.env` | Anthropic key, ports |
| **Chat UI** | `frontend/` | untouched upstream repo |
| **User PDFs** | `files/` | mounted or local |

---

## 6  How your *old* files map to the *new* layout

| Old file | New destination | Change required |
|----------|-----------------|-----------------|
| `mcp_server/server.py` | **deleted** | Functionality is now split: pure tool lives in `pdf_search.py`; HTTP moves to `main.py` |
| `mcp_server/pdf_search.py` | `backend/app/tools/pdf_search.py` | Remove CLI debugger block; keep FastMCP decorator |
| `mcp_client/client.py` | **deleted** | Lobe Chat becomes the client; orchestrator handles Claude calls |
| `files/` | unchanged | still the storage bucket |

---

### Why this feels clean

* **Clear contract edges**  
  * Front‑end ↔ Back‑end → HTTP+SSE only  
  * Back‑end scaffolding ↔ Business logic → function calls only  
* **No circular imports** – `main.py` imports `orchestrator`, which imports `tools`, which **doesn’t** import back up.  
* **Swap‑ability** – you can later move `tools` into a separate package, or spin them back out as real FastMCP servers, without touching `main.py` or `frontend/`.

Adapt the file paths/names to your taste, but keep the three‑tier mental model and you’ll sidestep the “spaghetti refactor” trap. Happy restructuring!