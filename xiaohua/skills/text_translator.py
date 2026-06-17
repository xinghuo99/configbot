"""文本翻译 Skill（外部 Skill 示例）

将文本翻译为指定语言（模拟实现）。
放置于 xiaohua/skills/ 目录下，通过 load_skill_from_file 动态加载。
"""

from typing import Any, Dict

from configbot.skills.base import BaseSkill, SkillCategory, SkillExecResult


class TextTranslatorSkill(BaseSkill):
    """文本翻译 Skill

    模拟翻译功能，实际使用时对接翻译 API（如 DeepL、Google Translate）。
    """
    name = "text_translator"
    description = "将文本翻译为指定语言（模拟实现）"
    category = SkillCategory.CUSTOM
    version = "1.0.0"
    requires_tools = set()

    # 模拟翻译词表
    _MOCK_DICT = {
        "hello": "你好",
        "world": "世界",
        "error": "错误",
        "success": "成功",
        "file": "文件",
        "not found": "未找到",
        "code": "代码",
        "review": "审查",
        "security": "安全",
        "config": "配置",
    }

    async def execute(
        self,
        context: Dict[str, Any],
        tool_executor: Any,
        mcp_executor: Any,
    ) -> SkillExecResult:
        text = context.get("text", "")
        target_lang = context.get("target_lang", "zh")
        source_lang = context.get("source_lang", "auto")

        if not text:
            return SkillExecResult(success=False, error="缺少参数: text")

        steps = []
        translated = self._mock_translate(text, target_lang)

        steps.append({"step": "translate", "status": "ok"})

        return SkillExecResult(
            success=True,
            data={
                "original": text,
                "translated": translated,
                "source_lang": source_lang,
                "target_lang": target_lang,
                "note": "此为模拟翻译，实际使用请对接翻译 API",
            },
            steps=steps,
            metadata={"text_length": len(text)},
        )

    def _mock_translate(self, text: str, target_lang: str) -> str:
        """模拟翻译"""
        if target_lang == "en":
            return text  # 已经是英文
        result = text.lower()
        for en, zh in self._MOCK_DICT.items():
            result = result.replace(en, zh)
        return result