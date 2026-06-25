"""ChatSession - 多轮对话会话管理器

提供统一的聊天入口，支持：
- 多轮对话历史管理
- 上下文累积（跨轮次传递文件路径等）
- 自然语言 → Agent 自动路由
- LLM 驱动的智能推理（可选）
- 交互式 REPL 和单次调用两种模式
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from .agent import Agent
from .llm import LLMClient, create_llm_client
from .logger import log_info

logger = logging.getLogger(__name__)


class ChatSession:
    """多轮对话会话管理器

    使用示例:
        # 不使用 LLM（纯关键词匹配）
        agent = Agent()
        session = ChatSession(agent)

        # 使用 LLM（阿里 DashScope 视觉模型）
        llm = create_llm_client()
        session = ChatSession(agent, llm_client=llm)

        # 交互式模式
        await session.run_repl()

        # 单次调用
        response = await session.chat("帮我审查 main.py")
    """

    def __init__(self, agent: Agent, llm_client: Optional[LLMClient] = None):
        self.agent = agent
        self.llm_client = llm_client
        self.history: List[Dict[str, str]] = []
        self.context: Dict[str, Any] = {}
        self._turn_count = 0

        # 如果提供了 LLM 客户端，注册到 Agent
        if llm_client:
            self.agent.set_llm(llm_client.create_agent_callback())
            logger.info("LLM 已配置: model=%s", llm_client.model)
        else:
            logger.info("LLM 未配置，使用关键词匹配模式")

    # ── 核心聊天接口 ──

    async def chat(self, user_input: str) -> str:
        """处理单轮对话，返回格式化的响应文本

        这是统一的聊天入口函数，所有用户输入都通过此方法处理。
        Agent 内部自动完成意图识别、工具选择和执行。
        """
        self._turn_count += 1

        # 记录用户输入
        self.history.append({"role": "user", "content": user_input})

        # 构建增强上下文（含历史信息）
        enriched_context = self._build_context(user_input)

        # 委托 Agent 处理
        try:
            result = await self.agent.run(user_input, enriched_context)
        except Exception as e:
            logger.exception("Agent.run 异常")
            response = f"[错误] 处理请求时发生异常: {e}"
            self.history.append({"role": "assistant", "content": response})
            return response

        # 格式化响应
        response = self._format_response(result)

        # 更新上下文（从结果中提取可复用的信息）
        self._update_context(user_input, result)

        # 记录助手响应
        self.history.append({"role": "assistant", "content": response})

        return response

    async def chat_stream(self, user_input: str):
        """流式处理单轮对话，逐 chunk 产出响应文本

        当 LLM 返回文本回复时，逐 token 流式输出；
        当匹配到工具/技能时，一次性产出格式化结果。

        Yields:
            str: 响应文本的增量片段
        """
        self._turn_count += 1
        self.history.append({"role": "user", "content": user_input})

        enriched_context = self._build_context(user_input)

        # 先尝试 Agent 路由（工具/技能/LLM 意图）
        try:
            result = await self.agent.run(user_input, enriched_context)
        except Exception as e:
            logger.exception("Agent.run 异常")
            yield f"[错误] 处理请求时发生异常: {e}"
            return

        # 如果是 LLM 纯文本回复且配置了 LLM → 流式输出
        if result.get("type") == "llm" and result.get("success") and self.llm_client:
            full_response = ""
            try:
                system_prompt = self._build_llm_system_prompt()
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                # 带上历史上下文
                for h in self.history[-10:]:
                    messages.append(h)
                async for chunk in self.llm_client.chat_stream(messages):
                    yield chunk
                    full_response += chunk
            except Exception as e:
                logger.exception("LLM 流式调用异常")
                yield f"\n[LLM 流式异常: {e}]"
                full_response = result.get("data", str(result))
        else:
            # 工具/技能/其他结果 → 一次性输出
            full_response = self._format_response(result)
            yield full_response

        self._update_context(user_input, result)
        self.history.append({"role": "assistant", "content": full_response})

    def _build_llm_system_prompt(self) -> str:
        """构建 LLM 流式聊天用的系统提示词"""
        from .llm.client import _build_system_prompt
        return _build_system_prompt(
            self.agent.tool_registry.get_all_schemas(),
            self.agent.skill_registry.get_all_info(),
            self.agent.mcp_manager.get_all_tool_schemas(),
        )

    async def run_repl(self, user_inputs: List[str]) -> None:
        """按顺序处理传入的用户输入列表

        所有用户输入从最外层调用方统一收集后传入，不再使用 input()。

        Args:
            user_inputs: 用户输入字符串列表，每个元素代表一轮对话。
        """
        for raw_input in user_inputs:
            user_input = raw_input.strip()
            if not user_input:
                continue

            # 特殊命令
            if user_input.lower() in ("exit", "quit", "退出", "q"):
                log_info("再见！")
                break
            if user_input.lower() in ("help", "帮助", "h", "?"):
                self._print_help()
                continue
            if user_input.lower() in ("clear", "清空", "cls"):
                self.clear()
                log_info("会话已清空。")
                continue
            if user_input.lower() in ("history", "历史"):
                self._print_history()
                continue
            if user_input.lower() in ("status", "状态"):
                self._print_status()
                continue

            # 处理用户输入
            response = await self.chat(user_input)
            log_info(f"\n{response}\n")

    # ── 上下文管理 ──

    def _build_context(self, user_input: str) -> Dict[str, Any]:
        """从历史对话中构建上下文，传递给 Agent

        自动提取历史中的关键信息：
        - 最近提到的文件路径
        - 最近操作的目标
        """
        context = dict(self.context)

        # 从当前输入和历史中提取文件路径
        file_path = self._extract_file_path(user_input)
        if not file_path:
            file_path = self.context.get("last_file_path")
        if file_path:
            context["file_path"] = file_path

        # 从历史中提取最近的操作上下文
        if self.history:
            last_user = ""
            for h in reversed(self.history):
                if h["role"] == "user":
                    last_user = h["content"]
                    break
            context["last_user_input"] = last_user

        context["history_length"] = len(self.history)
        context["turn_count"] = self._turn_count

        return context

    def _update_context(self, user_input: str, result: Dict[str, Any]):
        """从 Agent 执行结果中更新上下文"""
        # 提取文件路径
        fp = self._extract_file_path(user_input)
        if fp:
            self.context["last_file_path"] = fp

        # 提取 Skill 名称
        if result.get("type") == "skill" and result.get("success"):
            self.context["last_skill"] = result.get("skill_name")

        # 提取工具名称
        if result.get("type") == "tool" and result.get("success"):
            self.context["last_tool"] = result.get("tool_name")

    @staticmethod
    def _extract_file_path(text: str) -> Optional[str]:
        """从文本中提取文件路径"""
        import re
        # 匹配常见文件路径模式
        patterns = [
            r'([\w./\\-]+\.(?:py|txt|json|yaml|yml|md|csv|log|xml|ini|cfg|toml))',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                path = match.group(1)
                # 排除明显不是文件路径的
                if not path.startswith(('http://', 'https://')):
                    return path
        return None

    # ── 响应格式化 ──

    def _format_response(self, result: Dict[str, Any]) -> str:
        """将 Agent 返回的结构化结果格式化为自然语言响应"""
        result_type = result.get("type", "unknown")

        handlers = {
            "tool": self._format_tool_result,
            "mcp": self._format_mcp_result,
            "skill": self._format_skill_result,
            "llm": self._format_llm_result,
            "info": self._format_info_result,
            "query": self._format_info_result,
            "error": self._format_error_result,
            "skill_create": self._format_skill_create_result,
            "skill_update": self._format_skill_update_result,
            "skill_uninstall": self._format_skill_uninstall_result,
            "reload": self._format_reload_result,
        }

        handler = handlers.get(result_type, self._format_generic_result)
        return handler(result)

    def _format_tool_result(self, result: Dict[str, Any]) -> str:
        tool_name = result.get("tool_name", "未知工具")
        if result.get("success"):
            data = result.get("data")
            if isinstance(data, str) and len(data) > 2000:
                data = data[:2000] + "\n... (输出已截断)"
            return f"[工具: {tool_name}] 执行成功\n{data}"
        else:
            return f"[工具: {tool_name}] 执行失败: {result.get('error', '未知错误')}"

    def _format_mcp_result(self, result: Dict[str, Any]) -> str:
        server = result.get("server", "未知服务")
        tool_name = result.get("tool_name", "未知工具")
        if result.get("success"):
            data = result.get("data", "无返回数据")
            return f"[MCP: {server}/{tool_name}] 执行成功\n{json.dumps(data, ensure_ascii=False, indent=2)}"
        else:
            return f"[MCP: {server}/{tool_name}] 执行失败: {result.get('error', '未知错误')}"

    def _format_skill_result(self, result: Dict[str, Any]) -> str:
        skill_name = result.get("skill_name", "未知技能")
        if result.get("success"):
            data = result.get("data")
            steps = result.get("steps", [])
            lines = [f"[技能: {skill_name}] 执行成功"]
            if steps:
                step_strs = [s.get("tool", s.get("step", str(s))) if isinstance(s, dict) else str(s) for s in steps]
                lines.append(f"执行步骤: {' → '.join(step_strs)}")
            if data is not None:
                if isinstance(data, dict):
                    lines.append(json.dumps(data, ensure_ascii=False, indent=2))
                else:
                    lines.append(str(data))
            return "\n".join(lines)
        else:
            return f"[技能: {skill_name}] 执行失败: {result.get('error', '未知错误')}"

    def _format_llm_result(self, result: Dict[str, Any]) -> str:
        if result.get("success"):
            return str(result.get("data", ""))
        else:
            return f"[LLM] {result.get('error', 'LLM 未配置')}"

    def _format_info_result(self, result: Dict[str, Any]) -> str:
        """格式化信息查询结果（如"你能做什么"）"""
        lines = []
        if "message" in result:
            lines.append(result["message"])

        summary = self.agent.summary()
        lines.append(f"\n我是 {summary['name']}，当前能力如下：")
        lines.append(f"  - 内置工具: {summary['tools']['count']} 个")
        lines.append(f"    {', '.join(summary['tools']['names'][:8])}{'...' if len(summary['tools']['names']) > 8 else ''}")
        lines.append(f"  - MCP 服务: {', '.join(summary['mcp']['servers'])}")
        lines.append(f"  - 技能: {summary['skills']['count']} 个")
        lines.append(f"    {', '.join(summary['skills']['names'][:8])}{'...' if len(summary['skills']['names']) > 8 else ''}")

        if result.get("hint"):
            lines.append(f"\n提示: {result['hint']}")

        return "\n".join(lines)

    def _format_error_result(self, result: Dict[str, Any]) -> str:
        return f"[错误] {result.get('error', '未知错误')}"

    def _format_skill_create_result(self, result: Dict[str, Any]) -> str:
        if result.get("success"):
            lines = [f"技能创建成功: {result.get('skill_name')}"]
            if result.get("file_path"):
                lines.append(f"文件路径: {result.get('file_path')}")
            if result.get("message"):
                lines.append(result["message"])
            return "\n".join(lines)
        else:
            return f"技能创建失败: {result.get('error', '未知错误')}"

    def _format_skill_update_result(self, result: Dict[str, Any]) -> str:
        if result.get("success"):
            lines = [f"技能更新成功: {result.get('skill_name')}"]
            if result.get("old_version") and result.get("new_version"):
                lines.append(f"版本: {result['old_version']} → {result['new_version']}")
            return "\n".join(lines)
        else:
            return f"技能更新失败: {result.get('error', '未知错误')}"

    def _format_skill_uninstall_result(self, result: Dict[str, Any]) -> str:
        if result.get("success"):
            lines = [f"技能卸载成功: {result.get('skill_name')}"]
            if result.get("message"):
                lines.append(result["message"])
            return "\n".join(lines)
        else:
            return f"技能卸载失败: {result.get('error', '未知错误')}"

    def _format_reload_result(self, result: Dict[str, Any]) -> str:
        if result.get("success"):
            data = result.get("data", {})
            return f"重载完成: {data.get('message', 'ok')}\n当前技能总数: {data.get('total_skills', '?')}"
        return f"重载失败: {result.get('error', '未知错误')}"

    def _format_generic_result(self, result: Dict[str, Any]) -> str:
        return json.dumps(result, ensure_ascii=False, indent=2)

    # ── 会话管理 ──

    def clear(self):
        """清空会话历史和上下文"""
        self.history.clear()
        self.context.clear()
        self._turn_count = 0

    def get_history(self) -> List[Dict[str, str]]:
        """获取对话历史"""
        return list(self.history)

    def get_context(self) -> Dict[str, Any]:
        """获取当前上下文"""
        return dict(self.context)

    # ── 交互式界面 ──

    def _print_welcome(self):
        summary = self.agent.summary()
        llm_status = "已配置" if summary["llm_configured"] else "未配置"
        if self.llm_client:
            llm_status += f" ({self.llm_client.model})"

        log_info("=" * 60)
        log_info(f"  {summary['name']} - 交互式聊天模式")
        log_info("=" * 60)
        log_info(f"  LLM: {llm_status}")
        log_info("")

        # ── 工具列表 ──
        log_info(f"  【工具】共 {summary['tools']['count']} 个")
        log_info("  " + "-" * 40)
        for tool in self.agent.tool_registry.list_all():
            desc = tool.description[:60] + "..." if len(tool.description) > 60 else tool.description
            example = self._gen_tool_example(tool)
            log_info(f"  • {tool.name}")
            log_info(f"    功能: {desc}")
            if example:
                log_info(f"    示例: {example}")
        log_info("")

        # ── 技能列表 ──
        log_info(f"  【技能】共 {summary['skills']['count']} 个")
        log_info("  " + "-" * 40)
        for skill in self.agent.skill_registry.list_all():
            desc = skill.description[:60] + "..." if len(skill.description) > 60 else skill.description
            example = self._gen_skill_example(skill)
            log_info(f"  • {skill.name}")
            log_info(f"    功能: {desc}")
            if example:
                log_info(f"    示例: {example}")
        log_info("")

        log_info(f"  输入 'help' 查看命令, 'exit' 退出")
        log_info("=" * 60)

    def _gen_tool_example(self, tool) -> str:
        """根据工具的参数 schema 生成使用示例"""
        try:
            schema = tool._get_parameters_schema()
            props = schema.get("properties", {})
            required = schema.get("required", [])
            if not props:
                return ""
            # 生成所有 required 参数的示例
            parts = []
            for pname in required:
                prop_info = props.get(pname, {})
                ptype = prop_info.get("type", "string")
                if ptype == "string":
                    val = f'"<{pname}>"'
                elif ptype in ("integer", "number"):
                    val = "1"
                else:
                    val = "true"
                parts.append(f"{pname}={val}")
            if parts:
                return f'"{tool.name} {" ".join(parts)}"'
            # 没有 required 参数时，取第一个可选参数
            first = list(props.keys())[0]
            return f'"{tool.name}"'
        except Exception:
            return ""

    def _gen_skill_example(self, skill) -> str:
        """根据技能名称生成自然语言使用示例"""
        name = skill.name
        if "security" in name:
            return '"帮我扫描 main.py 的安全漏洞"'
        if "review" in name:
            return '"帮我审查 main.py 文件"'
        if "translator" in name or "translate" in name:
            return '"帮我把 readme.txt 翻译成中文"'
        if "csv" in name:
            return '"帮我把 data.csv 转换为 JSON"'
        if "json" in name:
            return '"帮我验证 data.json 是否合法"'
        if "backup" in name:
            return '"帮我备份 config 目录"'
        if "log" in name:
            return '"分析最近的日志文件"'
        if "deduplicator" in name or "dedup" in name:
            return '"帮我去重 data.csv 文件"'
        if "report" in name:
            return '"帮我生成一份项目报告"'
        if "stats" in name:
            return '"帮我统计文件行数和注释率"'
        return f'"帮我执行 {skill.description[:20]}"'

    def _print_help(self):
        log_info("""
可用命令:
  help / 帮助     - 显示此帮助信息
  exit / 退出     - 退出聊天
  clear / 清空    - 清空对话历史
  history / 历史  - 显示对话历史
  status / 状态   - 显示 Agent 状态

使用方式:
  直接用自然语言描述你的需求，Agent 会自动选择合适的工具/技能执行。
  例如：
    - "帮我审查 main.py"
    - "查看当前目录下的文件"
    - "查询北京的天气"
    - "你能做什么？"
    - "帮我生成一个skill，名字叫data_cleaner，用来做数据清洗"
    - "卸载skill data_backup"
    - "skill:csv_converter" (直接调用指定技能)
""")

    def _print_history(self):
        if not self.history:
            log_info("(无对话历史)")
            return
        log_info("\n对话历史:")
        for i, entry in enumerate(self.history, 1):
            role = "用户" if entry["role"] == "user" else "助手"
            content = entry["content"]
            if len(content) > 100:
                content = content[:100] + "..."
            log_info(f"  {i}. [{role}] {content}")

    def _print_status(self):
        summary = self.agent.summary()
        log_info(f"\nAgent 状态: {summary['name']}")
        log_info(f"  对话轮次: {self._turn_count}")
        log_info(f"  历史条数: {len(self.history)}")
        log_info(f"  上下文键: {list(self.context.keys())}")
        log_info(f"  工具: {summary['tools']['count']} 个")
        log_info(f"  技能: {summary['skills']['count']} 个")
        log_info(f"  LLM: {'已配置' if summary['llm_configured'] else '未配置'}")


# ═══════════════════════════════════════════════════════════════
# 便捷函数：快速创建聊天会话
# ═══════════════════════════════════════════════════════════════

def create_chat_session(
    agent: Optional[Agent] = None,
    llm_client: Optional[LLMClient] = None,
) -> ChatSession:
    """快速创建聊天会话

    Args:
        agent: Agent 实例，为 None 时自动创建
        llm_client: LLM 客户端，为 None 时使用关键词匹配模式

    Returns:
        ChatSession 实例
    """
    if agent is None:
        agent = Agent()
    return ChatSession(agent, llm_client=llm_client)


async def chat_once(
    user_input: str,
    agent: Optional[Agent] = None,
    llm_client: Optional[LLMClient] = None,
) -> str:
    """单次对话调用

    Args:
        user_input: 用户输入的自然语言文本
        agent: Agent 实例，为 None 时自动创建
        llm_client: LLM 客户端

    Returns:
        格式化的响应文本
    """
    session = create_chat_session(agent, llm_client=llm_client)
    return await session.chat(user_input)


async def chat_repl(
    user_inputs: List[str],
    agent: Optional[Agent] = None,
    llm_client: Optional[LLMClient] = None,
) -> None:
    """启动交互式 REPL 聊天（所有输入从最外层传入）

    Args:
        user_inputs: 用户输入字符串列表，由最外层调用方统一收集后传入。
        agent: Agent 实例，为 None 时自动创建。
        llm_client: LLM 客户端。
    """
    session = create_chat_session(agent, llm_client=llm_client)
    await session.run_repl(user_inputs)