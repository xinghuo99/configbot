"""搜索工具（模拟实现）"""

from typing import Any, Dict

from ...base import BaseTool, ToolExecResult


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "执行网页搜索（模拟实现，实际使用时对接搜索 API）"

    def _get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "max_results": {"type": "integer", "description": "最大返回结果数，默认 5", "default": 5},
            },
            "required": ["query"],
        }

    async def execute(self, query: str, max_results: int = 5) -> ToolExecResult:
        return ToolExecResult(
            success=True,
            data=f'[模拟搜索] 查询: "{query}", 结果数: {max_results}\n'
            "提示: 对接真实搜索 API 如 Bing/Google 后可获得实际结果。",
            metadata={"query": query, "max_results": max_results, "simulated": True},
        )