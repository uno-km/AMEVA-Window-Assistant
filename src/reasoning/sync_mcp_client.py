import asyncio
import os
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

class SyncMCPClient:
    """
    동기(Synchronous) 환경인 AMEVA Window Assistant에서 
    비동기(Async) 기반의 공식 MCP SDK를 쉽게 사용할 수 있도록 감싸주는 래퍼 클래스.
    """
    def __init__(self, script_path: str):
        self.script_path = script_path
        
    def execute_tool(self, tool_name: str, arguments: dict) -> str:
        async def _run():
            server_params = StdioServerParameters(
                command="python",
                args=[self.script_path]
            )
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    if result.isError:
                        return f"Error: {result.content}"
                    else:
                        texts = [getattr(c, 'text', str(c)) for c in result.content if getattr(c, 'type', '') == 'text']
                        if not texts:
                            return str(result.content)
                        return "\n".join(texts)
                        
        return asyncio.run(_run())
        
    def get_tools(self) -> list:
        async def _get():
            server_params = StdioServerParameters(
                command="python",
                args=[self.script_path]
            )
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    openai_tools = []
                    for t in result.tools:
                        openai_tools.append({
                            "type": "function",
                            "function": {
                                "name": t.name,
                                "description": t.description or "",
                                "parameters": t.inputSchema
                            }
                        })
                    return openai_tools
        return asyncio.run(_get())
