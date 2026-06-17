"""Skill 机制基类

Skill 是更高层次的抽象，代表一个完整的任务能力单元。
每个 Skill 可以组合调用多个内置工具和 MCP 工具来完成复杂任务。

与 Tool 的区别：
- Tool: 原子操作（读文件、搜索等）
- Skill: 复合任务（代码审查、安全扫描等），内部调用多个 Tool

扩展方式：
    继承 BaseSkill，实现 execute 和 _get_required_tools 方法。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class SkillCategory(Enum):
    """Skill 分类"""
    CODE = "code"
    SECURITY = "security"
    DATA = "data"
    DEPLOY = "deploy"
    CUSTOM = "custom"


@dataclass
class SkillExecResult:
    """Skill 执行结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    steps: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseSkill(ABC):
    """Skill 抽象基类

    属性：
        name: Skill 唯一名称
        description: Skill 功能描述
        category: Skill 分类
        version: 版本号
        requires_tools: 依赖的工具名称集合
    """

    name: str = ""
    description: str = ""
    category: SkillCategory = SkillCategory.CUSTOM
    version: str = "0.1.0"
    requires_tools: Set[str] = set()

    def get_info(self) -> Dict[str, Any]:
        """返回 Skill 元信息"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "version": self.version,
            "requires_tools": list(self.requires_tools),
        }

    @abstractmethod
    async def execute(
        self,
        context: Dict[str, Any],
        tool_executor: Any,
        mcp_executor: Any,
    ) -> SkillExecResult:
        """执行 Skill 逻辑

        Args:
            context: 上下文数据（用户输入、文件路径等）
            tool_executor: 内置工具执行器 callable(tool_name, **kwargs)
            mcp_executor: MCP 工具执行器 callable(server_name, tool_name, **kwargs)

        Returns:
            SkillExecResult: 执行结果
        """
        ...

    def pre_check(self, available_tools: Set[str]) -> bool:
        """前置检查：所需工具是否可用"""
        return self.requires_tools.issubset(available_tools)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name!r})>"