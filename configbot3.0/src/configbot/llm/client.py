"""LLM 客户端模块

对接阿里 DashScope 视觉模型（OpenAI 兼容接口），为 Agent 提供 AI 推理能力。
支持：
- 多模态视觉模型（qwen-vl-max / qwen-vl-plus）
- 纯文本模型（qwen-max / qwen-plus）
- 工具调用（Function Calling）
- 自动意图路由
"""

import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional

import openai  # pyright: ignore[reportMissingImports]

logger = logging.getLogger(__name__)

# ── 阿里 DashScope 配置 ──

DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 模型列表
QWEN_VL_MAX = "qwen-vl-max"         # 多模态视觉模型（最强）
QWEN_VL_PLUS = "qwen-vl-plus"       # 多模态视觉模型（均衡）
QWEN_MAX = "qwen-max"               # 纯文本模型（最强）
QWEN_PLUS = "qwen-plus"             # 纯文本模型（均衡）


class LLMClient:
    """LLM 客户端 - 对接阿里 DashScope（OpenAI 兼容接口）

    使用示例:
        client = LLMClient(model="qwen-vl-max")
        response = await client.chat([{"role": "user", "content": "你好"}])

        # 创建 Agent 回调
        agent.set_llm(client.create_agent_callback())
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = QWEN_VL_MAX,
        base_url: str = DASHSCOPE_BASE_URL,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        """初始化 LLM 客户端

        Args:
            api_key: DashScope API Key，默认从环境变量 DASHSCOPE_API_KEY 读取
            model: 模型名称，默认 qwen-vl-max
            base_url: API 地址，默认阿里 DashScope 兼容接口
            temperature: 生成温度
            max_tokens: 最大输出 token 数
        """
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY", "")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        self.client = openai.AsyncOpenAI(
            api_key=self.api_key,
            base_url=base_url,
        )

    # ── 核心聊天接口 ──

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> openai.types.chat.ChatCompletion:
        """发送聊天请求到 LLM

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            tools: 工具定义列表（Function Calling）
            temperature: 温度参数
            max_tokens: 最大输出 token

        Returns:
            ChatCompletion 响应对象
        """
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        logger.debug("LLM 请求: model=%s, messages=%d, tools=%d",
                     self.model, len(messages), len(tools or []))

        response = await self.client.chat.completions.create(**kwargs)

        logger.debug("LLM 响应: finish_reason=%s, usage=%s",
                     response.choices[0].finish_reason if response.choices else "N/A",
                     response.usage)

        return response

    async def chat_simple(self, user_message: str, system_prompt: str = "") -> str:
        """简单聊天：发送一条消息，返回文本回复

        Args:
            user_message: 用户消息
            system_prompt: 系统提示词

        Returns:
            LLM 回复的文本内容
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        response = await self.chat(messages)
        return response.choices[0].message.content or ""

    # ── Agent 回调生成 ──

    def create_agent_callback(self) -> Callable:
        """创建 Agent 使用的 LLM 回调函数

        Agent 调用此回调时将传入：
        - user_input: 用户输入文本
        - context: 包含 available_tools / available_skills / available_mcp_tools 等

        回调返回一个 intent dict，Agent 据此执行工具/技能调用。
        """
        client = self

        async def llm_callback(
            user_input: str,
            context: Dict[str, Any],
        ) -> Dict[str, Any]:
            """LLM 驱动的意图路由回调

            将用户输入 + 可用工具/技能信息发送给 LLM，
            由 LLM 自主判断应该调用哪个工具/技能，并提取参数。
            """
            available_tools = context.get("available_tools", [])
            available_skills = context.get("available_skills", [])
            available_mcp_tools = context.get("available_mcp_tools", [])
            user_context = context.get("user_context", {})

            # 构建系统提示词
            system_prompt = _build_system_prompt(
                available_tools, available_skills, available_mcp_tools
            )

            # 构建用户消息（含上下文）
            user_message = _build_user_message(user_input, user_context)

            # 构建 Function Calling 工具定义
            tools = _build_tool_definitions(
                available_tools, available_skills, available_mcp_tools
            )

            try:
                response = await client.chat(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    tools=tools,
                    temperature=0.3,  # 路由时用较低温度以获得稳定结果
                )

                return _parse_tool_call_response(response)

            except Exception as e:
                logger.exception("LLM 回调异常")
                return {
                    "type": "llm",
                    "success": True,
                    "data": f"LLM 调用异常: {e}",
                }

        return llm_callback


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════

def _build_system_prompt(
    tools: List[Dict[str, Any]],
    skills: List[Dict[str, Any]],
    mcp_tools: List[Dict[str, Any]],
) -> str:
    """构建系统提示词"""
    parts = [
        "你是 ConfigBot，一个智能 AI Agent 助手。",
        "你可以使用以下工具和技能来完成用户的任务。",
        "请根据用户的输入，自主判断应该调用哪个工具或技能。",
        "",
    ]

    if tools:
        parts.append("## 内置工具")
        for t in tools:
            name = t.get("name", "")
            desc = t.get("description", "")
            parts.append(f"- **{name}**: {desc}")
        parts.append("")

    if skills:
        parts.append("## 技能")
        for s in skills:
            name = s.get("name", "")
            desc = s.get("description", "")
            parts.append(f"- **{name}**: {desc}")
        parts.append("")

    if mcp_tools:
        parts.append("## MCP 工具")
        for t in mcp_tools:
            name = t.get("name", "")
            server = t.get("server", "")
            desc = t.get("description", "")
            parts.append(f"- **{server}/{name}**: {desc}")
        parts.append("")

    parts.append("## 指令")
    parts.append("1. 如果用户只是问候或询问能力，直接回复，不要调用工具。")
    parts.append("2. 如果用户请求执行具体操作，选择合适的工具/技能调用。")
    parts.append("3. 工具调用时，从用户输入中提取参数值。")
    parts.append("4. 回复使用中文，简洁明了。")

    return "\n".join(parts)


def _build_user_message(
    user_input: str,
    user_context: Dict[str, Any],
) -> str:
    """构建发送给 LLM 的用户消息"""
    parts = [f"用户输入: {user_input}"]

    if user_context:
        ctx_str = json.dumps(user_context, ensure_ascii=False)
        parts.append(f"上下文: {ctx_str}")

    return "\n".join(parts)


def _build_tool_definitions(
    tools: List[Dict[str, Any]],
    skills: List[Dict[str, Any]],
    mcp_tools: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """构建 OpenAI Function Calling 格式的工具定义"""
    definitions = []

    # 内置工具
    for t in tools:
        params = t.get("parameters", {})
        definitions.append({
            "type": "function",
            "function": {
                "name": f"tool__{t.get('name', '')}",
                "description": t.get("description", ""),
                "parameters": params if params else {"type": "object", "properties": {}},
            },
        })

    # 技能
    for s in skills:
        definitions.append({
            "type": "function",
            "function": {
                "name": f"skill__{s.get('name', '')}",
                "description": s.get("description", ""),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "文件路径"},
                        "text": {"type": "string", "description": "文本内容"},
                    },
                },
            },
        })

    # MCP 工具
    for t in mcp_tools:
        params = t.get("parameters", {})
        definitions.append({
            "type": "function",
            "function": {
                "name": f"mcp__{t.get('server', '')}__{t.get('name', '')}",
                "description": t.get("description", ""),
                "parameters": params if params else {"type": "object", "properties": {}},
            },
        })

    return definitions


def _parse_tool_call_response(
    response: openai.types.chat.ChatCompletion,
) -> Dict[str, Any]:
    """解析 LLM 响应，提取工具调用或文本回复"""
    if not response.choices:
        return {"type": "llm", "success": True, "data": "LLM 无响应"}

    choice = response.choices[0]
    message = choice.message

    # 如果有工具调用
    if message.tool_calls:
        tool_call = message.tool_calls[0]
        func_name = tool_call.function.name
        func_args = json.loads(tool_call.function.arguments)

        # 解析名称前缀：tool__ / skill__ / mcp__server__tool
        if func_name.startswith("tool__"):
            return {
                "type": "tool",
                "name": func_name.replace("tool__", "", 1),
                "params": func_args,
            }
        elif func_name.startswith("skill__"):
            return {
                "type": "skill",
                "name": func_name.replace("skill__", "", 1),
                "params": func_args,
            }
        elif func_name.startswith("mcp__"):
            parts = func_name.replace("mcp__", "", 1).split("__", 1)
            server = parts[0] if len(parts) > 0 else ""
            name = parts[1] if len(parts) > 1 else ""
            return {
                "type": "mcp",
                "server": server,
                "name": name,
                "params": func_args,
            }
        else:
            return {"type": "llm", "success": True, "data": f"未知工具: {func_name}"}

    # 纯文本回复
    content = message.content or ""
    return {"type": "llm", "success": True, "data": content}


# ═══════════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════════

def create_llm_client(
    api_key: Optional[str] = None,
    model: str = QWEN_VL_MAX,
    base_url: str = DASHSCOPE_BASE_URL,
) -> LLMClient:
    """快速创建 LLM 客户端

    Args:
        api_key: DashScope API Key，默认从环境变量读取
        model: 模型名称，默认 qwen-vl-max（视觉模型）
        base_url: API 地址

    Returns:
        LLMClient 实例
    """
    return LLMClient(api_key=api_key, model=model, base_url=base_url)