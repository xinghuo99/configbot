"""CSV 转换 Skill（外部 Skill 示例）

将 CSV 格式数据转换为 JSON 数组格式。
放置于 xiaohua/skills/ 目录下，Agent 启动时自动加载。
"""

import csv
import io
from typing import Any, Dict

from configbot.skills.base import BaseSkill, SkillCategory, SkillExecResult


class CsvConverterSkill(BaseSkill):
    """CSV 转 JSON Skill

    将 CSV 格式文本转换为 JSON 数组，支持自定义分隔符。
    """
    name = "csv_converter"
    description = "将 CSV 格式数据转换为 JSON 数组格式"
    category = SkillCategory.DATA
    version = "1.0.0"
    requires_tools = set()

    async def execute(
        self,
        context: Dict[str, Any],
        tool_executor: Any,
        mcp_executor: Any,
    ) -> SkillExecResult:
        csv_text = context.get("csv_text", "")
        delimiter = context.get("delimiter", ",")
        has_header = context.get("has_header", True)

        if not csv_text:
            return SkillExecResult(success=False, error="缺少参数: csv_text")

        steps = []
        try:
            reader = csv.reader(io.StringIO(csv_text), delimiter=delimiter)
            rows = list(reader)
            steps.append({"step": "parse_csv", "status": "ok", "rows": len(rows)})
        except Exception as e:
            return SkillExecResult(
                success=False,
                error=f"CSV 解析失败: {e}",
                steps=[{"step": "parse_csv", "status": "fail"}],
            )

        if not rows:
            return SkillExecResult(success=False, error="CSV 内容为空")

        if has_header:
            headers = rows[0]
            data = [dict(zip(headers, row)) for row in rows[1:]]
        else:
            data = [{"col_" + str(i): v for i, v in enumerate(row)} for row in rows]

        steps.append({"step": "convert", "status": "ok", "records": len(data)})

        return SkillExecResult(
            success=True,
            data={
                "columns": headers if has_header else list(range(len(rows[0]))),
                "records": data,
                "total": len(data),
            },
            steps=steps,
            metadata={"delimiter": delimiter, "has_header": has_header},
        )