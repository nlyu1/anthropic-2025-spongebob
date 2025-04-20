import logging
import os
from datetime import datetime
from typing import Any, Dict
import base64, glob
from mcp.server.fastmcp import FastMCP

# Assuming pdf_search.py is in the same directory (mcp_server)
from pdf_search import search_pdf_content, DEFAULT_FILES_DIR

# --- Logging Setup ---
LOG_DIR = "./logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Create a timestamped log file name
LOG_FILENAME = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".log"
LOG_FILE_PATH = os.path.join(LOG_DIR, LOG_FILENAME)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[MCP Server] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE_PATH),
        logging.StreamHandler()  # Also log to console
    ]
)

logger = logging.getLogger(__name__)

logger.info(f"Server starting. Logging to {LOG_FILE_PATH}")
logger.info(f"Expecting PDF files in: {os.path.abspath(DEFAULT_FILES_DIR)}")

# --- MCP Server Setup ---
# Initialize FastMCP server - Changed name to reflect function
mcp = FastMCP("pdf_searcher")

@mcp.tool()
def search_pdf(pdf_name: str, query: str, pdf_dir: str = "./files", context_length: int = 2000, topk: int = 10) -> Dict[str, Any]:
    """Searches a PDF file for a query string.

    Looks for the PDF file in the '../files/' directory relative to the server script.
    Returns context around matches found within the PDF.

    Args:
        pdf_name: Name of the PDF file (without .pdf extension).
        pdf_dir: directory of the pdf_dir. Always specify ./files unless expicitly prompted by the user
        query: The text string to search for.
        context_length: The amount of context (characters) around each match.
        topk: Maximum number of matches to return.

    Returns:
        A dictionary with keys: file_exists (bool), query_exists (bool), matches (list[str]), and optionally error (str).
    """
    logger.info(f"Received request: search_pdf(pdf_name='{pdf_name}', query='{query}', context_length={context_length}, topk={topk})")

    try:
        # Note: search_pdf_content uses DEFAULT_FILES_DIR = "../files" internally,
        # which is the correct path relative to this server script's location (mcp_server/)
        # to reach the top-level 'files/' directory.
        result = search_pdf_content(
            pdf_name=pdf_name,
            query=query,
            context_length=context_length,
            topk=topk,
            pdf_dir=pdf_dir
        )
        logger.info(f"Search completed. File exists: {result.get('file_exists')}, Query exists: {result.get('query_exists')}, Matches found: {len(result.get('matches', []))}")
        if 'error' in result:
            logger.error(f"Error during search: {result['error']}")
        return result
    except Exception as e:
        logger.exception(f"Unhandled exception during search_pdf execution for '{pdf_name}'")
        # Return a generic error structure consistent with expected output
        return {
            "file_exists": False, # Cannot confirm if file exists if an unexpected error occured
            "query_exists": False,
            "matches": [],
            "error": f"An unexpected server error occurred: {e}"
        }

if __name__ == "__main__":
    logger.info("Starting MCP server...")
    try:
        mcp.run()
    except Exception as e:
        logger.exception("MCP Server failed to run.")
    finally:
        logger.info("MCP Server stopped.")