"""ConfigBot 入口

基于自然语言的多轮对话 Agent，支持：
- 自然语言输入 → Agent 自主选择工具/Skill/MCP
- LLM 驱动的智能路由（阿里 DashScope 视觉模型）
- 多轮对话上下文管理
- 交互式 REPL 和单次调用两种模式

使用方式:
    python main.py              # 交互式聊天模式
    python main.py --query "..." # 单次查询模式
    python main.py --demo       # 运行旧版 Demo
    python main.py --no-llm     # 不使用 LLM（纯关键词匹配）
"""

import asyncio
import json
import os
import sys
from typing import Any, Dict, Optional

from configbot.agent import Agent
from configbot.tools import BaseTool, ToolExecResult
from configbot.mcp import MCPServer, MCPResponse, MCPTool
from configbot.skills import BaseSkill, SkillCategory, SkillExecResult
from configbot.llm import LLMClient, create_llm_client
from configbot.logger import log_info


# ═══════════════════════════════════════════════════════════════
# 扩展示例：自定义工具
# ═══════════════════════════════════════════════════════════════

class EchoTool(BaseTool):
    """自定义工具示例：回显消息"""
    name = "echo"
    description = "回显用户输入的文本"

    def _get_parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "要回显的消息"},
            },
            "required": ["message"],
        }

    async def execute(self, **kwargs) -> ToolExecResult:
        message = kwargs.get("message", "")
        return ToolExecResult(success=True, data=f"[Echo] {message}")


class CalculatorTool(BaseTool):
    """自定义工具示例：简单计算器"""
    name = "calculator"
    description = "执行基本数学运算"

    def _get_parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "数学表达式，如 '2 + 3 * 4'",
                },
            },
            "required": ["expression"],
        }

    async def execute(self, **kwargs) -> ToolExecResult:
        expression = kwargs.get("expression", "")
        try:
            # 注意：生产环境不要使用 eval，这里仅作演示
            allowed = set("0123456789+-*/(). ")
            if not all(c in allowed for c in expression):
                return ToolExecResult(
                    success=False, error="表达式包含不允许的字符"
                )
            result = eval(expression)
            return ToolExecResult(success=True, data=result)
        except Exception as e:
            return ToolExecResult(success=False, error=str(e))


# ═══════════════════════════════════════════════════════════════
# 扩展示例：自定义 MCP Server
# ═══════════════════════════════════════════════════════════════

class WeatherMCPServer(MCPServer):
    """自定义 MCP Server 示例：天气查询"""
    name = "weather"
    description = "天气查询 MCP 服务"
    version = "1.0.0"

    def get_tools(self):
        return [
            MCPTool(
                name="get_weather",
                description="查询指定城市的天气",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "城市名称"},
                    },
                    "required": ["city"],
                },
            ),
            MCPTool(
                name="get_forecast",
                description="查询指定城市的天气预报",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "城市名称"},
                        "days": {
                            "type": "integer",
                            "description": "预报天数",
                            "default": 3,
                        },
                    },
                    "required": ["city"],
                },
            ),
        ]

    async def call_tool(self, tool_name: str, **kwargs) -> MCPResponse:
        if tool_name == "get_weather":
            city = kwargs.get("city", "未知")
            return MCPResponse(
                success=True,
                data={
                    "city": city,
                    "temperature": "22°C",
                    "humidity": "65%",
                    "condition": "晴",
                },
            )
        elif tool_name == "get_forecast":
            city = kwargs.get("city", "未知")
            days = kwargs.get("days", 3)
            return MCPResponse(
                success=True,
                data={
                    "city": city,
                    "forecast": [
                        {"day": f"第{i+1}天", "temp": f"{20+i}°C", "condition": "晴"}
                        for i in range(days)
                    ],
                },
            )
        return MCPResponse(success=False, error=f"未知工具: {tool_name}")


# ═══════════════════════════════════════════════════════════════
# 扩展示例：自定义 Skill
# ═══════════════════════════════════════════════════════════════

class CodeStatsSkill(BaseSkill):
    """自定义 Skill 示例：代码统计"""
    name = "code_stats"
    description = "统计代码文件的基本信息（行数、注释率等）"
    category = SkillCategory.CODE
    version = "1.0.0"
    requires_tools = {"read_file"}

    async def execute(
        self, context: Dict[str, Any], tool_executor: Any, mcp_executor: Any
    ) -> SkillExecResult:
        file_path = context.get("file_path")
        if not file_path:
            return SkillExecResult(success=False, error="缺少参数: file_path")

        result = await tool_executor("read_file", file_path=file_path)
        if not result.success:
            return SkillExecResult(success=False, error=result.error)

        code = result.data
        lines = code.split("\n")
        total = len(lines)
        blank = sum(1 for l in lines if not l.strip())
        comment = sum(
            1 for l in lines if l.strip().startswith("#") or l.strip().startswith("//")
        )
        code_lines = total - blank - comment

        stats = {
            "file": file_path,
            "total_lines": total,
            "code_lines": code_lines,
            "blank_lines": blank,
            "comment_lines": comment,
            "comment_ratio": f"{comment / total * 100:.1f}%" if total > 0 else "0%",
        }
        return SkillExecResult(success=True, data=stats)


# ═══════════════════════════════════════════════════════════════
# 统一聊天入口
# ═══════════════════════════════════════════════════════════════

async def chat_main(llm_client: Optional[LLMClient] = None):
    """统一的聊天入口：交互式 REPL 模式

    所有用户输入在最外层（此处）通过 stdin 收集，统一传入 session.run_repl()。
    """
    from configbot.chat import ChatSession

    agent = Agent()
    # 注册自定义扩展
    agent.register_tool(EchoTool())
    agent.register_tool(CalculatorTool())
    agent.register_mcp_server(WeatherMCPServer())
    agent.register_skill(CodeStatsSkill())

    session = ChatSession(agent, llm_client=llm_client)

    # 最外层收集所有用户输入
    user_inputs: list[str] = []
    log_info("请输入对话内容（每行一条，输入 exit 结束，输入空行提交）：")
    while True:
        try:
            line = input("> ")
        except (EOFError, KeyboardInterrupt):
            break
        if line.strip().lower() in ("exit", "quit", "退出", "q"):
            line = line.strip()
            user_inputs.append(line)
            break
        user_inputs.append(line)

    await session.run_repl(user_inputs)


async def chat_once(query: str, llm_client: Optional[LLMClient] = None):
    """单次查询模式"""
    from configbot.chat import ChatSession

    agent = Agent()
    agent.register_tool(EchoTool())
    agent.register_tool(CalculatorTool())
    agent.register_mcp_server(WeatherMCPServer())
    agent.register_skill(CodeStatsSkill())

    session = ChatSession(agent, llm_client=llm_client)
    response = await session.chat(query)
    log_info(response)


def _create_llm_client() -> Optional[LLMClient]:
    """创建 LLM 客户端（阿里 DashScope 视觉模型）

    需要设置环境变量 DASHSCOPE_API_KEY，或通过参数传入。
    如果未配置 API Key，返回 None（使用关键词匹配模式）。
    """
    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        log_info("[提示] 未设置 DASHSCOPE_API_KEY 环境变量，使用关键词匹配模式", level="warning")
        log_info("  设置方式: set DASHSCOPE_API_KEY=your-key  (Windows)")
        log_info("  获取 Key: https://dashscope.console.aliyun.com/apiKey")
        return None

    try:
        client = create_llm_client(api_key=api_key)
        log_info(f"[LLM] 已连接阿里 DashScope, 模型: {client.model}")
        return client
    except Exception as e:
        log_info(f"[警告] LLM 初始化失败: {e}，使用关键词匹配模式", level="warning")
        return None


async def main():
    """主入口"""
    args = sys.argv[1:]

    if "--demo" in args:
        # 旧版 Demo 模式（兼容）
        await _run_demos()
        return

    # 解析 --no-llm 参数
    use_llm = "--no-llm" not in args

    # 创建 LLM 客户端
    llm_client = None
    if use_llm:
        llm_client = _create_llm_client()

    if "--query" in args:
        # 单次查询模式
        idx = args.index("--query")
        if idx + 1 < len(args):
            query = args[idx + 1]
        else:
            log_info("用法: python main.py --query \"你的问题\"", level="warning")
            return
        await chat_once(query, llm_client=llm_client)
        return

    # 默认：交互式聊天模式
    await chat_main(llm_client=llm_client)


async def _run_demos():
    """运行旧版 Demo（兼容保留）"""
    '''
    await demo_basic()
    await demo_tool_call()
    await demo_mcp_call()
    await demo_skill()
    await demo_intent_routing()
    await demo_new_tools()
    await demo_external_skills()
    await demo_skill_lifecycle()
    '''
    log_info("\n" + "=" * 60)
    log_info("所有 Demo 执行完毕！")
    log_info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())