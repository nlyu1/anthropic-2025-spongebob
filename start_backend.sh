#!/bin/bash

echo "=============================================="
echo "Starting FastAPI backend with OpenAI compatibility"
echo "=============================================="

# Navigate to the backend directory
cd "$(dirname "$0")/backend" || { echo "Failed to navigate to backend directory"; exit 1; }

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
else
    echo "No virtual environment found. Make sure to run:"
    echo "cd backend && uv venv && uv pip install -e ."
    exit 1
fi

# Check for required dependencies
if ! python -c "import anthropic" &> /dev/null; then
    echo "Anthropic library not found. Installing required dependencies..."
    uv pip install anthropic
fi

if ! python -c "import pdfminer" &> /dev/null; then
    echo "PDFMiner not found. Installing required dependencies..."
    uv pip install pdfminer.six
fi

# Check for Anthropic API key
if [ -z "$ANTHROPIC_API_KEY" ] && [ ! -f ".env" ] && [ ! -f "../.env" ]; then
    echo "ANTHROPIC_API_KEY not found in environment or .env file"
    echo "Please create a .env file with your Anthropic API key:"
    echo "ANTHROPIC_API_KEY=your_key_here"
    exit 1
fi

# Create files directory if it doesn't exist
mkdir -p ../files

# Make sure MCP server is available
if [ ! -d "./mcp_server" ]; then
    echo "MCP server directory not found. Make sure backend/mcp_server exists."
    exit 1
fi

echo "Starting backend server with PDF search functionality..."
echo "PDF files should be placed in the 'files/' directory"
echo "Use Ctrl+C to stop the server"

# Start the server
uvicorn app.main:app --reload --port 8000

echo ""
echo "Server has been stopped."
echo ""
echo "To configure Open WebUI to use this backend:"
echo "1. Set API Base URL: http://127.0.0.1:8000/v1"
echo "2. Any value can be used for the API key" 