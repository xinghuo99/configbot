"""数据去重 Skill（外部 Skill 示例）

对列表数据或文本行进行去重操作。
放置于 xiaohua/skills/ 目录下，Agent 启动时自动加载。
"""

from typing import Any, Dict, List

from configbot.skills.base import BaseSkill, SkillCategory, SkillExecResult


class DataDeduplicatorSkill(BaseSkill):
    """数据去重 Skill

    对文本行或数据列表进行去重，支持保留顺序和忽略大小写。
    """
    name = "data_deduplicator"
    description = "对文本行或数据列表进行去重操作"
    category = SkillCategory.DATA
    version = "1.0.0"
    requires_tools = set()

    async def execute(
        self,
        context: Dict[str, Any],
        tool_executor: Any,
        mcp_executor: Any,
    ) -> SkillExecResult:
        items = context.get("items", [])
        mode = context.get("mode", "set")  # set | preserve_order
        ignore_case = context.get("ignore_case", False)
        strip = context.get("strip", True)

        if not items:
            return SkillExecResult(success=False, error="缺少参数: items")

        steps = []

        # 预处理
        original = list(items)
        processed = original

        if strip and isinstance(original[0], str):
            processed = [s.strip() for s in original]

        if ignore_case and isinstance(processed[0], str):
            processed = [s.lower() for s in processed]

        steps.append({"step": "preprocess", "status": "ok", "original_count": len(original)})

        # 去重
        if mode == "preserve_order":
            seen = set()
            unique = []
            indices = []
            for i, item in enumerate(processed):
                if item not in seen:
                    seen.add(item)
                    unique.append(original[i])
                    indices.append(i)
        else:
            seen = {}
            unique = []
            indices = []
            for i, item in enumerate(processed):
                if item not in seen:
                    seen[item] = i
                    unique.append(original[i])
                    indices.append(i)

        duplicates = len(original) - len(unique)
        steps.append({"step": "deduplicate", "status": "ok", "removed": duplicates})

        return SkillExecResult(
            success=True,
            data={
                "original_count": len(original),
                "unique_count": len(unique),
                "duplicates_removed": duplicates,
                "unique_items": unique,
                "duplicate_indices": [
                    i for i in range(len(original)) if i not in set(indices)
                ],
            },
            steps=steps,
            metadata={"mode": mode, "ignore_case": ignore_case},
        )