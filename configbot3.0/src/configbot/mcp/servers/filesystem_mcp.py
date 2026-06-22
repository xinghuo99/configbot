"""文件系统 MCP Server 实现

提供文件读写、目录遍历等文件系统操作，
作为 MCP Server 扩展示例。
"""

import os
from pathlib import Path
from typing import List

from ..base import MCPServer, MCPResponse, MCPTool


class FilesystemMCPServer(MCPServer):
    name = "filesystem"
    description = "文件系统操作 MCP 服务"
    version = "1.0.0"

    def get_tools(self) -> List[MCPTool]:
        return [
            MCPTool(
                name="fs_read",
                description="读取文件内容",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "文件路径"},
                        "encoding": {
                            "type": "string",
                            "description": "编码",
                            "default": "utf-8",
                        },
                    },
                    "required": ["path"],
                },
            ),
            MCPTool(
                name="fs_write",
                description="写入文件",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "文件路径"},
                        "content": {"type": "string", "description": "写入内容"},
                    },
                    "required": ["path", "content"],
                },
            ),
            MCPTool(
                name="fs_list",
                description="列出目录内容",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "目录路径"},
                    },
                    "required": ["path"],
                },
            ),
            MCPTool(
                name="fs_exists",
                description="检查文件或目录是否存在",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "路径"},
                    },
                    "required": ["path"],
                },
            ),
        ]

    async def call_tool(self, tool_name: str, **kwargs) -> MCPResponse:
        handlers = {
            "fs_read": self._handle_read,
            "fs_write": self._handle_write,
            "fs_list": self._handle_list,
            "fs_exists": self._handle_exists,
        }
        handler = handlers.get(tool_name)
        if not handler:
            return MCPResponse(success=False, error=f"未知工具: {tool_name}")
        try:
            return await handler(**kwargs)
        except Exception as e:
            return MCPResponse(success=False, error=str(e))

    async def _handle_read(self, path: str, encoding: str = "utf-8") -> MCPResponse:
        p = Path(path)
        if not p.exists():
            return MCPResponse(success=False, error=f"文件不存在: {path}")
        content = p.read_text(encoding=encoding)
        return MCPResponse(success=True, data=content)

    async def _handle_write(self, path: str, content: str) -> MCPResponse:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return MCPResponse(success=True, data=f"已写入: {path}")

    async def _handle_list(self, path: str) -> MCPResponse:
        p = Path(path)
        if not p.is_dir():
            return MCPResponse(success=False, error=f"不是目录: {path}")
        entries = []
        for entry in sorted(p.iterdir()):
            t = "DIR" if entry.is_dir() else "FILE"
            entries.append(f"[{t}] {entry.name}")
        return MCPResponse(success=True, data=entries)

    async def _handle_exists(self, path: str) -> MCPResponse:
        p = Path(path)
        return MCPResponse(
            success=True,
            data={"path": path, "exists": p.exists(), "is_file": p.is_file(), "is_dir": p.is_dir()},
        )