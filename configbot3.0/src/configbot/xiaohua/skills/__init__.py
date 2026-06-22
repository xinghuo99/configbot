"""外部 Skill 加载器

从 xiaohua/skills/ 目录加载外部 Skill 模块。
每个 Skill 文件是一个独立的 Python 模块，包含一个继承 BaseSkill 的类。
"""

import importlib.util
import sys
from pathlib import Path
from typing import List, Optional

from configbot.skills.base import BaseSkill


def load_skill_from_file(file_path: str) -> Optional[BaseSkill]:
    """从单个 .py 文件加载 Skill

    Skill 文件要求：
    - 必须包含一个继承 BaseSkill 的类
    - 类名命名规则：XxxSkill
    """
    path = Path(file_path)
    if not path.exists() or path.suffix != ".py":
        return None

    module_name = f"xiaohua_skill_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if (
            isinstance(attr, type)
            and issubclass(attr, BaseSkill)
            and attr is not BaseSkill
        ):
            return attr()
    return None


def load_skills_from_dir(dir_path: str) -> List[BaseSkill]:
    """从目录批量加载 Skill"""
    path = Path(dir_path)
    if not path.is_dir():
        return []

    skills = []
    for py_file in sorted(path.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        skill = load_skill_from_file(str(py_file))
        if skill:
            skills.append(skill)

    return skills