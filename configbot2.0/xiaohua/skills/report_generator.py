"""数据报告生成 Skill（外部 Skill 示例）

将结构化数据格式化为 Markdown / HTML 报告。
放置于 xiaohua/skills/ 目录下，通过 load_skill_from_file 动态加载。
"""

from typing import Any, Dict

from configbot.skills.base import BaseSkill, SkillCategory, SkillExecResult


class ReportGeneratorSkill(BaseSkill):
    """数据报告生成 Skill

    将 JSON 数据格式化为 Markdown 表格或 HTML 报告。
    """
    name = "report_generator"
    description = "将结构化数据生成 Markdown 或 HTML 格式的报告"
    category = SkillCategory.DATA
    version = "1.0.0"
    requires_tools = set()

    async def execute(
        self,
        context: Dict[str, Any],
        tool_executor: Any,
        mcp_executor: Any,
    ) -> SkillExecResult:
        data = context.get("data")
        title = context.get("title", "数据报告")
        format_type = context.get("format", "markdown")

        if not data:
            return SkillExecResult(success=False, error="缺少参数: data")

        if format_type == "markdown":
            content = self._to_markdown(title, data)
        elif format_type == "html":
            content = self._to_html(title, data)
        else:
            return SkillExecResult(success=False, error=f"不支持的格式: {format_type}")

        return SkillExecResult(
            success=True,
            data=content,
            metadata={"title": title, "format": format_type},
        )

    def _to_markdown(self, title: str, data: Any) -> str:
        """生成 Markdown 报告"""
        lines = [f"# {title}", "", f"生成时间: 2026-06-10", ""]

        if isinstance(data, list):
            lines.append("| # | 内容 |")
            lines.append("|---|------|")
            for i, item in enumerate(data, 1):
                lines.append(f"| {i} | {item} |")
        elif isinstance(data, dict):
            lines.append("| 键 | 值 |")
            lines.append("|----|-----|")
            for k, v in data.items():
                lines.append(f"| {k} | {v} |")
        else:
            lines.append(f"```\n{data}\n```")

        return "\n".join(lines)

    def _to_html(self, title: str, data: Any) -> str:
        """生成 HTML 报告"""
        parts = [
            "<!DOCTYPE html>",
            "<html><head><meta charset='utf-8'>",
            f"<title>{title}</title>",
            "<style>body{font-family:Arial;margin:20px;}",
            "table{border-collapse:collapse;width:100%;}",
            "td,th{border:1px solid #ddd;padding:8px;text-align:left;}",
            "th{background:#4CAF50;color:white;}</style>",
            "</head><body>",
            f"<h1>{title}</h1>",
            "<p>生成时间: 2026-06-10</p>",
        ]

        if isinstance(data, list):
            parts.append("<table><tr><th>#</th><th>内容</th></tr>")
            for i, item in enumerate(data, 1):
                parts.append(f"<tr><td>{i}</td><td>{item}</td></tr>")
            parts.append("</table>")
        elif isinstance(data, dict):
            parts.append("<table><tr><th>键</th><th>值</th></tr>")
            for k, v in data.items():
                parts.append(f"<tr><td>{k}</td><td>{v}</td></tr>")
            parts.append("</table>")
        else:
            parts.append(f"<pre>{data}</pre>")

        parts.append("</body></html>")
        return "\n".join(parts)