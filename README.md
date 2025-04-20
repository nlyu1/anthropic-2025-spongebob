# anthropic-2025-spongebob

This project integrates a backend service with a chat interface (like LobeChat) to enable conversations augmented by PDF document search using Anthropic's Claude model and the MCP protocol for tool use.

## Quick Start

Follow these steps to set up and run the backend server.

**Prerequisites:**

*   Python 3.10+
*   `uv`: We recommend using `uv` for environment and package management. Install it if you haven't already (e.g., `pip install uv` or follow official instructions).

**Setup:**

1.  **Clone the repository** (if you haven't already):
    ```bash
    git clone <repository_url>
    cd anthropic-2025-spongebob
    ```

2.  **Navigate to the backend directory:**
    ```bash
    cd backend
    ```

3.  **Create and activate a virtual environment:**
    ```bash
    uv venv
    uv sync 
    source .venv/bin/activate  # On Linux/macOS
    # .\.venv\Scripts\activate  # On Windows PowerShell
    ```

4.  **Install dependencies:**
    This command installs the main application dependencies and development dependencies (like `requests` needed for tests/benchmarking).
    ```bash
    uv pip install .
    ```

5.  **Configure Environment Variables:**
    Create a file named `.env` in the **project root** directory (the one containing the `backend/` and `frontend/` folders). Add your Anthropic API key:
    ```env
    ANTHROPIC_KEY=your_anthropic_api_key_here

    # Optional: Specify allowed origins for CORS (comma-separated)
    # Default allows http://localhost:3210 if not set
    # CORS_ORIGINS="http://localhost:3210,http://127.0.0.1:3210"

    # Optional: Specify a different directory for uploaded files
    # Defaults to 'files/' in the backend directory if not set
    # FILES_DIR="/path/to/your/pdf/storage"
    ```
    *Note: Ensure the `.env` file is added to your `.gitignore` to avoid committing secrets.*

6.  **Run the backend server:**
    Make sure you are in the `backend/` directory with the virtual environment activated.
    ```bash
    uvicorn app.main:app --reload --port 8000
    ```
    The server should now be running at `http://localhost:8000`. You can check its status by visiting `http://localhost:8000/check` in your browser or using `curl`.

7.  **Run the Benchmark Script (Optional):**
    To run the benchmark test:
    ```bash
    # Navigate to the benchmarking directory from the project root
    cd benchmarking # Or cd ../benchmarking if you are in backend/
    python benchmark_wrapper.py
    ```
    *(This requires the backend server to be running and uses dependencies installed via `uv pip install .`)*

## Project Structure

The project is organized into several key directories:

*   `README.md`: (This file) Top-level project overview.
*   `breakdown.md`: Document outlining a target architecture (Note: The current implementation may differ).
*   `files/`: Default storage location for uploaded PDF files used by the backend. (Note: The actual location is determined by `backend/app/settings.py`, which defaults to `backend/files/` unless `FILES_DIR` is set in `.env`).
*   `frontend/`: Intended location for the chat frontend (e.g., a clone of LobeChat). See `breakdown.md` for setup details regarding `.env.local` for frontend configuration.
*   `backend/`: Contains the FastAPI backend application.
    *   `app/`: The core FastAPI application package.
        *   `main.py`: Defines API endpoints (`/check`, `/api/upload`, `/api/chat`, `/benchmark`), configures CORS, and handles incoming requests. It uses `orchestrator.py` for the main chat logic.
        *   `orchestrator.py`: Manages the interaction flow with Anthropic's Claude model. It initializes an `MCPClient`, connects to the separate MCP server process (`./mcp_server/server.py`), prepares messages (including loading PDF content via `pdf_loading_utils.py`), handles the tool execution loop with Claude, and returns the final response.
        *   `pdf_loading_utils.py`: Contains helper functions for loading and processing PDF content to be included in the Claude prompt.
        *   `settings.py`: Defines Pydantic models for loading configuration settings (like `ANTHROPIC_KEY`, `CORS_ORIGINS`, `FILES_DIR`) from the root `.env` file.
    *   `mcp_server/`: **(Current Implementation Detail)** Contains the separate MCP server process that exposes the `search_pdf` tool.
        *   `server.py`: The script that runs the MCP server using the `mcp` library. This is the process `orchestrator.py` connects to.
        *   `pdf_search.py`: Implements the actual PDF search logic using libraries like `pdfminer.six`, `sentence-transformers`, and `numpy`. It defines the `search_pdf` tool exposed by the MCP server.
        *   `pyproject.toml`: Defines *some* dependencies specific to the MCP server (uses Poetry). **Note:** This structure and the separate dependency file deviate from the unified approach suggested in `breakdown.md`. Ideally, dependencies should be consolidated in `backend/pyproject.toml` and the tool logic potentially integrated directly into the `backend/app/` structure.
    *   `tests/`: Contains scripts for testing backend functionality (e.g., `test_upload.py`).
    *   `files/`: Default directory within the backend where uploaded PDFs are stored (can be configured via `.env`).
    *   `pyproject.toml`: The main dependency definition file for the backend application (using `hatchling`). Use `uv pip install .[dev]` to install all necessary packages.
    *   `uv.lock`: Lock file generated by `uv`.
    *   `README.md`: Placeholder for backend-specific documentation.
*   `benchmarking/`: Contains scripts and resources for benchmarking the backend's performance.
    *   `benchmark_wrapper.py`: Script to send requests to the `/benchmark` endpoint and measure performance.
    *   `files/`: Sample PDF files potentially used by the benchmark script.
    *   `sample_result.md`: An example of benchmark output.

## Backend API Specification

The backend provides the following REST API endpoints:

### `GET /check`

*   **Purpose:** A simple health check endpoint.
*   **Method:** `GET`
*   **Response:**
    *   `200 OK`: Returns JSON `{"message": "hello world"}`.

### `POST /api/upload`

*   **Purpose:** Uploads a PDF file to the server's configured `files/` directory.
*   **Method:** `POST`
*   **Request:**
    *   `Content-Type`: `multipart/form-data`
    *   `file`: The PDF file (`.pdf` extension required).
*   **Response:**
    *   `200 OK`: JSON `{"pdf_name": "your_file_name_without_extension"}`.
    *   `400 Bad Request`: If the file is not a PDF or issue with the request.
    *   `500 Internal Server Error`: If the server fails to save the file.

### `POST /api/chat`

*   **Purpose:** Processes a chat conversation history, interacts with Claude (potentially using the `search_pdf` tool via the MCP server), and returns the final aggregated text response.
*   **Method:** `POST`
*   **Request:**
    *   `Content-Type`: `application/json`
    *   **Body:** JSON object with a `messages` key (list of Anthropic message objects, e.g., `[{"role": "user", "content": "Query"}]`).
*   **Response:**
    *   `200 OK`: Plain text string containing the final response from the orchestrator. This may include text generated by Claude and potentially text indicating tool calls/results.
    *   `400 Bad Request`: Invalid JSON or missing/invalid `messages`.
    *   `500 Internal Server Error`: Error during MCP connection, Claude interaction, or other processing.

### `POST /benchmark`

*   **Purpose:** Similar to `/api/chat`, but allows overriding default parameters for benchmarking purposes.
*   **Method:** `POST`
*   **Request:**
    *   `Content-Type`: `application/json`
    *   **Body:** JSON object containing:
        *   `messages` (List[Dict]): Required conversation history.
        *   `claude_args` (Optional[Dict]): Overrides for Claude API call (e.g., `model`, `max_tokens`).
        *   `pdf_root` (Optional[str]): Override PDF search directory.
        *   `pdf_files` (Optional[List[str]]): Specific PDF filenames (no extension) to load.
        *   `max_rounds` (Optional[int]): Max internal tool-use rounds.
*   **Response:**
    *   `200 OK`: Plain text string containing the final response.
    *   `400/500`: Similar errors as `/api/chat`.

## Running Tests & Benchmarks

**Prerequisites:**

*   Backend server must be running (`uvicorn app.main:app --reload --port 8000` in `backend/`).
*   Dependencies must be installed (`uv pip install .[dev]` in `backend/`).

**Running Basic Tests:**

1.  Navigate to the `backend/` directory.
2.  Run the test script(s):
    ```bash
    # Example using the provided upload test
    python tests/test_upload.py
    ```
    *(You might need to adapt or add more tests)*

**Running Benchmarks:**

1.  Navigate to the `benchmarking/` directory.
2.  Execute the benchmark wrapper:
    ```bash
    python benchmark_wrapper.py
    ```
    *(Review `benchmark_wrapper.py` for any specific arguments or configuration it might accept)*