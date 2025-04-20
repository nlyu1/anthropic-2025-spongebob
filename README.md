# anthropic-2025-spongebob: OpenWebUI with Claude-Powered PDF Search

This project enhances the [Open WebUI](https://github.com/open-webui/open-webui) chat interface by integrating a custom backend service. This backend leverages Anthropic's Claude model and the Message Correlation Protocol (MCP) to enable intelligent conversations augmented by reliable PDF document search and citation capabilities.

## Core Features

*   **Enhanced Chat Interface:** Utilizes the feature-rich Open WebUI frontend.
*   **PDF Upload:** Allows users to upload PDF documents directly through the chat interface.
*   **Contextual PDF Search:** Enables users to ask questions about uploaded PDFs within their chat conversation.
*   **Claude Integration:** Uses Anthropic's Claude models for powerful language understanding and generation.
*   **Reliable Citations:** Employs MCP tools to interact with PDFs, aiming for accurate information retrieval and citation from the documents.

## Tech Stack

**Backend:**

*   **Programming Language:** Python 3.10+
*   **Web Framework:** FastAPI
*   **Server:** Uvicorn
*   **LLM API:** Anthropic Python SDK
*   **Tool Protocol:** MCP (`mcp` library)
*   **PDF Processing:** PyMuPDF (`fitz`), `pdfminer.six` (Note: `pdfminer.six` seems included in dependencies but `PyMuPDF` is used in `pdf_search.py`)
*   **Configuration:** Pydantic Settings, python-dotenv
*   **Package/Environment Management:** `uv`
*   **Other:** OpenAI Python SDK (optional, used within `pdf_search.py` for specific search methods), `httpx`, `sse-starlette`

**Frontend (`front-test/` directory):**

*   **Framework:** SvelteKit
*   **Language:** TypeScript
*   **Styling:** Tailwind CSS
*   **Build Tool:** Vite
*   **Package Management:** npm
*   **UI Components:** Various libraries including Bits UI, Tippy.js, Katex, Mermaid, etc. (inherited from OpenWebUI)

## Project Structure

```
root/
│
├── README.md                ← This file
├── breakdown.md             ← Initial architectural plan (current implementation differs)
├── files/                   ← Default storage location for uploaded PDFs
│
├── frontend/ (or front-test/) ← OpenWebUI frontend code (SvelteKit)
│   ├── src/
│   ├── package.json
│   └── .env.local           ← Frontend configuration (needs creation)
│
├── backend/                 ← FastAPI backend application
│   ├── app/                 ← Core FastAPI application package
│   │   ├── __init__.py
│   │   ├── main.py          ← FastAPI app setup, CORS, API endpoint definitions
│   │   ├── frontend_router.py ← Defines `/v1/*` API routes for OpenWebUI compatibility
│   │   ├── orchestrator.py  ← Manages Claude API interaction, MCP client logic, PDF loading
│   │   ├── pdf_loading_utils.py ← Helpers for loading PDF content for Claude context
│   │   └── settings.py      ← Pydantic models for loading .env configuration
│   │
│   ├── mcp_server/          ← Separate process running the MCP tool server
│   │   ├── server.py        ← Runs the MCP server exposing the pdf_search tool
│   │   ├── pdf_search.py    ← Implements the actual PDF search logic (using PyMuPDF)
│   │   └── pyproject.toml   ← Dependencies specific to the MCP server process
│   │
│   ├── tests/               ← Backend tests
│   ├── pyproject.toml       ← Main backend dependencies (managed by uv)
│   └── uv.lock              ← Backend lock file
│
├── .env                     ← Root environment configuration (needs creation)
├── .gitignore
└── ... (other config files, Dockerfiles, etc.)
```

**Key Components:**

*   **`frontend/` (`front-test/`):** The user interface, based on OpenWebUI. Communicates with the backend via HTTP requests.
*   **`backend/app/main.py` & `backend/app/frontend_router.py`:** The FastAPI application entry point. Defines API routes that the frontend calls (e.g., `/api/upload`, `/v1/chat/completions`).
*   **`backend/app/orchestrator.py`:** The core logic unit. It receives chat messages, prepares context (including loaded PDF content), interacts with the Anthropic Claude API, and acts as an MCP *client* to call tools exposed by the MCP server.
*   **`backend/mcp_server/`:** A separate Python process acting as an MCP *server*. It exposes the `search_pdf` tool, whose implementation resides in `pdf_search.py`. This server is started and managed implicitly by the `orchestrator.py` when it needs to call the tool.
*   **`backend/mcp_server/pdf_search.py`:** Contains the function that extracts text from PDFs (`PyMuPDF`) and performs searches based on user queries received via MCP.
*   **`files/`:** The directory where uploaded PDF files are stored by default.

## Setup and Running

**Prerequisites:**

*   Python 3.10 or higher
*   `uv` (Python package/environment manager): Install via `pip install uv` or follow official instructions.
*   Node.js (v18.13+ recommended) and npm

**Steps:**

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd anthropic-2025-spongebob
    ```

2.  **Configure Environment Variables:**
    Create a file named `.env` in the **project root** directory. Add your Anthropic API key:
    ```env
    # Required: Your Anthropic API Key
    ANTHROPIC_API_KEY=your_anthropic_api_key_here

    # Optional: Specify allowed origins for CORS (comma-separated)
    # Defaults to allowing http://localhost:3210, http://127.0.0.1:3210, http://localhost:5173 if not set
    # CORS_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"

    # Optional: Specify a different directory for uploaded files
    # Defaults to './backend/files/' relative to where the backend process is run
    # FILES_DIR="/path/to/your/pdf/storage"

    # Optional: API Key for Fireworks AI if using LLM-based search in pdf_search.py
    # FIREWORKS_API_KEY=your_fireworks_api_key_here
    ```
    *Note: Ensure the `.env` file is added to your `.gitignore` to avoid committing secrets.*

3.  **Set Up and Run Backend:**
    *   Navigate to the backend directory:
        ```bash
        cd backend
        ```
    *   Create and activate a virtual environment using `uv`:
        ```bash
        uv venv
        source .venv/bin/activate  # Linux/macOS
        # .\.venv\Scripts\activate  # Windows PowerShell
        ```
    *   Install dependencies:
        ```bash
        uv pip install -r requirements.txt # Or uv pip install . if using pyproject.toml directly
        # Consider 'uv pip install .[dev]' if you need development dependencies like 'requests' for tests
        ```
    *   Run the FastAPI server:
        ```bash
        # Make sure you are in the backend/ directory with the venv activated
        uvicorn app.main:app --reload --port 8000
        ```
        The backend server should now be running at `http://localhost:8000`.

4.  **Set Up and Run Frontend:**
    *   In a **new terminal**, navigate to the frontend directory:
        ```bash
        cd ../front-test # Or the correct path to your frontend directory
        ```
    *   Install Node.js dependencies:
        ```bash
        npm install
        ```
    *   **Configure Frontend API Endpoint:** Create a file named `.env.local` inside the `front-test` directory with the following content, pointing to your running backend:
        ```env
        NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/v1
        NEXT_PUBLIC_API_KEY=dummy_key # Required by OpenWebUI, value doesn't matter for local backend
        # Add other OpenWebUI specific env vars as needed, e.g.:
        # ENABLE_SIGNUP=false
        ```
        *(Consult OpenWebUI documentation for other relevant frontend environment variables)*
    *   Run the frontend development server:
        ```bash
        npm run dev
        ```

5.  **Access the Application:**
    Open your web browser and navigate to the URL provided by the frontend process (usually `http://localhost:5173`).

## Configuration Details

*   **`.env` (Project Root):**
    *   `ANTHROPIC_API_KEY`: **Required** for Claude API access.
    *   `CORS_ORIGINS`: Controls which frontend origins can access the backend API. Adjust if your frontend runs on a different port. Defaults are usually `http://localhost:5173`, `http://127.0.0.1:5173`.
    *   `FILES_DIR`: Specifies the directory to store uploaded PDFs. Defaults to `backend/files/`.
    *   `FIREWORKS_API_KEY`: Only needed if the LLM-based search (`find_relevant_text_llm`) within `pdf_search.py` is actively used.
*   **`front-test/.env.local`:**
    *   `NEXT_PUBLIC_API_BASE_URL`: **Required**. Tells the frontend where the backend API (specifically the OpenAI-compatible `/v1` endpoints) is located (e.g., `http://localhost:8000/v1`).
    *   `NEXT_PUBLIC_API_KEY`: Required by OpenWebUI, but the value isn't used by our backend. Set to any non-empty string like `dummy_key`.

## How It Works (Architecture Flow)

1.  **User Interaction:** The user types a message or uploads a PDF in the OpenWebUI frontend (`front-test`).
2.  **Frontend Request:** The frontend sends requests to the FastAPI backend API endpoints (e.g., `POST /api/upload` for files, `POST /v1/chat/completions` for messages).
3.  **FastAPI Routing:** `backend/app/main.py` receives the request and routes it to the appropriate handler function in `backend/app/frontend_router.py`.
4.  **Orchestration:** For chat messages, the request lands in `backend/app/orchestrator.py`.
    *   The orchestrator loads relevant PDF content using `pdf_loading_utils.py`.
    *   It constructs the message history, including PDF context.
    *   It calls the Anthropic Claude API (`messages.create`).
5.  **Tool Use (MCP):**
    *   If Claude decides to use the `search_pdf` tool, the orchestrator (acting as an MCP client) connects to the MCP server (`backend/mcp_server/server.py`).
    *   The orchestrator sends the tool call request (`search_pdf` with parameters) to the MCP server via the MCP protocol.
6.  **MCP Server Execution:**
    *   The MCP server receives the request and executes the `search_pdf` function in `backend/mcp_server/pdf_search.py`.
    *   This function reads the specified PDF (using `PyMuPDF`), performs the search logic, and prepares the results.
    *   The MCP server sends the results back to the orchestrator (MCP client).
7.  **Continuing Conversation:**
    *   The orchestrator receives the tool results and adds them to the conversation history.
    *   It calls the Claude API again with the updated history.
    *   This loop continues until Claude provides a final text response without requesting further tool calls.
8.  **Response to Frontend:** The final aggregated text response from the orchestrator is sent back through FastAPI to the OpenWebUI frontend, which displays it to the user. For streaming responses, chunks are sent via Server-Sent Events (SSE).