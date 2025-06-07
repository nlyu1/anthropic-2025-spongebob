import asyncio
import os
import logging # Import logging
from typing import Optional
from contextlib import AsyncExitStack
import base64, glob

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from anthropic import Anthropic
import json
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

    async def process_query(self, messages: list, pdf_root="./files", pdf_files=None, max_rounds=50) -> str:
        """
        pdf_root: where to look for pdf's
        pdf_files: which pdf files to parse & add to conversation. By default, everything in the folder is added 
        max_rounds: maximum rounds of internal conversation iteration Claude can call (i.e. number of round trips between Anthropic and local MCP server)
        """
        last_message = messages[-1]
        # logger.info(f"[INFO/Orchestrator]: last message {last_message}")
        if last_message["role"] != "user":
            # Last message should be of type 
            logger.error(f"[ERROR/Orchestrator] Last message is not a user message")
            raise ValueError("Last message is not a user message")
        
        # Prepare the content list from the last user message
        content_list = []
        if not isinstance(last_message["content"], list):
            # Assume it's a simple string, convert to text block
            content_list = [{'type': 'text', 'text': last_message['content']}]
            # print('    DEBUG: last_message["content"] is not a list, creating list with text block')
        else:
            # It's already a list, make a copy
            content_list = last_message['content'].copy()
            # print('    DEBUG: last_message["content"] is a list, copying')

        # Load and add PDF blocks
        pdf_blocks = load_pdf_as_blocks(pdf_root, pdf_files)
        content_list.extend(pdf_blocks)
        # print(f'    DEBUG: Extended content list length: {len(content_list)}')

        # Create the new last message with the combined content
        new_last_message = {
            'role': 'user',
            'content': content_list
        }
        
        # Replace the last message in the list
        messages = messages[:-1] + [new_last_message]
        # print(f'\n\nOld last message\n{last_message}\n\n\n')
        # print(f'\n\nNew last message\n{new_last_message}\n\n\n')
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
            logger.info(f"\n\n[INFO/Orchestrator] Processing round #{i}\n\n     Types: {compute_types(response)}\n\n")
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
                        # final_text.append(f"\n    `[Calling tool {tool_name} with args {tool_args}]`\n")
                        tool_snippet = ','.join([f"{k}: {v}" for k, v in tool_args.items()])
                        tool_display = f"""  🔵 🛠️ {tool_name} – {tool_snippet}\n"""
                        final_text.append(tool_display)
                        # Add tool-call response to the content list 
                        if hasattr(tool_return_content, 'text') and tool_return_content.text:
                            content_list.append({
                                'type': 'tool_result', 
                                'tool_use_id': tool_use_id, 
                                'content': tool_return_content.text 
                            })
                            content_list.append({
                                'type': 'text',
                                'text': f"Call {i+1} of {max_rounds} tools executed."
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