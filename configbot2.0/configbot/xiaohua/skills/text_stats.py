"""文本统计 Skill（外部 Skill 示例）

分析文本内容，统计字符数、词数、行数等指标。
放置于 xiaohua/skills/ 目录下，Agent 启动时自动加载。
"""

import re
from collections import Counter
from typing import Any, Dict

from configbot.skills.base import BaseSkill, SkillCategory, SkillExecResult


class TextStatsSkill(BaseSkill):
    """文本统计 Skill

    分析文本的各种统计指标：字符数、词数、行数、
    高频词、中英文检测等。
    """
    name = "text_stats"
    description = "分析文本统计指标：字符数、词数、行数、高频词等"
    category = SkillCategory.DATA
    version = "1.0.0"
    requires_tools = set()

    # 中文字符范围
    _CHINESE_PATTERN = re.compile(r"[\u4e00-\u9fff]")
    _WORD_PATTERN = re.compile(r"[\u4e00-\u9fff]|[a-zA-Z]+")

    async def execute(
        self,
        context: Dict[str, Any],
        tool_executor: Any,
        mcp_executor: Any,
    ) -> SkillExecResult:
        text = context.get("text", "")
        top_n = context.get("top_n", 10)

        if not text:
            return SkillExecResult(success=False, error="缺少参数: text")

        steps = []

        # 基本统计
        lines = text.split("\n")
        chars_total = len(text)
        chars_no_space = len(text.replace(" ", "").replace("\n", "").replace("\t", ""))
        chinese_chars = len(self._CHINESE_PATTERN.findall(text))

        # 单词统计
        words = self._WORD_PATTERN.findall(text)
        word_count = len(words)
        word_freq = Counter(words).most_common(top_n)

        steps.append({"step": "analyze", "status": "ok"})

        # 语言检测
        if chinese_chars > chars_no_space * 0.3:
            language = "中文为主"
        elif chinese_chars > 0:
            language = "中英混合"
        else:
            language = "英文为主"

        stats = {
            "chars_total": chars_total,
            "chars_no_space": chars_no_space,
            "chinese_chars": chinese_chars,
            "lines": len(lines),
            "non_empty_lines": sum(1 for l in lines if l.strip()),
            "words": word_count,
            "unique_words": len(set(words)),
            "language": language,
            "top_words": [{"word": w, "count": c} for w, c in word_freq],
        }

        return SkillExecResult(
            success=True,
            data=stats,
            steps=steps,
            metadata={"text_length": len(text)},
        )