"""Agent 核心编排引擎

Agent 是三大机制的协调者：
1. 内置 Tool 调用
2. MCP 工具调用
3. Skill 调度执行

通过统一的 Agent.run() 接口处理用户请求，
内部自动路由到合适的工具/技能组合。
"""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional

from ..tools import ToolRegistry, ToolExecResult
from ..tools.builtin import (
    ReadFileTool,
    WriteFileTool,
    ListDirTool,
    DeleteFileTool,
    FileInfoTool,
    WebFetchTool,
    WebSearchTool,
    HttpPostTool,
    BaiduWeatherTool,
    RunCommandTool,
    GetEnvTool,
    JsonFormatterTool,
    TextTemplateTool,
)
from ..mcp import MCPRegistry, MCPManager, MCPResponse
from ..mcp.servers import FilesystemMCPServer
from ..skills import SkillRegistry, SkillExecResult, SkillManager
from ..skills.builtin import CodeReviewSkill, SecurityReviewSkill

# 外部 Skill 加载器
from ..xiaohua.skills import load_skills_from_dir

logger = logging.getLogger(__name__)


class Agent:
    """AI Agent 核心类

    三大机制的统一入口：
    - tools:  内置工具链，支持动态注册新工具
    - mcp:    MCP 协议工具，支持内置 Server 和远程 Client
    - skills: 高级技能单元，组合工具完成复杂任务

    使用示例:
        agent = Agent()
        agent.register_tool(MyCustomTool())
        agent.register_mcp_server(MyMCPServer())
        agent.register_skill(MySkill())

        result = await agent.run("帮我审查 app.py")
    """

    def __init__(self, name: str = "ConfigBot"):
        self.name = name

        # 三大注册中心
        self.tool_registry = ToolRegistry()
        self.mcp_registry = MCPRegistry()
        self.mcp_manager = MCPManager(self.mcp_registry)
        self.skill_registry = SkillRegistry()

        # Skill 生命周期管理器（创建/更新/卸载）
        self.skill_manager = SkillManager(
            self._get_external_skills_dir(),
            self.skill_registry,
            reload_callback=self.reload_external_skills,
        )

        # LLM 回调（由外部注入，实现真正的 AI 推理）
        self._llm_callback: Optional[Callable] = None

        # 初始化内置组件
        self._setup_builtin_tools()
        self._setup_builtin_mcp_servers()
        self._setup_builtin_skills()

    # ── 内置组件初始化 ──

    def _setup_builtin_tools(self) -> None:
        """注册内置工具（按分类组织）"""
        for tool in [
            # file 类
            ReadFileTool(),
            WriteFileTool(),
            ListDirTool(),
            DeleteFileTool(),
            FileInfoTool(),
            # web 类
            WebFetchTool(),
            WebSearchTool(),
            HttpPostTool(),
            BaiduWeatherTool(),
            # system 类
            RunCommandTool(),
            GetEnvTool(),
            # code 类
            JsonFormatterTool(),
            TextTemplateTool(),
        ]:
            self.tool_registry.register(tool)

    def _setup_builtin_mcp_servers(self) -> None:
        """注册内置 MCP Server"""
        self.mcp_registry.register_server(FilesystemMCPServer())

    def _setup_builtin_skills(self) -> None:
        """注册内置 Skill + 自动加载外部 Skill"""
        # 内置 Skill
        for skill in [CodeReviewSkill(), SecurityReviewSkill()]:
            self.skill_registry.register(skill)

        # 自动加载 xiaohua/skills/ 目录下的外部 Skill
        self._load_external_skills()

    def _get_external_skills_dir(self) -> str:
        """获取外部技能目录路径"""
        from pathlib import Path
        return str(Path(__file__).resolve().parent.parent / "xiaohua" / "skills")

    def _load_external_skills(self) -> int:
        """从外部技能目录加载所有 Skill 文件"""
        skills_dir = self._get_external_skills_dir()
        external_skills = load_skills_from_dir(skills_dir)
        count = 0
        for skill in external_skills:
            if skill.name not in self.skill_registry:
                self.skill_registry.register(skill)
                logger.info("加载外部技能: %s (v%s)", skill.name, skill.version)
                count += 1
        logger.info("外部技能加载完成: %d 个", count)
        return count

    def reload_external_skills(self) -> Dict[str, Any]:
        """运行时重载外部技能目录

        新放入目录的技能文件会自动被发现并加载。
        已存在的技能不会被覆盖，如需刷新请重启 Agent。

        Returns:
            {"added": [...], "total": int}
        """
        before = set(self.skill_registry._skills.keys())
        count = self._load_external_skills()
        after = set(self.skill_registry._skills.keys())
        added = list(after - before)
        return {"added": added, "total": len(after)}

    def _handle_reload(self) -> Dict[str, Any]:
        """处理 reload 指令：动态重载外部技能"""
        result = self.reload_external_skills()
        if result["added"]:
            return {
                "type": "reload",
                "success": True,
                "data": {
                    "message": f"已加载 {len(result['added'])} 个新技能",
                    "new_skills": result["added"],
                    "total_skills": result["total"],
                },
            }
        else:
            return {
                "type": "reload",
                "success": True,
                "data": {
                    "message": "没有发现新技能文件",
                    "new_skills": [],
                    "total_skills": result["total"],
                },
            }

    # ── 扩展接口 ──

    def register_tool(self, tool) -> "Agent":
        """注册新的内置工具"""
        self.tool_registry.register(tool)
        logger.info(f"注册工具: {tool.name}")
        return self

    def register_mcp_server(self, server) -> "Agent":
        """注册新的 MCP Server"""
        self.mcp_registry.register_server(server)
        logger.info(f"注册 MCP Server: {server.name}")
        return self

    def register_skill(self, skill) -> "Agent":
        """注册新的 Skill（支持内部或外部 Skill）"""
        self.skill_registry.register(skill)
        logger.info(f"注册技能: {skill.name}")
        return self

    def register_mcp_client(self, client) -> "Agent":
        """注册远程 MCP Client"""
        self.mcp_registry.register_client(client)
        logger.info(f"注册 MCP Client: {client.transport}")
        return self

    def register_skill(self, skill) -> "Agent":
        """注册新的 Skill"""
        self.skill_registry.register(skill)
        logger.info(f"注册 Skill: {skill.name}")
        return self

    def set_llm(self, callback: Callable) -> "Agent":
        """设置 LLM 回调函数，实现真正的 AI 推理

        callback 签名: async def llm(query: str, context: dict) -> dict
        """
        self._llm_callback = callback
        return self

    # ── 执行器闭包 ──

    async def _tool_executor(self, tool_name: str, **kwargs) -> ToolExecResult:
        """内置工具执行器（传给 Skill 使用）"""
        tool = self.tool_registry.get(tool_name)
        if not tool:
            return ToolExecResult(success=False, error=f"工具不存在: {tool_name}")
        return await tool.execute(**kwargs)

    async def _mcp_executor(
        self, server_name: str, tool_name: str, **kwargs
    ) -> MCPResponse:
        """MCP 工具执行器（传给 Skill 使用）"""
        return await self.mcp_manager.call(server_name, tool_name, **kwargs)

    # ── 核心运行逻辑 ──

    async def run(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """处理用户请求的主入口

        Args:
            user_input: 用户输入文本
            context: 额外上下文（文件路径等）

        Returns:
            包含 type 和 result 的字典
        """
        context = context or {}

        try:
            # 简单意图路由（实际生产环境此处由 LLM 推理）
            intent = self._route_intent(user_input, context)

            if intent["type"] == "tool":
                return await self._handle_tool_call(intent, context)
            elif intent["type"] == "reload":
                return self._handle_reload()
            elif intent["type"] == "skill_create":
                return self._handle_skill_create(intent, context)
            elif intent["type"] == "skill_update":
                return self._handle_skill_update(intent, context)
            elif intent["type"] == "skill_uninstall":
                return self._handle_skill_uninstall(intent, context)
            elif intent["type"] == "mcp":
                return await self._handle_mcp_call(intent, context)
            elif intent["type"] == "skill":
                return await self._handle_skill_call(intent, context)
            elif intent["type"] == "llm":
                return await self._handle_llm_call(user_input, context)
            else:
                return await self._handle_query(user_input, context)
        except Exception:
            logger.exception("Agent.run 异常: input=%s", user_input[:100])
            return {"type": "error", "success": False, "error": "内部处理异常"}

    def _route_intent(
        self, user_input: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """意图路由：基于自然语言的自主工具选择

        路由优先级：Skill 生命周期指令 > 显式 Skill > 评分匹配 > LLM > 查询

        评分匹配规则：
        1. 对 Skill、Tool、MCP 三类分别计算相关性评分
        2. 按评分从高到低选择最佳匹配
        3. 自动提取自然语言中的参数
        """
        inp = user_input.lower().strip()

        # ── Skill 生命周期管理指令 ──

        # 卸载 Skill: "卸载skill xxx" / "删除skill xxx"
        if "卸载" in inp or "删除" in inp:
            if "skill" in inp.lower() or "技能" in inp:
                return self._parse_uninstall_intent(user_input)

        # 更新/进化 Skill: "优化skill xxx" / "更新skill xxx" / "进化skill xxx"
        if "优化" in inp or "更新" in inp or "进化" in inp:
            if "skill" in inp.lower() or "技能" in inp:
                return self._parse_update_intent(user_input, context)

        # 创建 Skill: "生成skill" / "创建skill" / "新建skill" / "帮我生成一个skill"
        if "生成" in inp or "创建" in inp or "新建" in inp:
            if "skill" in inp.lower() or "技能" in inp:
                return self._parse_create_intent(user_input, context)

        # 系统指令：reload 动态重载外部技能
        if inp == "reload":
            return {"type": "reload"}

        # 直接指定 Skill 调用：skill:技能名
        if inp.startswith("skill:"):
            skill_name = user_input.split(":", 1)[1].strip()
            return {"type": "skill", "name": skill_name}

        # ── 信息查询意图（仅无 LLM 时启用，有 LLM 时交给 LLM 回答）──
        if not self._llm_callback and self._is_info_query(inp):
            return {"type": "query"}

        # ── 评分匹配：对所有可用资源进行评分 ──
        candidates = self._score_all_resources(user_input, context)

        if candidates:
            best = candidates[0]
            if best["score"] > 0:
                return best["intent"]

        # 如果配置了 LLM，交给 LLM 处理
        if self._llm_callback:
            return {"type": "llm"}

        # 默认：信息查询
        return {"type": "query"}

    # ── 意图匹配辅助方法 ──

    def _is_info_query(self, inp: str) -> bool:
        """判断是否为信息查询类意图"""
        info_patterns = [
            "你能做什么", "你会什么", "帮助", "功能",
            "你是谁", "介绍", "有哪些能力", "可以做什么",
            "what can you do", "help", "capabilities",
        ]
        return any(p in inp for p in info_patterns)

    def _score_all_resources(
        self, user_input: str, context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """对所有可用资源（Skill/Tool/MCP）进行评分匹配

        返回按评分降序排列的候选列表。
        """
        candidates = []

        # 1. 对 Skill 评分
        for skill in self.skill_registry.list_all():
            score = self._score_match(user_input, skill.name, skill.description)
            if score > 0:
                params = self._extract_params(user_input, [])
                candidates.append({
                    "score": score + 5,  # Skill 优先加分
                    "intent": {"type": "skill", "name": skill.name, "params": params},
                })

        # 2. 对 Tool 评分
        for tool in self.tool_registry.list_all():
            score = self._score_match(user_input, tool.name, tool.description)
            if score > 0:
                schema = tool.get_schema()
                param_names = list(schema.get("parameters", {}).get("properties", {}).keys())
                params = self._extract_params(user_input, param_names)
                candidates.append({
                    "score": score,
                    "intent": {"type": "tool", "name": tool.name, "params": params},
                })

        # 3. 对 MCP 工具评分
        for schema in self.mcp_manager.get_all_tool_schemas():
            score = self._score_match(
                user_input,
                f"{schema.get('server', '')}/{schema.get('name', '')}",
                schema.get("description", ""),
            )
            if score > 0:
                param_names = list(schema.get("parameters", {}).get("properties", {}).keys())
                params = self._extract_params(user_input, param_names)
                candidates.append({
                    "score": score,
                    "intent": {
                        "type": "mcp",
                        "server": schema.get("server", ""),
                        "name": schema.get("name", ""),
                        "params": params,
                    },
                })

        # 按评分降序排列
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates

    def _score_match(self, user_input: str, name: str, description: str) -> int:
        """计算用户输入与资源（名称+描述）的匹配评分

        评分规则：
        - 名称完全匹配: +10
        - 名称包含在输入中: +8
        - 输入关键词在名称中: +6
        - 描述关键词匹配: +4/个
        - 中文语义关键词匹配: +3/个
        """
        inp = user_input.lower()
        name_lower = name.lower()
        desc_lower = description.lower() if description else ""
        score = 0

        # 名称匹配
        if name_lower == inp:
            score += 10
        elif name_lower in inp:
            score += 8
        elif any(word in name_lower for word in inp.split() if len(word) >= 2):
            score += 6

        # 描述关键词匹配
        for word in inp.split():
            if len(word) >= 2 and word in desc_lower:
                score += 4

        # 中文语义映射（常见动词 → 工具/技能）
        semantic_map = {
            "读取": ["read", "file_info", "text_stats"],
            "读": ["read", "file_info"],
            "查看": ["list", "file_info", "read", "info", "get"],
            "显示": ["list", "read", "info", "get"],
            "列出": ["list", "list_dir"],
            "目录": ["list_dir", "list"],
            "文件": ["file", "read_file", "file_info", "delete_file"],
            "天气": ["weather", "baidu"],
            "搜索": ["search", "web_search"],
            "获取": ["fetch", "get", "read"],
            "抓取": ["fetch", "web_fetch"],
            "网页": ["web", "fetch", "search"],
            "命令": ["run_command", "cmd"],
            "执行": ["run_command", "execute"],
            "环境": ["get_env", "env"],
            "变量": ["get_env", "env"],
            "格式化": ["format", "json_format"],
            "json": ["json_format", "json_validator"],
            "模板": ["template", "text_template"],
            "审查": ["code_review", "review"],
            "安全": ["security_review", "security"],
            "漏洞": ["security_review", "security"],
            "csv": ["csv_converter"],
            "转换": ["csv_converter", "text_translator"],
            "统计": ["text_stats", "code_stats"],
            "去重": ["data_deduplicator", "deduplicator"],
            "备份": ["file_backup", "data_backup", "backup"],
            "日志": ["log_analyzer", "log"],
            "分析": ["log_analyzer", "analyze"],
            "翻译": ["text_translator", "translate"],
            "报告": ["report_generator", "report"],
            "生成": ["report_generator", "generate"],
            "验证": ["json_validator", "validate"],
            "删除": ["delete_file", "delete"],
            "删除文件": ["delete_file"],
            "写入": ["write_file", "write"],
            "写文件": ["write_file"],
            "保存": ["write_file", "save"],
            "计算": ["calculator", "calculate"],
            "回显": ["echo"],
            "http": ["http_post", "web_fetch"],
            "post": ["http_post"],
        }

        for cn_word, target_keywords in semantic_map.items():
            if cn_word in inp:
                for kw in target_keywords:
                    if kw in name_lower or kw in desc_lower:
                        score += 3

        return score

    def _extract_params(
        self, user_input: str, param_names: List[str]
    ) -> Dict[str, Any]:
        """从自然语言中提取工具参数

        支持的参数名及提取方式：
        - file_path / path / dir_path: 提取文件路径
        - city / location: 提取城市名
        - expression: 提取数学表达式
        - message / text: 提取剩余文本
        - url: 提取 URL
        """
        import re

        params = {}

        for pname in param_names:
            if pname in ("file_path", "path", "dir_path"):
                # 提取文件路径
                fp = self._extract_file_path(user_input)
                if fp:
                    params[pname] = fp

            elif pname in ("city", "location"):
                # 提取城市名（中文城市名模式）
                city_match = re.search(
                    r'(?:城市|查询|在|的)?([\u4e00-\u9fff]{2,4}?)(?:的|天气|气温|温度|预报)',
                    user_input,
                )
                if city_match:
                    # 过滤掉常见非城市词
                    city = city_match.group(1)
                    non_city = {"帮我", "查询", "获取", "显示", "请", "我想", "当前"}
                    if city not in non_city:
                        params[pname] = city

            elif pname == "expression":
                # 提取数学表达式
                expr_match = re.search(
                    r'[\d\s+\-*/().]+', user_input
                )
                if expr_match:
                    expr = expr_match.group(0).strip()
                    if any(c.isdigit() for c in expr):
                        params[pname] = expr

            elif pname in ("message", "text", "content"):
                # 提取消息文本（去除命令词后的内容）
                # 简单实现：提取引号内的内容或最后一段
                quoted = re.findall(r'["""]([^"""]+)["\""]', user_input)
                if quoted:
                    params[pname] = quoted[0]
                else:
                    # 取关键词后的内容
                    params[pname] = user_input

            elif pname == "url":
                url_match = re.search(
                    r'(https?://[^\s]+)', user_input
                )
                if url_match:
                    params[pname] = url_match.group(1)

            elif pname in ("key", "name"):
                # 提取 key=value 或特定格式
                kv_match = re.search(rf'{pname}[=:：]\s*(\S+)', user_input)
                if kv_match:
                    params[pname] = kv_match.group(1)

        return params

    @staticmethod
    def _extract_file_path(text: str) -> Optional[str]:
        """从文本中提取文件路径"""
        import re
        patterns = [
            r'([\w./\\-]+\.(?:py|txt|json|yaml|yml|md|csv|log|xml|ini|cfg|toml))',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                path = match.group(1)
                if not path.startswith(('http://', 'https://')):
                    return path
        return None

    async def _handle_tool_call(
        self, intent: dict, context: dict
    ) -> Dict[str, Any]:
        """处理内置工具调用"""
        tool_name = intent.get("name", "")
        tool = self.tool_registry.get(tool_name)
        if not tool:
            return {"type": "tool", "success": False, "error": f"工具不存在: {tool_name}"}

        # 合并参数：intent 中的自动提取参数 + context 中的上下文参数
        params = {**context, **intent.get("params", {})}
        # 过滤掉非工具参数
        schema = tool.get_schema()
        param_names = set(schema.get("parameters", {}).get("properties", {}).keys())
        if param_names:
            params = {k: v for k, v in params.items() if k in param_names}

        # 为常见参数提供默认值
        self._apply_default_params(param_names, params)

        result = await tool.execute(**params)
        return {
            "type": "tool",
            "tool_name": tool_name,
            "success": result.success,
            "data": result.data,
            "error": result.error,
        }

    @staticmethod
    def _apply_default_params(param_names: set, params: Dict[str, Any]) -> None:
        """为缺失的常见参数补充默认值"""
        defaults = {
            "dir_path": ".",
            "path": ".",
            "file_path": ".",
            "indent": 2,
            "days": 3,
            "format": "markdown",
        }
        for key, default_val in defaults.items():
            if key in param_names and key not in params:
                params[key] = default_val

    async def _handle_mcp_call(
        self, intent: dict, context: dict
    ) -> Dict[str, Any]:
        """处理 MCP 工具调用"""
        server_name = intent.get("server", "")
        tool_name = intent.get("name", "")
        result = await self.mcp_manager.call(
            server_name, tool_name, **intent.get("params", {})
        )
        return {
            "type": "mcp",
            "server": server_name,
            "tool_name": tool_name,
            "success": result.success,
            "data": result.data,
            "error": result.error,
        }

    async def _handle_skill_call(
        self, intent: dict, context: dict
    ) -> Dict[str, Any]:
        """处理 Skill 调用"""
        skill_name = intent.get("name", "")
        skill = self.skill_registry.get(skill_name)
        if not skill:
            return {"type": "skill", "success": False, "error": f"Skill 不存在: {skill_name}"}

        # 前置检查
        available = {t.name for t in self.tool_registry.list_all()}
        if not skill.pre_check(available):
            missing = skill.requires_tools - available
            return {
                "type": "skill",
                "skill_name": skill_name,
                "success": False,
                "error": f"前置工具缺失: {missing}",
            }

        # 合并参数：intent 中的自动提取参数 + context 中的上下文参数
        merged_context = {**context, **intent.get("params", {})}

        result = await skill.execute(merged_context, self._tool_executor, self._mcp_executor)
        return {
            "type": "skill",
            "skill_name": skill_name,
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "steps": result.steps,
        }

    async def _handle_llm_call(
        self, user_input: str, context: dict
    ) -> Dict[str, Any]:
        """委托给 LLM 处理（需注入回调）

        LLM 返回的 intent 可能有两种：
        1. 工具/技能调用意图 → 直接执行对应的工具/技能
        2. 纯文本回复 → 直接返回
        """
        if not self._llm_callback:
            return {"type": "llm", "success": False, "error": "LLM 回调未配置"}

        llm_context = {
            "available_tools": self.tool_registry.get_all_schemas(),
            "available_mcp_tools": self.mcp_manager.get_all_tool_schemas(),
            "available_skills": self.skill_registry.get_all_info(),
            "user_context": context,
        }

        try:
            llm_intent = await self._llm_callback(user_input, llm_context)
        except Exception as e:
            logger.exception("LLM 回调执行异常")
            return {"type": "llm", "success": False, "error": f"LLM 调用异常: {e}"}

        # LLM 返回了工具/技能调用意图 → 直接执行
        intent_type = llm_intent.get("type", "")
        if intent_type == "tool":
            return await self._handle_tool_call(llm_intent, context)
        elif intent_type == "skill":
            return await self._handle_skill_call(llm_intent, context)
        elif intent_type == "mcp":
            return await self._handle_mcp_call(llm_intent, context)

        # LLM 返回了纯文本回复
        return {
            "type": "llm",
            "success": True,
            "data": llm_intent.get("data", str(llm_intent)),
        }

    async def _handle_query(
        self, user_input: str, context: dict
    ) -> Dict[str, Any]:
        """默认查询处理：展示可用能力"""
        result = {
            "type": "info",
            "message": f"[{self.name}] 收到查询: {user_input}",
            "available_tools": len(self.tool_registry),
            "available_mcp_servers": len(self.mcp_registry.list_servers()),
            "available_skills": len(self.skill_registry),
        }
        if not self._llm_callback:
            result["hint"] = "配置 LLM 回调以启用 AI 推理: agent.set_llm(my_llm_function)"
        return result

    # ── 便捷方法 ──

    async def call_tool(self, tool_name: str, **kwargs) -> ToolExecResult:
        """直接调用内置工具"""
        return await self._tool_executor(tool_name, **kwargs)

    async def call_mcp(
        self, server_name: str, tool_name: str, **kwargs
    ) -> MCPResponse:
        """直接调用 MCP 工具"""
        return await self.mcp_manager.call(server_name, tool_name, **kwargs)

    async def call_skill(
        self, skill_name: str, context: Dict[str, Any] = None
    ) -> SkillExecResult:
        """直接调用 Skill"""
        skill = self.skill_registry.get(skill_name)
        if not skill:
            return SkillExecResult(success=False, error=f"Skill 不存在: {skill_name}")
        return await skill.execute(
            context or {}, self._tool_executor, self._mcp_executor
        )

    # ── Skill 生命周期管理 ──

    def _parse_create_intent(
        self, user_input: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """解析创建 Skill 指令

        示例:
            "帮我生成一个skill，名字叫my_tool，用来做数据备份"
            "创建一个技能，叫data_cleaner，功能是数据清洗"
        """
        import re

        name = ""
        description = ""

        # 提取名称: 名字叫xxx / 叫xxx / 名为xxx
        name_match = re.search(
            r"(?:名字叫|名叫|叫|名为|命名[为]?)\s*([a-zA-Z_][a-zA-Z0-9_]*)",
            user_input,
        )
        if name_match:
            name = name_match.group(1)

        # 提取描述: 用来做xxx / 功能是xxx / 作用xxx
        desc_match = re.search(
            r"(?:用来做|功能是|作用是|用于|用途[是为]?)\s*(.+?)(?:[，。！？\s]*$)",
            user_input,
        )
        if desc_match:
            description = desc_match.group(1).strip()

        if not name:
            # 尝试从 context 中获取
            name = context.get("skill_name", "")
            description = context.get("description", description or user_input)

        if not name:
            return {
                "type": "skill_create",
                "success": False,
                "error": "请指定 Skill 名称，例如：帮我生成一个skill，名字叫my_cleaner，用来做数据清洗",
            }

        return {
            "type": "skill_create",
            "name": name,
            "description": description or f"自动生成的 Skill: {name}",
            "category": context.get("category", "custom"),
            "operations": context.get("operations", description or ""),
            "requires_tools": context.get("requires_tools", []),
            "context_keys": context.get("context_keys", []),
        }

    def _parse_update_intent(
        self, user_input: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """解析更新/进化 Skill 指令

        示例:
            "优化skill my_tool，增加日志功能"
            "更新技能 data_cleaner，支持CSV格式"
        """
        import re

        name = ""

        # 提取名称: skill xxx / 技能 xxx
        name_match = re.search(
            r"(?:skill|技能)\s*[:：]?\s*([a-zA-Z_][a-zA-Z0-9_]*)",
            user_input,
            re.IGNORECASE,
        )
        if name_match:
            name = name_match.group(1)

        if not name:
            name = context.get("skill_name", "")

        if not name:
            return {
                "type": "skill_update",
                "success": False,
                "error": "请指定要更新的 Skill 名称，例如：优化skill my_tool，增加XXX功能",
            }

        # 提取新的操作描述
        new_operations = context.get("new_operations", "")
        if not new_operations:
            # 从用户输入中提取"增加xxx"、"支持xxx"等
            new_operations = user_input

        return {
            "type": "skill_update",
            "name": name,
            "new_operations": new_operations,
            "new_description": context.get("new_description"),
            "new_category": context.get("new_category"),
            "new_requires_tools": context.get("new_requires_tools"),
        }

    def _parse_uninstall_intent(self, user_input: str) -> Dict[str, Any]:
        """解析卸载 Skill 指令

        示例:
            "卸载skill my_tool"
            "删除技能 data_cleaner"
        """
        import re

        name = ""

        name_match = re.search(
            r"(?:skill|技能)\s*[:：]?\s*([a-zA-Z_][a-zA-Z0-9_]*)",
            user_input,
            re.IGNORECASE,
        )
        if name_match:
            name = name_match.group(1)

        if not name:
            return {
                "type": "skill_uninstall",
                "success": False,
                "error": "请指定要卸载的 Skill 名称，例如：卸载skill my_tool",
            }

        return {"type": "skill_uninstall", "name": name}

    def _handle_skill_create(
        self, intent: dict, context: dict
    ) -> Dict[str, Any]:
        """处理 Skill 创建"""
        if intent.get("success") is False:
            return {"type": "skill_create", "success": False, "error": intent.get("error")}

        result = self.skill_manager.create_skill(
            name=intent["name"],
            description=intent["description"],
            category=intent.get("category", "custom"),
            operations=intent.get("operations", ""),
            requires_tools=intent.get("requires_tools", []),
            context_keys=intent.get("context_keys", []),
        )
        return {"type": "skill_create", **result}

    def _handle_skill_update(
        self, intent: dict, context: dict
    ) -> Dict[str, Any]:
        """处理 Skill 更新/进化"""
        if intent.get("success") is False:
            return {"type": "skill_update", "success": False, "error": intent.get("error")}

        result = self.skill_manager.update_skill(
            name=intent["name"],
            new_operations=intent.get("new_operations"),
            new_description=intent.get("new_description"),
            new_category=intent.get("new_category"),
            new_requires_tools=intent.get("new_requires_tools"),
            new_context_keys=intent.get("new_context_keys"),
        )
        return {"type": "skill_update", **result}

    def _handle_skill_uninstall(
        self, intent: dict, context: dict
    ) -> Dict[str, Any]:
        """处理 Skill 卸载"""
        if intent.get("success") is False:
            return {"type": "skill_uninstall", "success": False, "error": intent.get("error")}

        result = self.skill_manager.uninstall_skill(name=intent["name"])
        return {"type": "skill_uninstall", **result}

    def summary(self) -> Dict[str, Any]:
        """返回 Agent 当前状态摘要"""
        return {
            "name": self.name,
            "tools": {
                "count": len(self.tool_registry),
                "names": [t.name for t in self.tool_registry.list_all()],
            },
            "mcp": {
                "servers": [s.name for s in self.mcp_registry.list_servers()],
                "clients": [c.transport for c in self.mcp_registry.list_clients()],
            },
            "skills": {
                "count": len(self.skill_registry),
                "names": [s.name for s in self.skill_registry.list_all()],
            },
            "llm_configured": self._llm_callback is not None,
        }