"""文件读写工具"""

import os
from pathlib import Path
from typing import Any, Dict

from ...base import BaseTool, ToolExecResult


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "读取指定文件的内容"

    def _get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "要读取的文件路径"},
                "encoding": {"type": "string", "description": "文件编码，默认 utf-8", "default": "utf-8"},
            },
            "required": ["file_path"],
        }

    async def execute(self, file_path: str, encoding: str = "utf-8") -> ToolExecResult:
        try:
            path = Path(file_path)
            if not path.exists():
                return ToolExecResult(success=False, error=f"文件不存在: {file_path}")
            content = path.read_text(encoding=encoding)
            return ToolExecResult(success=True, data=content)
        except Exception as e:
            return ToolExecResult(success=False, error=str(e))


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "将内容写入指定文件"

    def _get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "要写入的文件路径"},
                "content": {"type": "string", "description": "要写入的内容"},
                "encoding": {"type": "string", "description": "文件编码，默认 utf-8", "default": "utf-8"},
            },
            "required": ["file_path", "content"],
        }

    async def execute(self, file_path: str, content: str, encoding: str = "utf-8") -> ToolExecResult:
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding=encoding)
            return ToolExecResult(
                success=True,
                data=f"文件已写入: {file_path}",
                metadata={"file_path": str(path.absolute())},
            )
        except Exception as e:
            return ToolExecResult(success=False, error=str(e))