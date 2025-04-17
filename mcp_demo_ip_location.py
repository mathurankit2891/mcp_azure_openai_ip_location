import asyncio
from contextlib import AsyncExitStack
from openai import AzureOpenAI
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from dotenv import load_dotenv
import os
import json

load_dotenv()  # Load environment variables from .env


class MCPClient:
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.client = AzureOpenAI(
            azure_deployment="GPT-4o",
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2024-02-15-preview"
        )
        print("Init Done")

    async def connect_to_server(self):
        print("Reading config file")
        with open('config.json', 'r') as f:
            config = json.load(f)

        server_params = StdioServerParameters(
            command=config["mcpServers"]["mcp-server-ip-lookup"]["command"],
            args=config["mcpServers"]["mcp-server-ip-lookup"]["args"],
            env=config["mcpServers"]["mcp-server-ip-lookup"]["env"],
        )
        print("Server params processed")

        try:
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            self.stdio, self.write = stdio_transport
            print("Server process started and connected")
            self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
            await asyncio.wait_for(self.session.initialize(), timeout=5)
            print("Server connected successfully")
        except Exception as e:
            print(f"Error while connecting to the server: {str(e)}")

        response = await self.session.list_tools()
        tools = response.tools
        print(f"\nConnected to server with tools: {[tool.name for tool in tools]}")

    async def process_query(self, query: str) -> str:
        print(f"Processing query: {query}")
        messages = [
            {
                "role": "system",
                "content": "You are an assistant that can answer general questions using your own knowledge or use tools if necessary."
            },
            {"role": "user", "content": query}
        ]
        deployment_name = "GPT-4o"

        response = await self.session.list_tools()
        available_tools = [{
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.inputSchema
        } for tool in response.tools]
        available_tools = [{"type": "function", "function": tool} for tool in available_tools]

        print(f"Available tools: {[tool['function']['name'] for tool in available_tools]}")

        final_text = []

        response = await asyncio.to_thread(self.client.chat.completions.create,
                                           model=deployment_name,
                                           messages=messages,
                                           tools=available_tools,
                                           tool_choice="auto")

        msg = response.choices[0].message

        # Handle tool calls if any
        if msg.tool_calls:
            for tool_call in msg.tool_calls:
                print(f"Tool call detected: {tool_call.function.name} with arguments {tool_call.function.arguments}")
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}

                # Logging tool usage
                final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")

                # Append assistant tool_call message to history
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": tool_call.id,
                        "function": {
                            "name": tool_name,
                            "arguments": tool_call.function.arguments
                        },
                        "type": "function"
                    }]
                })

                # Call the tool
                result = await self.session.call_tool(tool_name, tool_args)
                print(f"Result from tool {tool_name}: {result.content}")

                # Append tool response to message history
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": result.content
                })

            # Final GPT call after tool responses
            response = await asyncio.to_thread(self.client.chat.completions.create,
                                               model=deployment_name,
                                               messages=messages,
                                               tools=available_tools,
                                               tool_choice="auto")
            final_response = response.choices[0].message.content
            final_text.append(final_response)
        else:
            # No tool used, just answer the question
            final_text.append(msg.content)

        return "\n".join(final_text)

    async def chat_loop(self):
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()
                if query.lower() == 'quit':
                    break
                response = await self.process_query(query)
                print("\n" + response)
            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        await self.exit_stack.aclose()


async def main():
    client = MCPClient()
    try:
        await client.connect_to_server()
        test_query = "Where is Boardman USA? Can you tell me state?"
        print(f"\nAuto test query: {test_query}")
        response = await client.process_query(test_query)
        print("\n" + response)
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
