"""ConfigBot - 可扩展 AI Agent 框架

支持：
- 自然语言输入 → 自主选择工具/Skill 执行
- 多轮对话上下文管理
- LLM 接入（支持阿里 DashScope/Qwen 等）
- Skill 动态创建/更新/卸载
"""

__version__ = "0.1.0"

from .agent import Agent
from .chat import ChatSession, create_chat_session, chat_once, chat_repl
from .llm import LLMClient, create_llm_client

__all__ = [
    "Agent",
    "ChatSession",
    "create_chat_session",
    "chat_once",
    "chat_repl",
    "LLMClient",
    "create_llm_client",
]