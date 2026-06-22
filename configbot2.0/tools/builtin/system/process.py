"""系统进程和环境变量工具"""

import os
import subprocess
from typing import Any, Dict

from ...base import BaseTool, ToolExecResult


class RunCommandTool(BaseTool):
    """执行系统命令"""
    name = "run_command"
    description = "执行系统命令并返回输出（超时 30 秒）"

    def _get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的命令"},
                "cwd": {"type": "string", "description": "工作目录"},
            },
            "required": ["command"],
        }

    async def execute(self, command: str, cwd: str = None) -> ToolExecResult:
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=cwd,
            )
            return ToolExecResult(
                success=result.returncode == 0,
                data=result.stdout or result.stderr,
                metadata={
                    "returncode": result.returncode,
                    "command": command,
                },
            )
        except subprocess.TimeoutExpired:
            return ToolExecResult(success=False, error="命令执行超时（30秒）")
        except Exception as e:
            return ToolExecResult(success=False, error=str(e))


class GetEnvTool(BaseTool):
    """获取环境变量"""
    name = "get_env"
    description = "获取系统环境变量"

    def _get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "环境变量名，不传则返回所有"},
            },
            "required": [],
        }

    async def execute(self, key: str = None) -> ToolExecResult:
        if key:
            value = os.environ.get(key)
            if value is None:
                return ToolExecResult(success=False, error=f"环境变量不存在: {key}")
            return ToolExecResult(success=True, data={key: value})
        else:
            return ToolExecResult(
                success=True,
                data=dict(os.environ),
                metadata={"count": len(os.environ)},
            )