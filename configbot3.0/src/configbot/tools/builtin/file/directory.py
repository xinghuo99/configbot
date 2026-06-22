"""目录操作工具"""

from pathlib import Path
from typing import Any, Dict

from ...base import BaseTool, ToolExecResult


class ListDirTool(BaseTool):
    name = "list_dir"
    description = "列出目录中的文件和子目录"

    def _get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "dir_path": {"type": "string", "description": "要列出的目录路径"},
            },
            "required": ["dir_path"],
        }

    async def execute(self, dir_path: str) -> ToolExecResult:
        try:
            path = Path(dir_path)
            if not path.exists():
                return ToolExecResult(success=False, error=f"目录不存在: {dir_path}")
            if not path.is_dir():
                return ToolExecResult(success=False, error=f"不是目录: {dir_path}")

            entries = []
            for entry in sorted(path.iterdir()):
                entry_type = "DIR" if entry.is_dir() else "FILE"
                entries.append(f"[{entry_type}] {entry.name}")

            return ToolExecResult(
                success=True,
                data="\n".join(entries),
                metadata={"dir_path": str(path.absolute()), "count": len(entries)},
            )
        except Exception as e:
            return ToolExecResult(success=False, error=str(e))


class DeleteFileTool(BaseTool):
    """删除文件或目录"""
    name = "delete_file"
    description = "删除指定文件或空目录"

    def _get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "要删除的文件路径"},
            },
            "required": ["file_path"],
        }

    async def execute(self, file_path: str) -> ToolExecResult:
        try:
            path = Path(file_path)
            if not path.exists():
                return ToolExecResult(success=False, error=f"路径不存在: {file_path}")
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
            return ToolExecResult(success=True, data=f"已删除: {file_path}")
        except Exception as e:
            return ToolExecResult(success=False, error=str(e))


class FileInfoTool(BaseTool):
    """获取文件详细信息"""
    name = "file_info"
    description = "获取文件的详细信息（大小、修改时间等）"

    def _get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "文件路径"},
            },
            "required": ["file_path"],
        }

    async def execute(self, file_path: str) -> ToolExecResult:
        try:
            path = Path(file_path)
            if not path.exists():
                return ToolExecResult(success=False, error=f"文件不存在: {file_path}")

            stat = path.stat()
            info = {
                "name": path.name,
                "path": str(path.absolute()),
                "size": stat.st_size,
                "size_human": self._format_size(stat.st_size),
                "is_file": path.is_file(),
                "is_dir": path.is_dir(),
                "suffix": path.suffix,
                "modified": stat.st_mtime,
            }
            return ToolExecResult(success=True, data=info)
        except Exception as e:
            return ToolExecResult(success=False, error=str(e))

    @staticmethod
    def _format_size(size: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"