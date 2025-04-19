# MCP Server Specifications: PDF Search Tool

This document outlines the specifications for an MCP (Model Context Protocol) tool designed to search within PDF documents.

## Tool: `search_pdf`

### Description

This tool searches for a given text query within a specified PDF file located in a predefined directory (`./files/`) relative to the **project root** (the directory containing `mcp_server/`). It returns information about the file's existence, whether the query was found, and context surrounding the matches.

### Interface

`search_pdf(pdf_name: str, query: str, context_length: int = 2000, topk: int = 10) -> dict`

### Arguments

-   `pdf_name` (String): The name of the PDF file (without the `.pdf` extension) to search within. The server will look for this file at `./files/{pdf_name}.pdf` relative to the project root.
-   `query` (String): The text string to search for within the PDF document. The search should be case-insensitive.
-   `context_length` (Integer, Optional, Default: 2000): The approximate number of characters to include as context *around* each match (half before, half after, if possible).
-   `topk` (Integer, Optional, Default: 10): The maximum number of matches (with context) to return.

### Return Value

A JSON dictionary with the following keys:

-   `file_exists` (Boolean): `true` if the file `./files/{pdf_name}.pdf` was found and accessible by the server, `false` otherwise.
-   `query_exists` (Boolean): `true` if the `query` string was found at least once within the PDF content (only evaluated if `file_exists` is `true`), `false` otherwise.
-   `matches` (List[String]): A list containing strings of context surrounding each found occurrence of the `query`.
    -   Each string in the list represents one match and its surrounding context, up to `context_length` characters.
    -   The list will contain at most `topk` elements.
    -   If `file_exists` is `false` or `query_exists` is `false`, this list will be empty (`[]`).

### Behavior

1.  **File Location:** The server constructs the full file path relative to the *project root*. For a server running from `./mcp_server/`, the path will be `../files/{pdf_name}.pdf`.
2.  **File Check:** It first checks if this file exists and is readable. If not, it returns `{"file_exists": false, "query_exists": false, "matches": []}`.
3.  **PDF Parsing:** If the file exists, the server parses the text content of the PDF. If parsing fails, it should ideally return an error state or indicate failure appropriately (e.g., `{"file_exists": true, "query_exists": false, "matches": [], "error": "Failed to parse PDF"}` - *Note: Error handling details can be refined during implementation*).
4.  **Query Search:** It performs a case-insensitive search for the `query` string within the extracted text.
5.  **Context Extraction:** For each match found (up to `topk`), it extracts the surrounding text context. The goal is to get roughly `context_length / 2` characters before the match and `context_length / 2` characters after the match. Boundary conditions (start/end of the document) should be handled gracefully.
6.  **Response Formatting:** It constructs and returns the JSON response dictionary as specified above. If the query is not found, it returns `{"file_exists": true, "query_exists": false, "matches": []}`.

### Example Interaction (Conceptual)

**Request:**
```json
{
  "tool": "search_pdf",
  "args": {
    "pdf_name": "research_paper_on_llms",
    "query": "transformer architecture",
    "topk": 3
  }
}
```

**Possible Response (Success):**
```json
{
  "file_exists": true,
  "query_exists": true,
  "matches": [
    "...context before match 1... **transformer architecture** ...context after match 1...",
    "...context before match 2... **Transformer Architecture** ...context after match 2...",
    "...context before match 3... **transformer architecture** ...context after match 3..."
  ]
}
```

**Possible Response (File Not Found):**
```json
{
  "file_exists": false,
  "query_exists": false,
  "matches": []
}
```

**Possible Response (Query Not Found):**
```json
{
  "file_exists": true,
  "query_exists": false,
  "matches": []
}
```

### Dependencies

-   Requires a library capable of parsing text content from PDF files (e.g., `PyPDF2`, `pdfminer.six`, etc.).
-   Assumes a directory named `files` exists in the project root directory (parallel to `mcp_server/`), containing the PDF files.

### Logging

-   The server logs requests and responses to a timestamped file within the `./mcp_server/logs/` directory for each session.
-   Log files are named using the format `YYYY-MM-DD_HH-MM-SS.log`.
-   Logs include information about received requests (tool name, arguments) and the results returned (or errors encountered).
