"""日志分析 Skill（外部 Skill 示例）

从日志文件中提取错误、警告信息，生成分析报告。
放置于 xiaohua/skills/ 目录下，通过 load_skill_from_file 动态加载。
"""

import re
from collections import Counter
from typing import Any, Dict

from configbot.skills.base import BaseSkill, SkillCategory, SkillExecResult


class LogAnalyzerSkill(BaseSkill):
    """日志文件分析 Skill

    分析日志内容，统计错误、警告、信息数量，
    提取 Top N 错误信息。
    """
    name = "log_analyzer"
    description = "分析日志文件，提取错误和警告信息，生成统计报告"
    category = SkillCategory.DATA
    version = "1.0.0"
    requires_tools = {"read_file"}

    # 日志级别模式
    LEVEL_PATTERNS = {
        "ERROR": re.compile(r"\bERROR\b", re.IGNORECASE),
        "WARN": re.compile(r"\bWARN(?:ING)?\b", re.IGNORECASE),
        "INFO": re.compile(r"\bINFO\b", re.IGNORECASE),
        "DEBUG": re.compile(r"\bDEBUG\b", re.IGNORECASE),
    }

    async def execute(
        self,
        context: Dict[str, Any],
        tool_executor: Any,
        mcp_executor: Any,
    ) -> SkillExecResult:
        file_path = context.get("file_path")
        if not file_path:
            return SkillExecResult(success=False, error="缺少参数: file_path")

        result = await tool_executor("read_file", file_path=file_path)
        if not result.success:
            return SkillExecResult(success=False, error=f"读取文件失败: {result.error}")

        lines = result.data.split("\n")
        steps = [{"step": "read_file", "status": "ok"}]

        # 统计各级别日志
        level_counts = Counter()
        error_lines = []
        warn_lines = []

        for i, line in enumerate(lines, 1):
            for level, pattern in self.LEVEL_PATTERNS.items():
                if pattern.search(line):
                    level_counts[level] += 1
                    if level == "ERROR":
                        error_lines.append({"line": i, "content": line.strip()[:200]})
                    elif level == "WARN":
                        warn_lines.append({"line": i, "content": line.strip()[:200]})
                    break

        steps.append({"step": "analyze", "status": "ok", "levels_found": dict(level_counts)})

        # 生成报告
        report = {
            "file": file_path,
            "total_lines": len(lines),
            "level_summary": dict(level_counts),
            "error_count": len(error_lines),
            "warn_count": len(warn_lines),
            "top_errors": error_lines[:10],
            "top_warnings": warn_lines[:10],
            "health": self._health_check(level_counts, len(lines)),
        }

        return SkillExecResult(
            success=True,
            data=report,
            steps=steps,
            metadata={"file_path": file_path},
        )

    @staticmethod
    def _health_check(level_counts: Counter, total: int) -> str:
        errors = level_counts.get("ERROR", 0)
        warns = level_counts.get("WARN", 0)
        if errors > 0:
            return "异常（存在错误）"
        elif warns > 10:
            return "警告（警告较多）"
        elif warns > 0:
            return "正常（有少量警告）"
        else:
            return "健康"