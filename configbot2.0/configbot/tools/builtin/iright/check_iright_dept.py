from typing import Any, Dict
from ...base import BaseTool, ToolExecResult

def iright_and_dept_check(iright: str, dept: str) -> bool:
    """检查群组是否包含指定部门的成员
    Args:
        iright (str): 群组名称
        dept (str): 部门名称
    Returns:
        bool: 如果包含则返回 True，否则返回 False
    """
    result = iright + dept
    return result

class IrightTool(BaseTool):
    name = "查询群组成员部门"
    description = "查询群组的成员部门不是指定部门的成员信息"

    def _get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "iright": {"type": "string", "description": "要查询的群组名称"},
                "dept": {"type": "string", "description": "要校验的部门名称"},
            },
            "required": ["iright", "dept"],
        }

    async def execute(self, iright: str, dept: str) -> ToolExecResult:
          try:
              result = iright_and_dept_check(iright, dept)
              return ToolExecResult(success=True, data=result)
          except Exception as e:
              return ToolExecResult(success=False, error=str(e))
