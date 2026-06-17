"""文件备份 Skill（外部 Skill 示例）

为目标文件创建带时间戳的备份副本。
放置于 xiaohua/skills/ 目录下，Agent 启动时自动加载。
"""

import os
from datetime import datetime
from typing import Any, Dict

from configbot.skills.base import BaseSkill, SkillCategory, SkillExecResult


class FileBackupSkill(BaseSkill):
    """文件备份 Skill

    为指定文件创建带时间戳的备份副本，支持自定义备份目录。
    """
    name = "file_backup"
    description = "为指定文件创建带时间戳的备份副本"
    category = SkillCategory.CUSTOM
    version = "1.0.0"
    requires_tools = {"read_file", "write_file"}

    async def execute(
        self,
        context: Dict[str, Any],
        tool_executor: Any,
        mcp_executor: Any,
    ) -> SkillExecResult:
        file_path = context.get("file_path", "")
        backup_dir = context.get("backup_dir", "")
        keep_ext = context.get("keep_ext", True)

        if not file_path:
            return SkillExecResult(success=False, error="缺少参数: file_path")

        steps = []

        # 读取源文件
        result = await tool_executor("read_file", file_path=file_path)
        if not result.success:
            return SkillExecResult(
                success=False,
                error=f"读取源文件失败: {result.error}",
                steps=[{"step": "read", "status": "fail"}],
            )
        steps.append({"step": "read", "status": "ok"})

        # 生成备份文件名
        filename = os.path.basename(file_path)
        name, ext = os.path.splitext(filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if keep_ext:
            backup_name = f"{name}.{timestamp}{ext}"
        else:
            backup_name = f"{filename}.{timestamp}.bak"

        if backup_dir:
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, backup_name)
        else:
            backup_path = os.path.join(os.path.dirname(file_path), backup_name)

        # 写入备份
        result = await tool_executor("write_file", file_path=backup_path, content=result.data)
        if not result.success:
            return SkillExecResult(
                success=False,
                error=f"写入备份失败: {result.error}",
                steps=[*steps, {"step": "write", "status": "fail"}],
            )

        steps.append({"step": "write", "status": "ok", "backup_path": backup_path})

        return SkillExecResult(
            success=True,
            data={
                "source": file_path,
                "backup": backup_path,
                "backup_name": backup_name,
                "timestamp": timestamp,
            },
            steps=steps,
            metadata={"file_path": file_path},
        )