0. Activate: `source .venv/bin/activate`. 
1. Running tests: `uv run python tests/test_upload.py` in `./backend`. 
2. Running server: `uv run python client.py` in `./backend`. 
3. Running archive example: `uv run python client.py ../mcp_server/server.py` in `./archives/mcp_client`.

You are Claude 3 with access to the MCP tool **search_pdf(file, query)**.

<!-- 
uv run python tests/debug_chat.py "GOAL  
• Read the attached PDF of name gettysburg_address.
• Produce a concise, integrated summary of its key ideas.  
• Support every claim with accurately transcribed quotations from the PDF by using the MCP tool **search_pdf(file, query)**.
• Do not call the tool search_pdf just to verify that the file exists. You can assume that it exists. 

MANDATORY WORKFLOW  
1. **Plan step‑by‑step.** Before you write any summary sentence, explicitly reason through what information you need and where it appears in the attached document.  
2. For each quotation you intend to use:  
   a. Call **search_pdf** with the *exact* text you plan to quote to see if the quote exists.  
   b. search_pdf returns that the quote does not exist, revise the quote and repeat the call until you obtain at least one hit.  
3. If any re‑check fails, immediately correct or remove the quotation.  
4. **Output format**:  
   • Present the summary in coherent paragraphs.  
   • Quotes begin with <quote> and end with <\quote>.  
   • After the summary, you must include an **Audit Trail** table listing *all* search_pdf calls in order, showing the query string, number of matches, and pages returned.

CONSTRAINTS  
• Do not fabricate or alter quotations.  
• Only produce content that can be directly verified with search_pdf calls logged in the Audit Trail.  
• Stay within 400 words for the main summary (citations excluded).

Summarize the file gettysburg_address"

uv run python tests/debug_chat.py "search for 'gettysburg' in the pdf file gettysburg_address"

uv run python tests/debug_chat.py "use tool to search for 'gettysburg' in the gettysburg address file, and 'white boys' in the MLK speech file"

uv run python tests/debug_chat.py "use tool to search for 'pdf_1' in the file pdf_1"
-->

