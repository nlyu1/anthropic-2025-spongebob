# anthropic-2025-spongebob

## Setting up the mcp-server

## Setting up the Backend

1.  **Navigate to the backend directory:**
    ```bash
    cd backend
    ```
2.  **Create a virtual environment and install dependencies:**
    We recommend using `uv`:
    ```bash
    # Ensure uv is installed (e.g., pip install uv)
    uv venv
    uv pip install . # Install project and dependencies
    source .venv/bin/activate 
    ```
    *(Alternatively, use `python -m venv .venv` and `pip install ...`)*

3.  **Configure Environment Variables:**
    Create a `.env` file in the **project root** (the directory containing `backend/` and `frontend/`) and add your Anthropic API key:
    ```env
    ANTHROPIC_KEY=your_api_key_here
    # Optional: Specify allowed origins for CORS
    # CORS_ORIGINS="http://localhost:3210,http://127.0.0.1:3210"
    ```

4.  **Run the backend server:**
    ```bash
    uvicorn app.main:app --reload --port 8000
    ```
    The server should now be running at `http://localhost:8000`.

## Backend API Specification

The backend provides the following REST API endpoints:

### `GET /check`

*   **Purpose:** A simple health check endpoint.
*   **Method:** `GET`
*   **Request:** None
*   **Response:**
    *   `200 OK`: Returns a JSON object `{"message": "hello world"}`.

### `POST /api/upload`

*   **Purpose:** Uploads a PDF file to the server's `files/` directory.
*   **Method:** `POST`
*   **Request:**
    *   `Content-Type`: `multipart/form-data`
    *   `file`: The PDF file to upload. The server currently only accepts files with a `.pdf` extension.
*   **Response:**
    *   `200 OK`: Returns a JSON object `{"pdf_name": "your_file_name_without_extension"}` upon successful upload.
    *   `400 Bad Request`: If the uploaded file is not a PDF or if there's an issue with the request format.
    *   `500 Internal Server Error`: If the server fails to save the file.
*   **Example Usage:** See `backend/tests/test_upload.py`.

### `POST /api/chat`

*   **Purpose:** Sends a chat message history to the Claude model via an MCP client, potentially using tools defined on an MCP server (`./mcp_server/server.py`), and returns the model's final response.
*   **Method:** `POST`
*   **Request:**
    *   `Content-Type`: `application/json`
    *   **Body:** A JSON object containing a `messages` key. The value should be a list of message objects, following the Anthropic Messages API format (e.g., `[{"role": "user", "content": "Your query here"}]`).
*   **Response:**
    *   `200 OK`: Returns the final text response from the Claude model as a plain text string. This might include text generated directly by the model and placeholders indicating tool calls were made (e.g., `[Calling tool search_pdf with args {'pdf_name': 'WGAN', 'query': 'probability density'}]`). **Note:** The current implementation in `orchestrator.py` handles tool calls sequentially and may not fully support complex multi-tool interactions in a single turn.
    *   `400 Bad Request`: If the request body is missing, malformed, or the `messages` list is invalid.
    *   `500 Internal Server Error`: If an error occurs during MCP client setup, connection to the server, or processing the query with Claude.

## Running Tests

A simple test script is provided to check basic functionality.

1.  **Ensure the backend server is running** (see steps above).

2.  **Install development dependencies (if not already done):**
    The test script requires the `requests` library. Install it and other dev dependencies:
    ```bash
    # Navigate to the backend directory first if you aren't there
    cd backend 
    # Activate your virtual environment (e.g., source .venv/bin/activate)
    uv pip install --extra dev 
    # Or if you installed the project with 'uv pip install .':
    # uv pip install requests
    ```

3.  **Run the test script:**
    From the **backend** directory:
    ```bash
    python tests/test_upload.py
    ```
    Or, using `uv` from the **backend** directory:
    ```bash
    uv run python tests/test_upload.py
    ```
    The script will print `Test PASSED` or `Test FAILED`.