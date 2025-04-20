# Claude Trusted: OpenWebUI with Claude-Powered PDF Search & Citation

> Our custom MCP-powered verification workflow ensures Claude cites real evidence, reducing error rates on PDFs

This project enhances the [Open WebUI](https://github.com/open-webui/open-webui) chat interface by integrating a custom backend service for advanced PDF search and citation capabilities. It involves three main components:

1.  **Chat Frontend (`front-test/`):** The modified OpenWebUI (SvelteKit) user interface.
2.  **Chat Backend (`front-test/backend/`):** The standard OpenWebUI backend (Python), which serves the frontend.
3.  **Custom API Backend (`backend/`):** A separate FastAPI backend leveraging Anthropic's Claude model and MCP for PDF processing, search, and reliable citations.

## Benchmark
<img width="819" alt="image" src="https://github.com/user-attachments/assets/5dded91a-c91a-4d87-ac8d-5207f3669aad" />

## Core Features

*   **Enhanced Chat Interface:** Utilizes the feature-rich OpenWebUI frontend.
*   **PDF Upload & Context:** Allows users to upload PDFs and maintain context within conversations.
*   **Contextual PDF Search:** Enables natural language questions about uploaded PDFs.
*   **Claude Integration:** Uses Anthropic's Claude models via the Custom API Backend.
*   **Reliable Citations:** Employs a custom MCP-based verification workflow in the Custom API Backend.

## Tech Stack

**Custom API Backend (`backend/`):**

*   **Programming Language:** Python 3.10+
*   **Web Framework:** FastAPI
*   **Server:** Uvicorn
*   **LLM API:** Anthropic Python SDK
*   **Tool Protocol:** MCP (`mcp` library)
*   **PDF Processing:** PyMuPDF (`fitz`)
*   **Core Logic:** Orchestrator (`app/orchestrator.py`), MCP Server (`mcp_server/`)
*   **Configuration:** Pydantic Settings, python-dotenv
*   **Package/Environment Management:** `uv`

**Chat Backend (`front-test/backend/`):**

*   **Programming Language:** Python (likely using Flask/similar based on OpenWebUI standard)
*   **Dependencies:** Defined in `requirements.txt`
*   **Environment Management:** Conda (recommended in original instructions)

**Chat Frontend (`front-test/`):**

*   **Framework:** SvelteKit
*   **Language:** TypeScript
*   **Styling:** Tailwind CSS
*   **Build Tool:** Vite
*   **Package Management:** npm

## Project Structure

```
root/
│
├── README.md                ← This file
│
├── front-test/              ← Chat Frontend & Backend
│   ├── src/                 ← Frontend source (SvelteKit)
│   ├── backend/             ← Chat Backend (Python/OpenWebUI standard)
│   │   ├── open_webui/
│   │   ├── requirements.txt
│   │   └── dev.sh           ← Script to run Chat Backend
│   ├── package.json         ← Frontend dependencies
│   ├── vite.config.ts
│   └── .env.local           ← Frontend configuration
│
├── backend/                 ← Custom API Backend (FastAPI)
│   ├── files/               ← Default storage for Custom API
│   ├── app/                 ← FastAPI application
│   │   ├── main.py
│   │   ├── orchestrator.py
│   │   └── ...
│   ├── mcp_server/          ← MCP Tool Server
│   │   ├── server.py
│   │   ├── pdf_search.py
│   │   └── ...
│   ├── pyproject.toml       ← Custom API Backend dependencies
│   └── uv.lock
│
├── .env                     ← Root environment configuration (for Custom API Backend)
├── .gitignore
├── LICENSE
└── ...
```

**Key Components:**

*   **`front-test/`:** Contains the **Chat Frontend** code (`src/`) and the **Chat Backend** code (`backend/`).
*   **`front-test/backend/`:** The standard OpenWebUI backend process. It serves the frontend and likely communicates with the Custom API Backend for specific tasks.
*   **`backend/`:** The **Custom API Backend** process. Handles all Claude interactions, MCP tool execution, and PDF processing logic.
*   **`backend/files/`:** Default storage for PDFs uploaded via the Custom API Backend.

## Setup and Running

This setup requires running **three separate processes**: the Custom API Backend, the Chat Backend, and the Chat Frontend.

**Prerequisites:**

*   Python 3.10+ (for both backends)
*   `uv` (for Custom API Backend): Install via `pip install uv`.
*   Conda (recommended for Chat Backend): Install Conda/Miniconda.
*   Node.js (v18.13+ recommended) and npm (for Chat Frontend).

**Steps:**

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd anthropic-2025-spongebob
    ```

2.  **Configure Custom API Backend:**
    *   Create `.env` in the **project root**:
        ```env
        # Required: Your Anthropic API Key
        ANTHROPIC_API_KEY=your_anthropic_api_key_here

        # Optional: Custom API Backend file storage
        # FILES_DIR="./backend/files/"

        # Optional: CORS origins allowed to access Custom API Backend
        # Ensure the Chat Backend's origin (e.g., http://localhost:8080) is allowed if it calls this API directly.
        # CORS_ORIGINS="http://localhost:8080,http://localhost:5173"
        ```

3.  **Set Up & Run Custom API Backend (`backend/`):**
    *   Navigate to the Custom API backend directory:
        ```bash
        cd backend
        ```
    *   Set up environment and install dependencies:
        ```bash
        uv venv
        source .venv/bin/activate # Linux/macOS
        # .\.venv\Scripts\activate # Windows
        uv pip install -r requirements.txt # Or uv pip install .
        ```
    *   Run the FastAPI server (typically on port 8000):
        ```bash
        uvicorn app.main:app --reload --port 8000
        ```
    *   Keep this terminal running.

4.  **Set Up & Run Chat Backend (`front-test/backend/`):**
    *   In a **new terminal**, navigate to the Chat Backend directory:
        ```bash
        cd ../front-test/backend # From project root
        ```
    *   Set up environment and install dependencies (using Conda as recommended):
        ```bash
        conda create --name open-webui python=3.11 # Or python=3.10
        conda activate open-webui
        pip install -r requirements.txt -U
        ```
    *   Run the Chat Backend server (likely defaults to port 8080):
        ```bash
        # Ensure conda env is active
        sh dev.sh # Or consult OpenWebUI docs/start scripts for the correct command
        ```
    *   Keep this terminal running. *(Note: This backend might need configuration to know the URL of the Custom API Backend if it calls it directly).* 

5.  **Set Up & Run Chat Frontend (`front-test/`):**
    *   In a **new terminal**, navigate to the frontend directory:
        ```bash
        cd .. # From front-test/backend
        # Or cd ../front-test # From project root
        ```
    *   Install Node.js dependencies:
        ```bash
        npm install
        ```
    *   **Configure Frontend API Endpoint:** Create `.env.local` inside `front-test/` pointing to the **Chat Backend**: 
        ```env
        # Point to the Chat Backend (running on port 8080 by default)
        NEXT_PUBLIC_API_BASE_URL=http://localhost:8080/v1
        NEXT_PUBLIC_API_KEY=dummy_key # May be required by frontend
        ```
    *   Run the frontend development server (typically on port 5173):
        ```bash
        npm run dev
        ```

6.  **Access the Application:**
    Open your web browser to the Chat Frontend URL (usually `http://localhost:5173`).

## Using PDF Search

1.  Click the "+" button in the chat input area.
2.  Select a PDF file to upload.
3.  Once uploaded, the PDF will be attached to your conversation.
4.  Ask questions about the content of the PDF in natural language.
5.  The system will interact with the backend to search the PDF and provide relevant answers with citations.

## How It Works (Architecture Flow)

1.  **User Interaction:** The user types a message or uploads a PDF in the OpenWebUI frontend (`front-test`).
2.  **Frontend Request:** The frontend sends requests to the FastAPI backend API endpoints (e.g., `POST /api/upload` for files, `POST /v1/chat/completions` for messages).
3.  **FastAPI Routing:** `backend/app/main.py` receives the request and routes it to the appropriate handler function, often in `backend/app/frontend_router.py`.
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

## Configuration Details

*   **`.env` (Project Root):**
    *   `ANTHROPIC_API_KEY`: **Required** for Claude API access.
    *   `CORS_ORIGINS`: Controls which frontend origins can access the backend API. Adjust if your frontend runs on a different port. Defaults are usually `http://localhost:5173`, `http://127.0.0.1:5173`.
    *   `FILES_DIR`: Specifies the directory to store uploaded PDFs. Defaults to `backend/files/`.
*   **`front-test/.env.local`:**
    *   `NEXT_PUBLIC_API_BASE_URL`: **Required**. Tells the frontend where the backend API (specifically the OpenAI-compatible `/v1` endpoints) is located (e.g., `http://localhost:8000/v1`).
    *   `NEXT_PUBLIC_API_KEY`: Required by OpenWebUI, but the value isn't used by our backend. Set to any non-empty string like `dummy_key`.

## Development Notes

See [our hackathon memo](0-our-hackathon-memo.md) for implementation details and troubleshooting information.

## Credits

This project builds upon the excellent work of [Open WebUI](https://github.com/open-webui/open-webui), created by [Timothy Jaeryang Baek](https://github.com/tjbck).

## Team Members

This project was developed by Harvard College CS students during the Anthropic x WiCS Hackathon 2025 (April):

*   Xingjian (Nicholas) Lyu
*   Bozhen Peng
*   Aghyad Deeb
*   Jay Choi
*   Aldo Stefanoni

## License

This project is licensed under the [BSD-3-Clause License](LICENSE). Our modifications are Copyright (c) 2025, Claude Trusted Team, while the original Open WebUI components remain Copyright (c) 2023, Timothy Jaeryang Baek.
