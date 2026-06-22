"""代码审查 Skill

对指定代码文件进行自动化审查，检查代码质量、风格和潜在问题。
演示 Skill 如何组合内置工具完成复杂任务。
"""

from typing import Any, Dict

from ..base import BaseSkill, SkillCategory, SkillExecResult


class CodeReviewSkill(BaseSkill):
    name = "code_review"
    description = "对代码文件进行自动化审查，检查代码质量和风格问题"
    category = SkillCategory.CODE
    version = "1.0.0"
    requires_tools = {"read_file"}

    async def execute(
        self,
        context: Dict[str, Any],
        tool_executor: Any,
        mcp_executor: Any,
    ) -> SkillExecResult:
        """执行代码审查流程

        1. 读取目标文件
        2. 分析代码质量
        3. 生成审查报告
        """
        file_path = context.get("file_path")
        if not file_path:
            return SkillExecResult(success=False, error="缺少参数: file_path")

        steps = []
        issues = []

        # Step 1: 读取文件
        result = await tool_executor("read_file", file_path=file_path)
        if not result.success:
            return SkillExecResult(success=False, error=f"读取文件失败: {result.error}")
        steps.append({"step": "read_file", "status": "ok"})

        code = result.data
        lines = code.split("\n")

        # Step 2: 代码质量分析
        # 检查行长度
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                issues.append(
                    {"line": i, "severity": "warning", "message": f"行长度超过120字符 ({len(line)}字符)"}
                )

        # 检查 TODO/FIXME
        for i, line in enumerate(lines, 1):
            if "TODO" in line:
                issues.append(
                    {"line": i, "severity": "info", "message": "发现 TODO 标记"}
                )
            if "FIXME" in line:
                issues.append(
                    {"line": i, "severity": "warning", "message": "发现 FIXME 标记"}
                )

        # 检查空文件
        if not code.strip():
            issues.append({"line": 0, "severity": "warning", "message": "文件为空"})

        # 检查文件大小
        if len(lines) > 500:
            issues.append(
                {
                    "line": 0,
                    "severity": "info",
                    "message": f"文件较大 ({len(lines)}行)，建议拆分",
                }
            )

        steps.append({"step": "analyze_code", "status": "ok", "issues_found": len(issues)})

        # Step 3: 生成报告
        severity_counts = {"error": 0, "warning": 0, "info": 0}
        for issue in issues:
            sev = issue["severity"]
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        report = {
            "file": file_path,
            "total_lines": len(lines),
            "issues": issues,
            "summary": severity_counts,
            "score": self._calculate_score(severity_counts, len(lines)),
        }

        return SkillExecResult(
            success=True,
            data=report,
            steps=steps,
            metadata={"file_path": file_path, "total_issues": len(issues)},
        )

    @staticmethod
    def _calculate_score(severity_counts: dict, total_lines: int) -> str:
        """根据问题严重程度计算代码评分"""
        score = 100
        score -= severity_counts.get("error", 0) * 15
        score -= severity_counts.get("warning", 0) * 5
        score -= severity_counts.get("info", 0) * 1
        score = max(0, min(100, score))

        if score >= 90:
            return f"{score}/100 (优秀)"
        elif score >= 70:
            return f"{score}/100 (良好)"
        elif score >= 50:
            return f"{score}/100 (一般)"
        else:
            return f"{score}/100 (需改进)"