"""LLM 模块 - 对接阿里 DashScope 视觉模型"""

from .client import (
    LLMClient,
    QWEN_VL_MAX,
    QWEN_VL_PLUS,
    QWEN_MAX,
    QWEN_PLUS,
    DASHSCOPE_BASE_URL,
    create_llm_client,
)

__all__ = [
    "LLMClient",
    "QWEN_VL_MAX",
    "QWEN_VL_PLUS",
    "QWEN_MAX",
    "QWEN_PLUS",
    "DASHSCOPE_BASE_URL",
    "create_llm_client",
]