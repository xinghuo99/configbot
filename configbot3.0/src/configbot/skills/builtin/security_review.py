"""安全审查 Skill

对指定代码进行安全漏洞扫描，检查常见安全问题。
演示 Skill 如何扩展安全审查能力。
"""

import re
from typing import Any, Dict

from ..base import BaseSkill, SkillCategory, SkillExecResult


class SecurityReviewSkill(BaseSkill):
    name = "security_review"
    description = "对代码进行安全漏洞扫描，检测常见安全问题"
    category = SkillCategory.SECURITY
    version = "1.0.0"
    requires_tools = {"read_file"}

    # 安全规则定义（可扩展）
    SECURITY_RULES = [
        {
            "id": "SEC-001",
            "pattern": r'(?:password|passwd|pwd|secret)\s*=\s*["\'][^"\']+["\']',
            "severity": "high",
            "message": "硬编码密码/密钥",
        },
        {
            "id": "SEC-002",
            "pattern": r'(?:api_key|apikey|api_secret|access_key)\s*=\s*["\'][^"\']+["\']',
            "severity": "high",
            "message": "硬编码 API 密钥",
        },
        {
            "id": "SEC-003",
            "pattern": r'eval\s*\(',
            "severity": "high",
            "message": "使用 eval() 可能导致代码注入",
        },
        {
            "id": "SEC-004",
            "pattern": r'exec\s*\(',
            "severity": "high",
            "message": "使用 exec() 可能导致代码注入",
        },
        {
            "id": "SEC-005",
            "pattern": r'os\.system\s*\(',
            "severity": "medium",
            "message": "使用 os.system() 存在命令注入风险",
        },
        {
            "id": "SEC-006",
            "pattern": r'subprocess\.(?:call|Popen|run)\s*\([^)]*shell\s*=\s*True',
            "severity": "medium",
            "message": "subprocess 使用 shell=True 存在注入风险",
        },
        {
            "id": "SEC-007",
            "pattern": r'(?:SELECT|INSERT|UPDATE|DELETE).*%\s*[a-z_]+\s',
            "severity": "medium",
            "message": "SQL 语句使用字符串格式化可能导致注入",
            "case_sensitive": False,
        },
        {
            "id": "SEC-008",
            "pattern": r'pickle\.(?:loads?|dump)',
            "severity": "medium",
            "message": "使用 pickle 反序列化不可信数据存在安全风险",
        },
        {
            "id": "SEC-009",
            "pattern": r'yaml\.load\s*\(',
            "severity": "medium",
            "message": "使用 yaml.load() 而非 yaml.safe_load() 存在风险",
        },
        {
            "id": "SEC-010",
            "pattern": r'assert\s+.*\s*,\s*.*',
            "severity": "low",
            "message": "assert 语句在优化模式下会被移除，不建议用于安全检查",
        },
    ]

    async def execute(
        self,
        context: Dict[str, Any],
        tool_executor: Any,
        mcp_executor: Any,
    ) -> SkillExecResult:
        """执行安全审查流程"""
        file_path = context.get("file_path")
        if not file_path:
            return SkillExecResult(success=False, error="缺少参数: file_path")

        steps = []
        findings = []

        # Step 1: 读取文件
        result = await tool_executor("read_file", file_path=file_path)
        if not result.success:
            return SkillExecResult(success=False, error=f"读取文件失败: {result.error}")
        steps.append({"step": "read_file", "status": "ok"})

        code = result.data
        lines = code.split("\n")

        # Step 2: 逐行扫描安全规则
        for i, line in enumerate(lines, 1):
            for rule in self.SECURITY_RULES:
                flags = 0
                if rule.get("case_sensitive") is False:
                    flags = re.IGNORECASE
                if re.search(rule["pattern"], line, flags):
                    findings.append(
                        {
                            "rule_id": rule["id"],
                            "line": i,
                            "severity": rule["severity"],
                            "message": rule["message"],
                            "code_snippet": line.strip()[:100],
                        }
                    )

        steps.append({"step": "scan_rules", "status": "ok", "findings": len(findings)})

        # 如果需要，可通过 MCP 工具做更深入的检查
        # additional = await mcp_executor("security_scan", "deep_scan", ...)

        # Step 3: 生成报告
        severity_counts = {"high": 0, "medium": 0, "low": 0}
        for f in findings:
            severity_counts[f["severity"]] += 1

        risk_level = self._determine_risk(severity_counts)

        report = {
            "file": file_path,
            "total_lines": len(lines),
            "findings": findings,
            "summary": severity_counts,
            "risk_level": risk_level,
        }

        return SkillExecResult(
            success=True,
            data=report,
            steps=steps,
            metadata={"file_path": file_path, "total_findings": len(findings)},
        )

    @staticmethod
    def _determine_risk(counts: dict) -> str:
        if counts["high"] > 0:
            return "高危"
        elif counts["medium"] > 2:
            return "中危"
        elif counts["medium"] > 0 or counts["low"] > 3:
            return "低危"
        else:
            return "安全"