"""MCP 注册中心

管理所有 MCP Server 和 MCP Client 的注册与查找。
"""

from typing import Dict, List, Optional, Union

from .base import MCPClient, MCPServer


class MCPRegistry:
    """MCP 注册表

    统一管理 MCPServer（内置）和 MCPClient（远程）实例。
    """

    def __init__(self):
        self._servers: Dict[str, MCPServer] = {}
        self._clients: Dict[str, MCPClient] = {}

    # ── Server 管理 ──

    def register_server(self, server: MCPServer) -> None:
        """注册内置 MCP Server"""
        if not server.name:
            raise ValueError(f"MCP Server {server} 必须定义 name 属性")
        self._servers[server.name] = server

    def unregister_server(self, name: str) -> bool:
        """移除 MCP Server"""
        return self._servers.pop(name, None) is not None

    def get_server(self, name: str) -> Optional[MCPServer]:
        """按名称获取 Server"""
        return self._servers.get(name)

    def list_servers(self) -> List[MCPServer]:
        """列出所有 Server"""
        return list(self._servers.values())

    # ── Client 管理 ──

    def register_client(self, client: MCPClient) -> None:
        """注册远程 MCP Client"""
        self._clients[client.transport] = client

    def unregister_client(self, transport: str) -> bool:
        """移除 MCP Client"""
        return self._clients.pop(transport, None) is not None

    def get_client(self, transport: str) -> Optional[MCPClient]:
        """按传输方式获取 Client"""
        return self._clients.get(transport)

    def list_clients(self) -> List[MCPClient]:
        """列出所有 Client"""
        return list(self._clients.values())

    # ── 统一查询 ──

    def get_all_tools(self) -> List[dict]:
        """获取所有 MCP Server 提供的工具 schema"""
        schemas = []
        for server in self._servers.values():
            for tool in server.get_tools():
                schemas.append(tool.to_dict())
        return schemas

    def find_tool_server(self, tool_name: str) -> Optional[MCPServer]:
        """查找提供指定工具的 Server"""
        for server in self._servers.values():
            for tool in server.get_tools():
                if tool.name == tool_name:
                    return server
        return None

    def __len__(self) -> int:
        return len(self._servers) + len(self._clients)

    def __bool__(self) -> bool:
        return True