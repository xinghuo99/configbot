"""工具注册中心

管理所有内置工具的注册、查找和获取。
支持动态注册新工具，实现热插拔扩展。
"""

from typing import Dict, List, Optional, Type

from .base import BaseTool


class ToolRegistry:
    """工具注册表

    使用方式：
        registry = ToolRegistry()
        registry.register(MyTool)
        tool = registry.get("my_tool")
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """注册一个工具实例"""
        if not tool.name:
            raise ValueError(f"工具 {tool} 必须定义 name 属性")
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> bool:
        """移除一个工具"""
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def get(self, name: str) -> Optional[BaseTool]:
        """按名称获取工具"""
        return self._tools.get(name)

    def list_all(self) -> List[BaseTool]:
        """列出所有已注册工具"""
        return list(self._tools.values())

    def get_all_schemas(self) -> List[dict]:
        """获取所有工具的 schema 列表，供 LLM 使用"""
        return [tool.get_schema() for tool in self._tools.values()]

    def find_by_keyword(self, keyword: str) -> List[BaseTool]:
        """按关键词搜索工具（匹配名称和描述）"""
        keyword_lower = keyword.lower()
        return [
            tool
            for tool in self._tools.values()
            if keyword_lower in tool.name.lower()
            or keyword_lower in tool.description.lower()
        ]

    def __len__(self) -> int:
        return len(self._tools)

    def __bool__(self) -> bool:
        return True

    def __contains__(self, name: str) -> bool:
        return name in self._tools