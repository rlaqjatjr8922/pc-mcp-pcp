from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
class MCPServer(FastMCP):
    def __init__(self, name, instructions=None):
        super().__init__(name, instructions=instructions, host='127.0.0.1', streamable_http_path='/mcp', stateless_http=True, json_response=True)
        @self._mcp_server.list_tools()
        async def listing(): return await self.list_tools()
        @self._mcp_server.call_tool(validate_input=False)
        async def calling(name, arguments): return await self.call_tool(name, arguments)
    def streamable_http_app(self, **kwargs):
        return super().streamable_http_app()
