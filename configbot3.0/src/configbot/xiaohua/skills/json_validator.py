"""JSON 验证与格式化 Skill（外部 Skill 示例）

验证 JSON 字符串的合法性，并支持格式化输出。
放置于 xiaohua/skills/ 目录下，Agent 启动时自动加载。
"""

import json
from typing import Any, Dict

from configbot.skills.base import BaseSkill, SkillCategory, SkillExecResult


class JsonValidatorSkill(BaseSkill):
    """JSON 验证与格式化 Skill

    验证 JSON 字符串是否合法，支持压缩和美化输出。
    """
    name = "json_validator"
    description = "验证 JSON 字符串合法性，支持压缩和美化格式化"
    category = SkillCategory.DATA
    version = "1.0.0"
    requires_tools = set()

    async def execute(
        self,
        context: Dict[str, Any],
        tool_executor: Any,
        mcp_executor: Any,
    ) -> SkillExecResult:
        raw = context.get("json_text", "")
        action = context.get("action", "validate")  # validate | format | compact

        if not raw:
            return SkillExecResult(success=False, error="缺少参数: json_text")

        steps = []

        try:
            parsed = json.loads(raw)
            steps.append({"step": "parse", "status": "ok"})
        except json.JSONDecodeError as e:
            return SkillExecResult(
                success=False,
                error=f"JSON 解析失败: {e.msg} (位置 {e.pos})",
                steps=[{"step": "parse", "status": "fail", "error": str(e)}],
            )

        if action == "format":
            output = json.dumps(parsed, ensure_ascii=False, indent=2)
        elif action == "compact":
            output = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
        else:
            output = json.dumps(parsed, ensure_ascii=False, indent=2)

        steps.append({"step": action, "status": "ok"})

        # 统计信息
        if isinstance(parsed, dict):
            stats = {"type": "object", "keys": len(parsed), "size": len(raw)}
        elif isinstance(parsed, list):
            stats = {"type": "array", "items": len(parsed), "size": len(raw)}
        else:
            stats = {"type": type(parsed).__name__, "size": len(raw)}

        return SkillExecResult(
            success=True,
            data={"valid": True, "formatted": output, "stats": stats},
            steps=steps,
            metadata={"action": action},
        )