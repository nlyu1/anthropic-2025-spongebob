import asyncio
import os
import logging # Import logging
from typing import Optional
from contextlib import AsyncExitStack
import base64, glob

FILES_DIR = './files'

MAX_INLINE_MB = 10     # keep token usage reasonable

def load_pdf_as_block() -> list[dict]:
    """Return a list of {'type':'document', ...} blocks for each PDF in ./files.
    
    PROBLEMATIC: only parses one pdf. """
    blocks: list[dict] = []

    logger.info(f'[INFO / Orchestrator / load_pdf_as_block] Loading PDF files from {os.path.abspath(FILES_DIR)}, available files: {glob.glob(f"{FILES_DIR}/*.pdf")}')
    for path in glob.glob(f"{FILES_DIR}/*.pdf"):
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


debug = True

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()  # load environment variables from .env

key = os.getenv("ANTHROPIC_API_KEY")
if not key:
    raise RuntimeError("ANTHROPIC_API_KEY not set in .env file or environment.")

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic(api_key=key)

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server
        
        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")
            
        command = "python" if is_python else "node"
        print(f'Connecting to server with command: {command} {server_script_path}')
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        logger.info('Creating session')
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        print('[Orchestrator / INFO] Initializing session', self.session)
        await self.session.initialize()
        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\n[Orchestrator / INFO]: Connected to server with tools:", [tool.name for tool in tools])

    async def process_query(self, messages: list) -> str:
        """Process a query using Claude and available tools"""
        response = await self.session.list_tools()
        doc_block = load_pdf_as_block()
        messages = messages + [{"role": "user", "content": [doc_block]}]

        available_tools = [{ 
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in response.tools]
        # print('[INFO] Available tools:', available_tools)
        # logger.info(f'[INFO / Orchestrator / process_query] processing query')
        # Initial Claude API call
        response = self.anthropic.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=5000,
            messages=messages,
            tools=available_tools
        )
        
        # Process response and handle tool calls
        tool_results, final_text = [], []
        running_messages = [m for m in messages]
        compute_types = lambda response: [content.type for content in response.content]
        for i in range(20):
            has_tool_calls = False 
            append_messages = []
            logger.info(f'[INFO / Orchestrator / process_query]\n    Processing response #{i} of type: {compute_types(response)}')
            for content in response.content:
                if content.type == 'text':
                    logger.info(f'    APPENDING TEXT FROM OUTPUT: \n\n\n{content.text}\n\n\n')
                    final_text.append(content.text)
                    append_messages.append({
                        "role": "assistant",
                        "content": content.text
                    })
                elif content.type == 'tool_use':
                    has_tool_calls = True 
                    tool_name = content.name
                    tool_args = content.input

                    # Execute tool call 
                    result = await self.session.call_tool(tool_name, tool_args)
                    # print('TOOL RESULT:', result)
                    tool_results.append({"call": tool_name, "result": result}) 
                    final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")
                    # Add tool-call response to a running queue of messages 
                    if hasattr(content, 'text') and content.text:
                        append_messages.append({
                        "role": "assistant",
                        "content": content.text
                        })
                    append_messages.append({
                        "role": "user", 
                        "content": result.content
                    })
            if not has_tool_calls:
                break 
            # After all tool calls have been made, make another API call to claude 
            running_messages = running_messages + append_messages
            response = self.anthropic.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=5000,
                messages=running_messages,
                tools=available_tools
            )
        print(messages)
        final_text = "\n".join(final_text)
        logger.info(f'[INFO] FINAL_TEXT: \n\n\n{final_text}\n\n\n')
        return final_text

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
                
                if query.lower() == 'quit':
                    break
                
                # Format the raw query string into the expected message list structure
                user_message = [{"role": "user", "content": query}]
                response = await self.process_query(user_message)
                print("\n" + response)
                    
            except Exception as e:
                print(f"\nError: {str(e)}")
    
    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

# async def main():
#     if len(sys.argv) < 2:
#         print("Usage: python client.py <path_to_server_script>")
#         sys.exit(1)
        
#     client = MCPClient()
#     try:
#         print('Trying to connect to server')
#         await client.connect_to_server(sys.argv[1])
#         print('Connected to server')
#         await client.chat_loop()
#     finally:
#         await client.cleanup()

# if __name__ == "__main__":
#     import sys
#     asyncio.run(main())