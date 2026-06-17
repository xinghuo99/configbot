"""代码格式化/处理工具"""

import json
import re
from string import Template
from typing import Any, Dict

from ...base import BaseTool, ToolExecResult


class JsonFormatterTool(BaseTool):
    """JSON 格式化工具"""
    name = "json_format"
    description = "格式化或压缩 JSON 字符串"

    def _get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "json_str": {"type": "string", "description": "JSON 字符串"},
                "indent": {"type": "integer", "description": "缩进空格数，0 表示压缩", "default": 2},
            },
            "required": ["json_str"],
        }

    async def execute(self, json_str: str, indent: int = 2) -> ToolExecResult:
        try:
            obj = json.loads(json_str)
            formatted = json.dumps(obj, ensure_ascii=False, indent=indent if indent > 0 else None)
            return ToolExecResult(success=True, data=formatted)
        except json.JSONDecodeError as e:
            return ToolExecResult(success=False, error=f"JSON 解析失败: {e}")


class TextTemplateTool(BaseTool):
    """文本模板替换工具"""
    name = "text_template"
    description = "使用模板字符串替换变量，变量格式 ${var_name}"

    def _get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "template": {"type": "string", "description": "模板字符串，如 'Hello ${name}'"},
                "variables": {"type": "object", "description": "变量字典，如 {\"name\": \"World\"}"},
            },
            "required": ["template", "variables"],
        }

    async def execute(self, template: str, variables: dict) -> ToolExecResult:
        try:
            result = Template(template).safe_substitute(**variables)
            return ToolExecResult(success=True, data=result)
        except Exception as e:
            return ToolExecResult(success=False, error=str(e))