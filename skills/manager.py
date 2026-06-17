"""Skill 生命周期管理器

提供 Skill 的自动创建、更新进化、卸载等自我管理能力。

三大核心能力：
1. create_skill:  通过描述自动生成 Skill 文件并安装
2. update_skill:  根据用户反馈自动优化 Skill 并重新加载
3. uninstall_skill: 卸载指定 Skill（删除文件 + 注销注册）
"""

import importlib
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import BaseSkill, SkillCategory
from ..xiaohua.skills import load_skill_from_file

# ── Skill 代码模板 ──

SKILL_TEMPLATE = '''"""{{description}}

自动生成的 Skill 文件。
创建时间: {{created_at}}
版本: {{version}}
分类: {{category}}
"""

from typing import Any, Dict

from configbot.skills.base import BaseSkill, SkillCategory, SkillExecResult


class {{class_name}}(BaseSkill):
    """{{description}}"""

    name = "{{name}}"
    description = "{{description}}"
    category = SkillCategory.{{category_enum}}
    version = "{{version}}"
    requires_tools = {{requires_tools}}

    async def execute(
        self,
        context: Dict[str, Any],
        tool_executor: Any,
        mcp_executor: Any,
    ) -> SkillExecResult:
        """{{description}}

        Args:
            context: 上下文数据，包含 {{context_keys}}
            tool_executor: 内置工具执行器
            mcp_executor: MCP 工具执行器
        """
        steps = []

{{execute_body}}

        return SkillExecResult(
            success=True,
            data={"result": "{{name}} 执行完成", "steps": steps},
            steps=steps,
        )
'''


def _snake_to_camel(name: str) -> str:
    """snake_case → CamelCase"""
    return "".join(w.capitalize() for w in name.split("_"))


def _camel_to_snake(name: str) -> str:
    """CamelCase → snake_case"""
    result = []
    for c in name:
        if c.isupper() and result:
            result.append("_")
        result.append(c.lower())
    return "".join(result)


class SkillManager:
    """Skill 生命周期管理器

    负责 Skill 的创建、更新、卸载全生命周期管理。

    使用方式:
        manager = SkillManager(skills_dir, skill_registry, reload_callback)
        manager.create_skill(name="my_skill", description="...", ...)
        manager.update_skill(name="my_skill", new_operations="...")
        manager.uninstall_skill(name="my_skill")
    """

    def __init__(self, skills_dir: str, registry, reload_callback=None):
        """
        Args:
            skills_dir: 外部 Skill 文件存放目录
            registry: SkillRegistry 实例
            reload_callback: 重载回调 callable()，用于通知 Agent 重新加载
        """
        self._skills_dir = Path(skills_dir)
        self._registry = registry
        self._reload_callback = reload_callback
        self._skills_dir.mkdir(parents=True, exist_ok=True)

    # ── 公共 API ──

    def create_skill(
        self,
        name: str,
        description: str,
        category: str = "custom",
        operations: str = "",
        requires_tools: Optional[List[str]] = None,
        context_keys: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """根据描述自动生成 Skill 文件并安装

        Args:
            name: Skill 名称（snake_case）
            description: Skill 功能描述
            category: 分类（code/security/data/deploy/custom）
            operations: 操作描述，用于生成 execute 方法体
            requires_tools: 依赖的工具列表
            context_keys: 需要的上下文参数

        Returns:
            {"success": bool, "skill_name": str, "file_path": str, "message": str}
        """
        # 检查名称是否已存在
        existing = self._registry.get(name)
        if existing:
            return {
                "success": False,
                "skill_name": name,
                "error": f"Skill '{name}' 已存在，请使用 update 更新",
            }

        # 校验分类
        valid_categories = {c.value for c in SkillCategory}
        if category not in valid_categories:
            category = "custom"

        # 生成代码
        code = self._generate_skill_code(
            name=name,
            description=description,
            category=category,
            operations=operations,
            requires_tools=requires_tools or [],
            context_keys=context_keys or [],
        )

        # 写入文件
        file_path = self._skills_dir / f"{name}.py"
        file_path.write_text(code, encoding="utf-8")

        # 重载
        reload_result = self._reload()
        loaded = name in reload_result.get("added", []) or name in self._registry

        return {
            "success": loaded,
            "skill_name": name,
            "file_path": str(file_path),
            "message": f"Skill '{name}' 已创建并加载" if loaded else f"Skill 文件已创建但加载失败",
            "reload": reload_result,
        }

    def update_skill(
        self,
        name: str,
        new_operations: Optional[str] = None,
        new_description: Optional[str] = None,
        new_category: Optional[str] = None,
        new_requires_tools: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """更新现有 Skill 并重新加载（Skill 进化）

        自动递增版本号（如 1.0.0 → 1.1.0）。

        Args:
            name: 要更新的 Skill 名称
            new_operations: 新的操作描述
            new_description: 新的功能描述
            new_category: 新的分类
            new_requires_tools: 新的依赖工具列表

        Returns:
            {"success": bool, "skill_name": str, "old_version": str, "new_version": str, ...}
        """
        skill = self._registry.get(name)
        if not skill:
            return {
                "success": False,
                "skill_name": name,
                "error": f"Skill '{name}' 不存在，请先创建",
            }

        old_version = skill.version
        new_version = self._bump_version(old_version)
        description = new_description or skill.description
        category = new_category or skill.category.value
        requires_tools = new_requires_tools or list(skill.requires_tools)

        # 备份旧文件
        file_path = self._skills_dir / f"{name}.py"
        if file_path.exists():
            backup_path = self._skills_dir / f"{name}.py.{old_version}.bak"
            file_path.rename(backup_path)

        # 生成新代码
        code = self._generate_skill_code(
            name=name,
            description=description,
            category=category,
            operations=new_operations or "",
            requires_tools=requires_tools,
            version=new_version,
        )

        file_path.write_text(code, encoding="utf-8")

        # 先注销旧版本，再重载
        self._registry.unregister(name)
        self._reload()

        return {
            "success": True,
            "skill_name": name,
            "old_version": old_version,
            "new_version": new_version,
            "file_path": str(file_path),
            "message": f"Skill '{name}' 已从 {old_version} 进化到 {new_version}",
        }

    def uninstall_skill(self, name: str) -> Dict[str, Any]:
        """卸载指定 Skill

        1. 从注册中心注销
        2. 删除对应的 .py 文件
        3. 删除备份文件

        Args:
            name: 要卸载的 Skill 名称

        Returns:
            {"success": bool, "skill_name": str, "message": str}
        """
        skill = self._registry.get(name)
        if not skill:
            return {
                "success": False,
                "skill_name": name,
                "error": f"Skill '{name}' 不存在",
            }

        # 从注册中心注销
        self._registry.unregister(name)

        # 删除文件
        deleted_files = []
        file_path = self._skills_dir / f"{name}.py"
        if file_path.exists():
            file_path.unlink()
            deleted_files.append(str(file_path))

        # 删除备份文件
        for bak in self._skills_dir.glob(f"{name}.py.*.bak"):
            bak.unlink()
            deleted_files.append(str(bak))

        return {
            "success": True,
            "skill_name": name,
            "message": f"Skill '{name}' 已卸载",
            "deleted_files": deleted_files,
        }

    def list_installable_skills(self) -> List[Dict[str, Any]]:
        """列出所有已安装的 Skill 及其文件路径"""
        result = []
        for skill in self._registry.list_all():
            file_path = self._skills_dir / f"{skill.name}.py"
            result.append({
                "name": skill.name,
                "description": skill.description,
                "category": skill.category.value,
                "version": skill.version,
                "file_path": str(file_path),
                "is_file": file_path.exists(),
            })
        return result

    def get_skill_source(self, name: str) -> Optional[str]:
        """获取 Skill 的源码"""
        file_path = self._skills_dir / f"{name}.py"
        if file_path.exists():
            return file_path.read_text(encoding="utf-8")
        return None

    # ── 内部方法 ──

    def _generate_skill_code(
        self,
        name: str,
        description: str,
        category: str,
        operations: str = "",
        requires_tools: Optional[List[str]] = None,
        context_keys: Optional[List[str]] = None,
        version: str = "1.0.0",
    ) -> str:
        """根据模板生成 Skill 代码"""
        from datetime import datetime

        class_name = _snake_to_camel(name) + "Skill"
        category_enum = category.upper()
        requires_tools_repr = repr(set(requires_tools or []))
        context_keys_str = ", ".join(context_keys) if context_keys else "根据操作需要传入"

        # 生成 execute 方法体
        if operations:
            execute_body = self._generate_execute_body(
                name, operations, requires_tools or [], context_keys or []
            )
        else:
            execute_body = f'        # TODO: 实现 "{description}" 的具体逻辑\n        pass'

        return (
            SKILL_TEMPLATE.replace("{{name}}", name)
            .replace("{{class_name}}", class_name)
            .replace("{{description}}", description)
            .replace("{{category}}", category)
            .replace("{{category_enum}}", category_enum)
            .replace("{{version}}", version)
            .replace("{{requires_tools}}", requires_tools_repr)
            .replace("{{context_keys}}", context_keys_str)
            .replace("{{execute_body}}", execute_body)
            .replace("{{created_at}}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )

    def _generate_execute_body(
        self,
        name: str,
        operations: str,
        requires_tools: List[str],
        context_keys: List[str],
    ) -> str:
        """根据操作描述生成 execute 方法体"""
        lines = []

        # 参数提取
        for key in context_keys:
            lines.append(f'        {key} = context.get("{key}", "")')
            lines.append(f'        if not {key}:')
            lines.append(
                f'            return SkillExecResult(success=False, error="缺少参数: {key}")'
            )
            lines.append("")

        if context_keys:
            lines.append("")

        # 操作注释
        lines.append(f"        # {operations}")
        lines.append("")

        # 工具调用（如果依赖了工具）
        for tool in requires_tools:
            lines.append(f'        # 调用工具: {tool}')
            # 传递上下文参数给工具
            if context_keys:
                args = ", ".join(f"{k}={k}" for k in context_keys)
                lines.append(f'        result = await tool_executor("{tool}", {args})')
            else:
                lines.append(f'        result = await tool_executor("{tool}")')
            lines.append(
                '        steps.append({"step": "' + tool + '", "status": "ok" if result.success else "fail"})'
            )
            lines.append("        if not result.success:")
            lines.append(
                f'            return SkillExecResult(success=False, error=result.error, steps=steps)'
            )
            lines.append("")

        # 如果没有具体操作，生成占位
        if not requires_tools and not context_keys:
            lines.append(
                f'        # 请在下方实现 "{name}" 的具体业务逻辑'
            )
            lines.append("        pass")
            lines.append("")

        return "\n".join(lines)

    def _bump_version(self, version: str) -> str:
        """递增版本号: 1.0.0 → 1.1.0"""
        try:
            parts = version.split(".")
            parts[1] = str(int(parts[1]) + 1)
            return ".".join(parts)
        except (IndexError, ValueError):
            return "1.1.0"

    def _reload(self) -> Dict[str, Any]:
        """触发重载并返回结果"""
        if self._reload_callback:
            return self._reload_callback()
        return {"added": [], "total": len(self._registry)}