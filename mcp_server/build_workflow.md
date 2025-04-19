# Create a new directory for our project
uv init mcp_server
cd mcp_server

# Create virtual environment and activate it
uv venv
source .venv/bin/activate

# Install dependencies
uv add "mcp[cli]" pdfminer.six mcp anthropic python-dotenv

# Run `pdf_search` to debug behavior

uv run pdf_search.py