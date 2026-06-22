"""Skill 注册中心

管理所有 Skill 的注册、查找和生命周期。
"""

from typing import Dict, List, Optional, Set

from .base import BaseSkill, SkillCategory


class SkillRegistry:
    """Skill 注册表

    使用方式：
        registry = SkillRegistry()
        registry.register(CodeReviewSkill())
        skill = registry.get("code_review")
        skills = registry.find_by_category(SkillCategory.CODE)
    """

    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        """注册一个 Skill"""
        if not skill.name:
            raise ValueError(f"Skill {skill} 必须定义 name 属性")
        if skill.name in self._skills:
            raise ValueError(f"Skill 名称冲突: {skill.name}")
        self._skills[skill.name] = skill

    def unregister(self, name: str) -> bool:
        """移除一个 Skill"""
        if name in self._skills:
            del self._skills[name]
            return True
        return False

    def get(self, name: str) -> Optional[BaseSkill]:
        """按名称获取 Skill"""
        return self._skills.get(name)

    def list_all(self) -> List[BaseSkill]:
        """列出所有已注册 Skill"""
        return list(self._skills.values())

    def get_all_info(self) -> List[dict]:
        """获取所有 Skill 的元信息"""
        return [skill.get_info() for skill in self._skills.values()]

    def find_by_category(self, category: SkillCategory) -> List[BaseSkill]:
        """按分类查找 Skill"""
        return [s for s in self._skills.values() if s.category == category]

    def find_by_keyword(self, keyword: str) -> List[BaseSkill]:
        """按关键词搜索 Skill"""
        keyword_lower = keyword.lower()
        return [
            s
            for s in self._skills.values()
            if keyword_lower in s.name.lower()
            or keyword_lower in s.description.lower()
        ]

    def check_requirements(
        self, name: str, available_tools: Set[str]
    ) -> Optional[List[str]]:
        """检查 Skill 的前置依赖是否满足，返回缺失的工具列表"""
        skill = self.get(name)
        if not skill:
            return None
        missing = skill.requires_tools - available_tools
        return list(missing) if missing else []

    def list_categories(self) -> List[SkillCategory]:
        """列出已有 Skill 涉及的所有分类"""
        return list({s.category for s in self._skills.values()})

    def __len__(self) -> int:
        return len(self._skills)

    def __bool__(self) -> bool:
        return True

    def __contains__(self, name: str) -> bool:
        return name in self._skills