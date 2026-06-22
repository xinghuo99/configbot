"""MCP 管理器

负责 MCP 工具的调用调度。Agent 通过 MCPManager 统一调用
内置 Server 和远程 Client 的工具。
"""

from typing import Any, Dict, List, Optional

from .base import MCPClient, MCPResponse, MCPServer
from .registry import MCPRegistry


class MCPManager:
    """MCP 调用管理器

    使用方式：
        manager = MCPManager(registry)
        result = await manager.call("filesystem", "read_file", path="/tmp/a.txt")
    """

    def __init__(self, registry: Optional[MCPRegistry] = None):
        self.registry = registry if registry is not None else MCPRegistry()

    async def call(
        self,
        server_name: str,
        tool_name: str,
        **kwargs,
    ) -> MCPResponse:
        """调用指定 MCP Server 的工具"""
        server = self.registry.get_server(server_name)
        if server:
            return await server.call_tool(tool_name, **kwargs)

        return MCPResponse(
            success=False,
            error=f"MCP Server 不存在: {server_name}",
        )

    async def call_remote(
        self,
        transport: str,
        tool_name: str,
        **kwargs,
    ) -> MCPResponse:
        """通过远程 Client 调用工具"""
        client = self.registry.get_client(transport)
        if not client:
            return MCPResponse(
                success=False,
                error=f"MCP Client 不存在 (transport={transport})",
            )
        return await client.call_tool(tool_name, **kwargs)

    def get_all_tool_schemas(self) -> List[dict]:
        """获取所有可用 MCP 工具 schema"""
        return self.registry.get_all_tools()

    async def connect_all_clients(self) -> Dict[str, bool]:
        """连接所有远程 Client"""
        results = {}
        for client in self.registry.list_clients():
            results[client.transport] = await client.connect()
        return results

    async def disconnect_all_clients(self) -> None:
        """断开所有远程 Client"""
        for client in self.registry.list_clients():
            await client.disconnect()