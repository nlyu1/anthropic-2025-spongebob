import asyncio, os, sys, base64, glob
from typing import Optional, List, Dict
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from anthropic import Anthropic
from dotenv import load_dotenv

MODEL="claude-3-7-sonnet-20250219"

SYSTEM_PROMT="""You are Claude 3 with access to the MCP tool **search_pdf(file, query)**.

GOAL  
• Read the attached PDF.  
• Produce a concise, integrated summary of its key ideas.  
• Support every claim with accurately transcribed quotations from the PDF.

MANDATORY WORKFLOW  
1. **Plan step‑by‑step.** Before you write any summary sentence, explicitly reason through what information you need and where it appears in the document.  
2. For each quotation you intend to use:  
   a. Call **search_pdf** with the *exact* text you plan to quote.  
   b. Capture the page number(s) returned.  
   c. If search_pdf returns zero hits, revise the quote and repeat the call until you obtain at least one hit.  
3. **Triple‑check rule**: After drafting the full summary, re‑issue search_pdf on **every quotation** two additional times (total of three independent calls per quote) to confirm both text and page reference.  
4. If any re‑check fails, immediately correct or remove the quotation and restart the triple‑check for that quote.  
5. **Output format**:  
   • Present the summary in coherent paragraphs.  
   • After each quoted segment, append the citation in this form: `(page X)`.  
   • After the summary, include an **Audit Trail** table listing *all* search_pdf calls in order, showing the query string, number of matches, and pages returned.

CONSTRAINTS  
• Do not fabricate or alter quotations.  
• Do not skip the triple‑check rule, even under token pressure.  
• Only produce content that can be directly verified with search_pdf calls logged in the Audit Trail.  
• Stay within 400 words for the main summary (citations excluded).

Begin."""

load_dotenv()
key = os.getenv("ANTHROPIC_API_KEY")
if not key:
    raise RuntimeError("ANTHROPIC_API_KEY not set")

MAX_INLINE_MB = 5     # keep token usage reasonable

def load_pdf_as_block() -> list[dict]:
    """Return a list of {'type':'document', ...} blocks for each PDF in ./files."""
    blocks: list[dict] = []
    for path in glob.glob("./files/*.pdf"):
        size_mb = os.path.getsize(path) / 1_048_576
        if size_mb > MAX_INLINE_MB:
            print(f"⚠️  Skipping {os.path.basename(path)} – {size_mb:.1f} MB > {MAX_INLINE_MB} MB inline limit")
            continue

        with open(path, "rb") as f:
            b64_pdf = base64.b64encode(f.read()).decode()

        pdf_b64_block = {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": b64_pdf
            }
        }

    return pdf_b64_block


class MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic(api_key=key)

        self.messages: list[dict] = []        # user / assistant only

    # ────────────────────────────────────────────────────────────
    # connection setup (unchanged)
    # ────────────────────────────────────────────────────────────
    async def connect_to_server(self, server_script_path: str):
        cmd = "python" if server_script_path.endswith(".py") else "node"
        params = StdioServerParameters(command=cmd, args=[server_script_path])
        self.stdio, self.write = await self.exit_stack.enter_async_context(
            stdio_client(params)
        )
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )
        await self.session.initialize()
        # cache tools once
        tool_list = await self.session.list_tools()
        self.available_tools = [{
            "name": t.name,
            "description": t.description,
            "input_schema": t.inputSchema
        } for t in tool_list.tools]
        print("Connected to server with tools:", [t["name"] for t in self.available_tools])

    # ────────────────────────────────────────────────────────────
    # ONE turn of conversation (adds to self.messages)
    # ────────────────────────────────────────────────────────────
    async def process_turn(self, user_query: str) -> str:
        # ① build content blocks: PDFs + user's question
        doc_block = load_pdf_as_block()

        # ② add this turn to the running history
        self.messages.append({"role": "user", "content": [
                doc_block,
                {
                    "type": "text",
                    "text": user_query
                }
            ]})

        # ③ synchronous Claude call wrapped in a thread
        response = await asyncio.to_thread(
            self.anthropic.messages.create,              # ⬅️ sync client
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMT,
            messages=self.messages,
            tools=self.available_tools                    # optional
        )

        # ④ parse Claude’s reply (may include tool calls)
        final_chunks = []
        for part in response.content:
            if part.type == "text":
                self.messages.append({"role": "assistant", "content": part.text})
                final_chunks.append(part.text)

            elif part.type == "tool_use":
                # execute the tool …
                call_result = await self.session.call_tool(part.name, part.input)
                self.messages += [
                    {"role": "assistant", "content": f"[Calling tool {part.name} with args {part.input}]"},
                    {"role": "user", "content": call_result.content}
                ]

                # … and get Claude’s follow‑up (again via to_thread)
                follow = await asyncio.to_thread(
                    self.anthropic.messages.create,
                    model=MODEL,
                    max_tokens=1024,
                    messages=self.messages,
                )
                txt = follow.content[0].text
                self.messages.append({"role": "assistant", "content": txt})
                final_chunks.append(txt)

        return "\n".join(final_chunks)


    async def process_turn_old(self, user_query: str) -> str:
        self.messages.append({"role": "user", "content": user_query})

        # first response (may include tool calls)
        response = self.anthropic.messages.create(
            model=MODEL,
            max_tokens=1000,
            messages=self.messages,
            tools=self.available_tools,
        )

        final_chunks = []
        for part in response.content:
            if part.type == "text":
                self.messages.append({"role": "assistant", "content": part.text})
                final_chunks.append(part.text)

            elif part.type == "tool_use":
                tool_name, tool_args = part.name, part.input
                call_result = await self.session.call_tool(tool_name, tool_args)

                # annotate transcript so Claude sees the result
                self.messages.append({
                    "role": "assistant",
                    "content": f"[Calling tool {tool_name} with args {tool_args}]"
                })
                self.messages.append({
                    "role": "user",
                    "content": call_result.content
                })

                follow_up = self.anthropic.messages.create(
                    model=MODEL,
                    max_tokens=1000,
                    messages=self.messages,
                )
                follow_text = follow_up.content[0].text
                self.messages.append({"role": "assistant", "content": follow_text})
                final_chunks.append(follow_text)

        return "\n".join(final_chunks)

    # ────────────────────────────────────────────────────────────
    async def chat_loop(self):
        print("\nContinuous MCP chat.  Type '/reset' to start over, 'quit' to exit.")
        while True:
            user_msg = input("\nYou: ").strip()
            if user_msg.lower() == "quit":
                break
            if user_msg.lower() == "/reset":
                self.messages = self.messages[:1]  # keep system prompt
                print("✦ conversation reset ✦")
                continue
            try:
                reply = await self.process_turn(user_msg)
                print("\nClaude:", reply)
            except Exception as e:
                print("Error:", e)

    async def cleanup(self):
        await self.exit_stack.aclose()

# ────────────────────────────────────────────────────────────
async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)

    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
