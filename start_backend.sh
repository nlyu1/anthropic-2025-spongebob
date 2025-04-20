#!/bin/bash

echo "=============================================="
echo "Starting FastAPI backend with OpenAI compatibility"
echo "=============================================="

# Change to backend directory
cd backend || { 
    echo "Error: Could not find backend directory!"
    exit 1
}

# Activate virtual environment
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate || {
        echo "Error: Failed to activate virtual environment!"
        exit 1
    }
else
    echo "Warning: No .venv directory found. Make sure you've set up the backend first."
    echo "See the README.md for setup instructions."
    exit 1
fi

# Kill any existing uvicorn processes
pkill -f "uvicorn app.main:app" 2>/dev/null || true
echo "Starting server on http://127.0.0.1:8000..."

# Start the server
python -m uvicorn app.main:app --port 8000 --reload

echo ""
echo "Server has been stopped."
echo ""
echo "To configure Open WebUI to use this backend:"
echo "1. Set API Base URL: http://127.0.0.1:8000/v1"
echo "2. Any value can be used for the API key" 