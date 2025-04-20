import asyncio
import os
import logging # Import logging
from typing import Optional, List, Dict, Any, AsyncGenerator
from contextlib import AsyncExitStack
import base64, glob

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from anthropic import Anthropic
from dotenv import load_dotenv

# Import the function from the new module
from .pdf_loading_utils import load_pdf_as_blocks

load_dotenv()  # load environment variables from .env
key = os.getenv("ANTHROPIC_API_KEY")
if not key:
    raise RuntimeError("ANTHROPIC_API_KEY not set in .env file or environment.")

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class MCPClient:
    def __init__(self, claude_args={'model': 'claude-3-7-sonnet-latest', 'max_tokens': 5000}):    
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic(api_key=key)
        self.claude_args = claude_args

    # ------------------------------------------------------------------
    # Helper utilities
    # ------------------------------------------------------------------
    def _prepare_messages(self,
                          messages: list,
                          pdf_root: str = "./files",
                          pdf_files=None) -> list:
        """Return a *new* messages list where the last user message has
        its original content (string or blocks) **plus** any PDF blocks
        loaded via ``load_pdf_as_blocks``.

        The logic is identical to what ``process_query`` previously
        implemented inline. Extracting it here lets both ``process_query``
        and the new ``stream_query`` share exactly the same behaviour
        without duplicating code.
        """
        if not messages:
            raise ValueError("messages list cannot be empty")

        last = messages[-1]
        if last.get("role") != "user":
            raise ValueError("Last message must be from the user")

        # ---- merge original text blocks with PDF blocks --------------
        # Original user content might be a plain string or already a list
        original_content = last["content"]
        if not isinstance(original_content, list):
            original_blocks = [{"type": "text", "text": original_content}]
        else:
            # Make a shallow copy so we don't mutate the caller's data
            original_blocks = original_content.copy()

        pdf_blocks = load_pdf_as_blocks(pdf_root, pdf_files)

        new_last = {
            "role": "user",
            "content": [*original_blocks, *pdf_blocks],
        }

        return [*messages[:-1], new_last]

    async def process_query(self, messages: list, pdf_root="./files", pdf_files=None, max_rounds=10) -> str:
        """
        pdf_root: where to look for pdf's
        pdf_files: which pdf files to parse & add to conversation. By default, everything in the folder is added 
        max_rounds: maximum rounds of internal conversation iteration Claude can call (i.e. number of round trips between Anthropic and local MCP server)
        """
        # Build conversation identical to original logic
        messages = self._prepare_messages(messages, pdf_root, pdf_files)
        response = await self.session.list_tools()
        available_tools = [{ 
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in response.tools]
        # print('[INFO] Available tools:', available_tools)
        # logger.info(f'[INFO / Orchestrator / process_query] processing query')
        # Initial Claude API call
        response = self.anthropic.messages.create(
            messages=messages,
            tools=available_tools,
            **self.claude_args 
        )
        # """Sample response:
        # Message(
        #     id='msg_01HBuyfpmGb9sRJZe99xkAWK',
        #     content=[
        #         TextBlock(citations=None, text="I'll search for 'pdf_1' in the short_pdf1.pdf file for you.", type='text'),
        #         ToolUseBlock(id='toolu_01RmogbLEpWcWesmo2jXUFmH', input={'pdf_name': 'short_pdf1', 'query': 'pdf_1'}, name='search_pdf', type='tool_use')
        #     ],
        #     model='claude-3-7-sonnet-20250219',
        #     role='assistant',
        #     stop_reason='tool_use',
        #     stop_sequence=None,
        #     type='message',
        #     usage=Usage(cache_creation_input_tokens=0, cache_read_input_tokens=0, input_tokens=3806, output_tokens=100)
        # )
        # """
        # Process response and handle tool calls
        final_text = []
        running_messages = [m for m in messages]
        compute_types = lambda response: [content.type for content in response.content]
        # print('DEBUG: Claude response: \n\n\n', response, '\n\n\n')
        for i in range(max_rounds):
            # Append the model's response to the conversation
            running_messages.append({
                "role": "assistant",
                "content": [blk.model_dump(exclude_none=True)
                            for blk in response.content]  # or blk.__dict__ if older SDK
                            })
            has_tool_calls = False 
            content_list = [] # Responding content list 
            # logger.info(f'[Info/Orchestrator]\n    Processing round #{i} of block types: [{compute_types(response)}]')
            for content in response.content:
                if content.type == 'text':
                    logger.info(f"[Info/Orchestrator]\n    Model output: {str(content.text)[:50]}...")
                    final_text.append(content.text)
                elif content.type == 'tool_use':
                    has_tool_calls = True 
                    tool_name, tool_args = content.name, content.input
                    tool_use_id = content.id
                    logger.info(f"[Info/Orchestrator]\n    Using tool [{content.name}] with inputs [{content.input}]")
                    # Execute tool call 
                    try:
                        result = await self.session.call_tool(tool_name, tool_args)
                        # print('TOOL RESULT: \n\n\n', result, '\n\n\n')
                        # """Standard result:
                        #     meta=None content=[
                        #     TextContent(
                        #         type='text', 
                        #         text='{'file_exists': true, 'query_exists': false, 'matches': []}', 
                        #         annotations=None
                        #     )] isError=False
                        # """
                        # Use a different name: don't overwrite the tool-call content!
                        tool_return_content = result.content[0]
                        final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")
                        # Add tool-call response to the content list 
                        if hasattr(tool_return_content, 'text') and tool_return_content.text:
                            content_list.append({
                                'type': 'tool_result', 
                                'tool_use_id': tool_use_id, 
                                'content': tool_return_content.text 
                            })
                    except Exception as e:
                        # raise RuntimeError(f"[ERROR / Orchestrator / process_query] Error calling tool {tool_name} with args {tool_args}: {e}")
                        logger.error(f"[ERROR / Orchestrator / process_query] Error calling tool {tool_name} with args {tool_args}: {e}")
                        final_text.append(f"[Error calling tool {tool_name} with args {tool_args}: {e}]")
                        content_list.append({
                            'type': 'tool_result', 
                            'tool_use_id': tool_use_id, 
                            'content': f"[Error calling tool {tool_name} with args {tool_args}: {e}]"
                        })
            if not has_tool_calls:
                break 
            # Add the user's tool-use response to the conversation. 
            new_message = {'role': 'user', 'content': content_list} 
            # print(f"    DEBUG: new message \n\n\n{new_message}\n\n\n")
            running_messages = running_messages + [new_message]
            response = self.anthropic.messages.create(
                messages=running_messages,
                tools=available_tools,
                **self.claude_args
            )
        final_text = "\n".join(final_text)
        logger.info(f'[INFO] FINAL_TEXT: \n\n\n{final_text}\n\n\n')
        return final_text
    
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
    
    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

    # ------------------------------------------------------------------
    # Streaming version that yields assistant tokens in real‑time
    # ------------------------------------------------------------------
    async def stream_query(
        self,
        messages: List[Dict[str, Any]],
        pdf_root: str = "./files",
        pdf_files=None,
        max_rounds: int = 10,
    ) -> AsyncGenerator[str, None]:
        """Stream assistant tokens **while preserving** the full
        ``process_query`` logic (PDF injection, tool‑calls, multi‑round
        reasoning).

        The implementation follows these steps:
        1. Build a conversation identical to :py:meth:`process_query` via
           :py:meth:`_prepare_messages`.
        2. Enter a *while* loop (bounded by ``max_rounds``) where we make
           a streaming Claude call (``stream=True``).
        3. For every ``text_delta`` chunk coming back we immediately
           ``yield`` it to the caller **and** accumulate it in
           ``assistant_blocks`` so it becomes part of the conversation
           context for any further calls.
        4. If, instead of text, Claude emits a ``tool_use`` delta we:
           a. Execute the tool via the MCP session.
           b. Close out the assistant turn constructed so far
              (including the ``tool_use`` block).
           c. Append a *user* message with the tool result.
           d. Break the *async‑for* loop to start **another** streaming
              request, thereby emulating the recursive behaviour of the
              non‑streaming ``process_query``.
        5. If the stream ends *without* any tool calls we consider the
           task done and return, terminating the generator.
        """

        # ---- 0. prepare conversation identical to process_query -------
        running_messages: List[Dict[str, Any]] = self._prepare_messages(
            messages, pdf_root, pdf_files
        )

        # Cache available tools once per outer call
        tools_response = await self.session.list_tools()
        available_tools = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.inputSchema,
            }
            for t in tools_response.tools
        ]

        rounds_left = max_rounds

        # ----------------------------------------------------------------
        # Main reasoning loop                                             |
        # ----------------------------------------------------------------
        while rounds_left > 0:
            rounds_left -= 1

            # Keep track of content blocks that will form the assistant
            assistant_blocks: List[Dict[str, Any]] = []

            # ---- 1. make streaming request to Claude ------------------
            stream = self.anthropic.messages.create(
                messages=running_messages,
                tools=available_tools,
                tool_choice={"type": "any"},
                stream=True,
                **self.claude_args,
            )

            # The Anthropic SDK stream object is a synchronous iterator
            # even when called from async code. Iterate over it with a
            # normal *for* loop inside this async function.
            for delta in stream:
                dtype = getattr(delta, "type", None)

                # 1.a) Text token events --------------------------------
                if dtype in {"text_delta", "text", "content_block_delta"}:
                    #  Different SDK versions expose text in different ways.
                    token: str | None = getattr(delta, "text", None)

                    # Newer SDKs wrap text inside a `delta` model that has a
                    # `.text` attribute (not a dict). Guard accordingly.
                    if token is None and hasattr(delta, "delta"):
                        inner_delta = getattr(delta, "delta")
                        token = getattr(inner_delta, "text", None)

                    if token is None:
                        token = ""
                    if token:
                        # forward to client immediately
                        yield token

                        # accumulate into assistant_blocks for context
                        if assistant_blocks and assistant_blocks[-1]["type"] == "text":
                            assistant_blocks[-1]["text"] += token
                        else:
                            assistant_blocks.append({"type": "text", "text": token})

                # 1.b) Tool‑call ----------------------------------------
                elif dtype in {"tool_use", "content_block_start"} and getattr(delta, "name", None):
                    # Record the tool_use block exactly as received so
                    # that the assistant message we store later mirrors
                    # Claude's output.
                    tool_name = getattr(delta, "name", None)
                    tool_args = getattr(delta, "input", None)

                    if tool_name is None or tool_args is None:
                        # Not actually a tool use; ignore.
                        continue

                    assistant_blocks.append(
                        {
                            "type": "tool_use",
                            "id": getattr(delta, "id", None),
                            "name": tool_name,
                            "input": tool_args,
                        }
                    )

                    logger.info(
                        f"[stream_query] Executing tool '{tool_name}' with args {tool_args}"
                    )

                    # Emit an informative marker token so the client is
                    # aware that a tool is being called. This mirrors the
                    # behaviour of the non‑streaming `process_query` which
                    # inserts `[Calling tool ...]` into the final text.
                    placeholder = f"[Calling tool {tool_name} with args {tool_args}]"
                    yield placeholder
                    if assistant_blocks and assistant_blocks[-1]["type"] == "text":
                        assistant_blocks[-1]["text"] += placeholder
                    else:
                        assistant_blocks.append({"type": "text", "text": placeholder})

                    # ----------------------------------------------------------------
                    # Execute tool via MCP
                    try:
                        tool_result = await self.session.call_tool(tool_name, tool_args)
                        tool_return_content = tool_result.content[0]
                        tool_result_text = (
                            getattr(tool_return_content, "text", str(tool_return_content))
                            if tool_return_content is not None
                            else ""
                        )
                    except Exception as exc:
                        logger.error(
                            f"Tool '{tool_name}' failed: {exc}", exc_info=True
                        )
                        tool_result_text = f"[Tool error: {exc}]"

                    # ----------------------------------------------------------------
                    # Close current assistant turn and append tool result
                    running_messages.append(
                        {"role": "assistant", "content": assistant_blocks}
                    )

                    running_messages.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": getattr(delta, "id", None),
                                    "content": tool_result_text,
                                }
                            ],
                        }
                    )

                    # Break out of current stream to initiate the next
                    # round (if any) *after* the async-for loop.
                    break

            else:
                # The for‑loop exhausted *without* a break, meaning we
                # reached the end of the stream and there were **no**
                # tool calls in this round. We thus finalise the
                # assistant message and terminate the generator.
                running_messages.append(
                    {"role": "assistant", "content": assistant_blocks}
                )
                return  # End of generator – implicit StopAsyncIteration

            # Loop continues when a tool_use was encountered -------------

        # Reached round limit – quietly stop
        return

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