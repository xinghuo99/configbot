"""内置工具基类

所有内置工具必须继承 BaseTool 并实现 execute 方法。
可通过 ToolRegistry 注册和发现新工具。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ToolExecResult:
    """工具执行结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseTool(ABC):
    """内置工具抽象基类

    扩展方式：继承此类并实现 execute 方法，然后注册到 ToolRegistry。
    """

    # 子类必须定义的属性
    name: str = ""
    description: str = ""

    def get_schema(self) -> Dict[str, Any]:
        """返回工具的 JSON Schema 描述，供 LLM 使用"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self._get_parameters_schema(),
        }

    def _get_parameters_schema(self) -> Dict[str, Any]:
        """子类可重写以提供参数 schema"""
        return {"type": "object", "properties": {}, "required": []}

    @abstractmethod
    async def execute(self, **kwargs) -> ToolExecResult:
        """执行工具逻辑，子类必须实现"""
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name!r})>"