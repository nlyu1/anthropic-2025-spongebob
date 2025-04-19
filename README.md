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