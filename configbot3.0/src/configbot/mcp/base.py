"""MCP（Model Context Protocol）基类

定义 MCP Server 和 MCP Client 的抽象接口。
MCP 允许 Agent 通过标准化协议调用外部服务提供的工具。

参考规范: https://modelcontextprotocol.io/

扩展方式：
    继承 MCPServer 实现新的 MCP 服务，注册到 MCPRegistry。
"""

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class MCPToolType(Enum):
    """MCP 工具类型"""
    FUNCTION = "function"
    RESOURCE = "resource"
    PROMPT = "prompt"


@dataclass
class MCPTool:
    """MCP 工具描述"""
    name: str
    description: str
    tool_type: MCPToolType = MCPToolType.FUNCTION
    parameters_schema: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "type": self.tool_type.value,
            "parameters": self.parameters_schema,
        }


@dataclass
class MCPResponse:
    """MCP 调用响应"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    request_id: Optional[str] = None


class MCPServer(ABC):
    """MCP 服务端抽象基类

    每个 MCP Server 对外暴露一组工具（tools/resources/prompts），
    Agent 通过 MCPManager 与 Server 交互。

    扩展方式：
        class MyMCPServer(MCPServer):
            name = "my_mcp"
            description = "我的 MCP 服务"

            def get_tools(self) -> List[MCPTool]:
                return [MCPTool(name="my_tool", ...)]

            async def call_tool(self, tool_name: str, **kwargs) -> MCPResponse:
                ...
    """

    name: str = ""
    description: str = ""
    version: str = "0.1.0"

    @abstractmethod
    def get_tools(self) -> List[MCPTool]:
        """返回该 Server 提供的所有工具列表"""
        ...

    @abstractmethod
    async def call_tool(self, tool_name: str, **kwargs) -> MCPResponse:
        """调用指定的工具"""
        ...

    def get_server_info(self) -> Dict[str, Any]:
        """返回 Server 元信息"""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "tool_count": len(self.get_tools()),
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name!r})>"


class MCPClient(ABC):
    """MCP 客户端抽象基类

    用于连接远程 MCP Server（通过 stdio/HTTP/WebSocket 等传输方式）。
    内置 MCPServer 不需要客户端，直接用 MCPManager 管理即可。

    扩展方式：
        class HTTPMCPClient(MCPClient):
            transport = "http"

            async def connect(self, url: str) -> bool: ...
            async def list_tools(self) -> List[MCPTool]: ...
            async def call_tool(self, tool_name: str, **kwargs) -> MCPResponse: ...
    """

    transport: str = "stdio"

    @abstractmethod
    async def connect(self, **kwargs) -> bool:
        """连接到 MCP Server"""
        ...

    @abstractmethod
    async def list_tools(self) -> List[MCPTool]:
        """列出远程 Server 提供的工具"""
        ...

    @abstractmethod
    async def call_tool(self, tool_name: str, **kwargs) -> MCPResponse:
        """调用远程工具"""
        ...

    async def disconnect(self) -> None:
        """断开连接（可选实现）"""
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(transport={self.transport!r})>"