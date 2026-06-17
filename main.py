"""ConfigBot 入口

演示 Agent 的完整使用流程，包括：
- 内置工具调用
- MCP 工具调用
- Skill 执行
- 扩展新工具/Skill 的方式
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中，支持直接点击运行按钮
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from configbot.agent import Agent
from configbot.tools import BaseTool, ToolExecResult
from configbot.mcp import MCPServer, MCPResponse, MCPTool
from configbot.skills import BaseSkill, SkillCategory, SkillExecResult


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

    async def execute(self, message: str) -> ToolExecResult:
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

    async def execute(self, expression: str) -> ToolExecResult:
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

    async def execute(self, context, tool_executor, mcp_executor) -> SkillExecResult:
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
# 主函数
# ═══════════════════════════════════════════════════════════════

async def demo_basic():
    """演示基础功能"""
    print("=" * 60)
    print("ConfigBot Demo - 基础功能")
    print("=" * 60)

    agent = Agent()
    summary = agent.summary()
    print(f"\nAgent 状态: {json.dumps(summary, ensure_ascii=False, indent=2)}")


async def demo_tool_call():
    """演示内置工具调用"""
    print("\n" + "=" * 60)
    print("Demo 1: 内置工具调用")
    print("=" * 60)

    agent = Agent()
    agent.register_tool(EchoTool())

    # 调用 echo 工具
    result = await agent.call_tool("echo", message="Hello ConfigBot!")
    print(f"  Echo: {result.data}")

    # 调用 calculator 工具
    agent.register_tool(CalculatorTool())
    result = await agent.call_tool("calculator", expression="2 + 3 * 4")
    print(f"  Calculator(2+3*4): {result.data}")

    # 列出目录
    result = await agent.call_tool("list_dir", dir_path=".")
    print(f"  ListDir:\n{result.data}")


async def demo_mcp_call():
    """演示 MCP 工具调用"""
    print("\n" + "=" * 60)
    print("Demo 2: MCP 工具调用")
    print("=" * 60)

    agent = Agent()
    agent.register_mcp_server(WeatherMCPServer())

    # MCP 天气查询
    result = await agent.call_mcp("weather", "get_weather", city="北京")
    print(f"  天气查询: {json.dumps(result.data, ensure_ascii=False)}")

    result = await agent.call_mcp("weather", "get_forecast", city="上海", days=3)
    print(f"  天气预报: {json.dumps(result.data, ensure_ascii=False)}")

    # MCP 文件系统
    result = await agent.call_mcp("filesystem", "fs_exists", path=".")
    print(f"  文件系统检查: {json.dumps(result.data, ensure_ascii=False)}")


async def demo_skill():
    """演示 Skill 执行"""
    print("\n" + "=" * 60)
    print("Demo 3: Skill 执行")
    print("=" * 60)

    agent = Agent()
    agent.register_skill(CodeStatsSkill())

    # 审查 main.py
    result = await agent.call_skill("code_review", {"file_path": __file__})
    if result.success:
        report = result.data
        print(f"  代码审查: {report['file']}")
        print(f"    行数: {report['total_lines']}")
        print(f"    评分: {report['score']}")
        print(f"    问题: {len(report['issues'])} 个")
    else:
        print(f"  错误: {result.error}")

    # 安全审查
    result = await agent.call_skill("security_review", {"file_path": __file__})
    if result.success:
        report = result.data
        print(f"\n  安全审查: {report['file']}")
        print(f"    风险等级: {report['risk_level']}")
        print(f"    发现: {report['summary']}")
    else:
        print(f"  错误: {result.error}")

    # 代码统计
    result = await agent.call_skill("code_stats", {"file_path": __file__})
    if result.success:
        stats = result.data
        print(f"\n  代码统计: {json.dumps(stats, ensure_ascii=False, indent=4)}")


async def demo_intent_routing():
    """演示意图路由"""
    print("\n" + "=" * 60)
    print("Demo 4: 意图路由")
    print("=" * 60)

    agent = Agent()

    # 自动路由到 skill
    result = await agent.run("帮我审查代码", {"file_path": __file__})
    print(f"  输入: '帮我审查代码' -> 路由到: {result['type']}/{result.get('skill_name', '')}")

    result = await agent.run("扫描安全漏洞", {"file_path": __file__})
    print(f"  输入: '扫描安全漏洞' -> 路由到: {result['type']}/{result.get('skill_name', '')}")

    # 查询
    result = await agent.run("你能做什么？")
    print(f"  输入: '你能做什么？' -> {result['type']}")


async def demo_new_tools():
    """演示新增工具（file/web/system/code 分类）"""
    print("\n" + "=" * 60)
    print("Demo 5: 新增工具（按分类）")
    print("=" * 60)

    agent = Agent()

    # ── file 类 ──
    print("\n  [file 类]")
    result = await agent.call_tool("file_info", file_path=__file__)
    if result.success:
        info = result.data
        print(f"    file_info: {info['name']} ({info['size_human']})")
    result = await agent.call_tool("delete_file", file_path="./_test_temp.txt")
    print(f"    delete_file: {result.data if result.success else result.error}")

    # ── web 类 ──
    print("\n  [web 类]")
    result = await agent.call_tool("http_post", url="http://httpbin.org/post", body='{"test": "hello"}')
    print(f"    http_post: {'成功' if result.success else result.error}")

    # ── system 类 ──
    print("\n  [system 类]")
    result = await agent.call_tool("get_env", key="USERNAME")
    print(f"    get_env(USERNAME): {result.data if result.success else result.error}")

    # ── code 类 ──
    print("\n  [code 类]")
    result = await agent.call_tool("json_format", json_str='{"name":"configbot","version":"0.1.0"}', indent=2)
    print(f"    json_format:\n{result.data}")
    result = await agent.call_tool("text_template", template="Hello ${name}, version ${ver}", variables={"name": "ConfigBot", "ver": "1.0"})
    print(f"    text_template: {result.data}")


async def demo_external_skills():
    """演示外部 Skills 自动加载和动态生效（xiaohua/skills/）"""
    print("\n" + "=" * 60)
    print("Demo 6: 外部 Skills 自动加载与动态生效")
    print("=" * 60)

    agent = Agent()

    # 1. 展示自动加载的外部技能
    external = agent.skill_registry.find_by_keyword("")
    print(f"\n  [自动加载] Agent 启动时自动加载了 {len(external)} 个技能:")
    for s in external:
        print(f"    - {s.name}: {s.description}")

    # 2. 通过 "skill:技能名" 格式直接调用
    print("\n  [动态调用] 使用 'skill:技能名' 格式触发：")

    # 2.1 JSON 验证
    print("\n  --- json_validator ---")
    result = await agent.run("skill:json_validator", {
        "json_text": '{"name":"configbot","version":"0.1.0","tools":13}',
        "action": "format",
    })
    if result["success"]:
        print(f"    验证: {result['data']['stats']}")
    else:
        print(f"    失败: {result.get('error')}")

    # 2.2 CSV 转换
    print("\n  --- csv_converter ---")
    result = await agent.run("skill:csv_converter", {
        "csv_text": "name,version,type\nconfigbot,0.1.0,agent\nmcp_server,1.0.0,service",
    })
    if result["success"]:
        print(f"    转换: {result['data']['total']} 条记录")
        print(f"    列: {result['data']['columns']}")
    else:
        print(f"    失败: {result.get('error')}")

    # 2.3 文本统计
    print("\n  --- text_stats ---")
    result = await agent.run("skill:text_stats", {
        "text": "Hello World! ConfigBot 是一个 AI Agent 框架，支持工具链和技能扩展。\nHello again!",
    })
    if result["success"]:
        print(f"    统计: 字符={result['data']['chars_total']}, "
              f"词数={result['data']['words']}, "
              f"语言={result['data']['language']}")
        print(f"    高频词: {result['data']['top_words'][:3]}")
    else:
        print(f"    失败: {result.get('error')}")

    # 2.4 数据去重
    print("\n  --- data_deduplicator ---")
    result = await agent.run("skill:data_deduplicator", {
        "items": ["apple", "banana", "Apple", "orange", "banana", "grape"],
        "ignore_case": True,
        "mode": "preserve_order",
    })
    if result["success"]:
        print(f"    去重: {result['data']['original_count']} -> "
              f"{result['data']['unique_count']} (移除 {result['data']['duplicates_removed']})")
        print(f"    结果: {result['data']['unique_items']}")
    else:
        print(f"    失败: {result.get('error')}")

    # 2.5 文件备份
    print("\n  --- file_backup ---")
    test_file = Path(__file__).parent / "_test_backup.txt"
    test_file.write_text("Hello ConfigBot Backup!", encoding="utf-8")
    result = await agent.run("skill:file_backup", {
        "file_path": str(test_file),
    })
    if result["success"]:
        print(f"    备份: {result['data']['source']} -> {result['data']['backup_name']}")
        Path(result["data"]["backup"]).unlink(missing_ok=True)
    else:
        print(f"    失败: {result.get('error')}")
    test_file.unlink(missing_ok=True)

    # 2.6 日志分析
    print("\n  --- log_analyzer ---")
    temp_log = Path(__file__).parent / "_test_sample.log"
    temp_log.write_text("""2026-06-10 INFO Server started
2026-06-10 DEBUG Loading config
2026-06-10 WARN Config file not found, using defaults
2026-06-10 INFO Listening on port 8080
2026-06-10 ERROR Connection refused to database
2026-06-10 ERROR Timeout while fetching data
2026-06-10 INFO Retrying connection
2026-06-10 WARN High memory usage detected
""")
    result = await agent.run("skill:log_analyzer", {"file_path": str(temp_log)})
    if result["success"]:
        print(f"    分析: {result['data']['file']}")
        print(f"    健康度: {result['data']['health']}")
        print(f"    统计: {result['data']['level_summary']}")
    else:
        print(f"    失败: {result.get('error')}")
    temp_log.unlink(missing_ok=True)

    # 2.7 翻译
    print("\n  --- text_translator ---")
    result = await agent.run("skill:text_translator", {
        "text": "hello world error not found",
        "target_lang": "zh",
    })
    if result["success"]:
        print(f"    翻译: {result['data']['original']} -> {result['data']['translated']}")

    # 2.8 报告生成
    print("\n  --- report_generator ---")
    result = await agent.run("skill:report_generator", {
        "title": "技能总览",
        "data": {"内置技能": "2", "外部技能": "8", "总工具数": "13"},
        "format": "markdown",
    })
    if result["success"]:
        # 只显示前几行
        lines = result["data"].split("\n")[:5]
        print(f"    报告:\n      " + "\n      ".join(lines))

    # 3. 演示动态重载
    print("\n\n  [动态重载] 新增技能文件后无需重启:")
    print("    1. 将新的 skill.py 文件放入 xiaohua/skills/ 目录")
    print("    2. 调用 agent.reload_external_skills()")
    print("    3. 新技能即可通过 'skill:技能名' 调用")
    print(f"    当前技能总数: {len(agent.skill_registry)}")


async def demo_skill_lifecycle():
    """演示 Skill 生命周期管理：创建 / 进化 / 卸载"""
    print("\n" + "=" * 60)
    print("Demo 7: Skill 生命周期管理（创建/进化/卸载）")
    print("=" * 60)

    agent = Agent()

    # ── 1. 创建 Skill ──
    print("\n  [1. 创建 Skill] 通过聊天指令自动生成 Skill 文件并安装")
    print("    指令: '帮我生成一个skill，名字叫data_backup，用来做数据备份'")

    result = await agent.run(
        "帮我生成一个skill，名字叫data_backup，用来做数据备份",
        {
            "category": "data",
            "requires_tools": ["read_file", "file_info"],
            "context_keys": ["file_path"],
        },
    )
    if result["success"]:
        print(f"    创建成功: {result.get('skill_name')}")
        print(f"    文件路径: {result.get('file_path')}")
        # 查看源码
        source = agent.skill_manager.get_skill_source("data_backup")
        if source:
            lines = source.split("\n")
            print(f"    生成代码: {len(lines)} 行")
            print(f"      类名: {_snake_to_camel('data_backup')}Skill")
    else:
        print(f"    创建失败: {result.get('error')}")

    # ── 2. 调用新创建的 Skill ──
    print("\n  [2. 调用新 Skill] 验证新创建的 Skill 是否可用")
    test_file = Path(__file__).parent / "_test_skill_data.txt"
    test_file.write_text("line1\nline2\nline3", encoding="utf-8")

    result = await agent.run("skill:data_backup", {"file_path": str(test_file)})
    if result["success"]:
        print(f"    执行成功: {result['data'].get('result', 'ok')}")
    else:
        print(f"    执行结果: {result.get('error', 'ok')}")

    # ── 3. 进化 Skill ──
    print("\n  [3. 进化 Skill] 通过聊天指令优化已有 Skill")
    print("    指令: '优化skill data_backup，增加压缩功能和验证功能'")

    result = await agent.run(
        "优化skill data_backup，增加压缩功能和验证功能",
        {
            "new_description": "数据备份 Skill（支持压缩和验证）",
            "new_requires_tools": ["read_file", "file_info", "list_dir"],
        },
    )
    if result["success"]:
        print(f"    进化成功: {result.get('skill_name')}")
        print(f"    版本: {result.get('old_version')} → {result.get('new_version')}")
    else:
        print(f"    进化失败: {result.get('error')}")

    # ── 4. 查看 Skill 列表 ──
    print("\n  [4. 查看已安装 Skill]")
    skills = agent.skill_manager.list_installable_skills()
    for s in skills:
        marker = " [文件]" if s["is_file"] else " [内置]"
        print(f"    - {s['name']} v{s['version']}: {s['description']}{marker}")

    # ── 5. 卸载 Skill ──
    print("\n  [5. 卸载 Skill] 通过聊天指令卸载 Skill")
    print("    指令: '卸载skill data_backup'")

    result = await agent.run("卸载skill data_backup")
    if result["success"]:
        print(f"    卸载成功: {result.get('message')}")
        print(f"    删除文件: {result.get('deleted_files')}")
    else:
        print(f"    卸载失败: {result.get('error')}")

    # 验证已卸载
    exists = agent.skill_registry.get("data_backup")
    print(f"    验证: data_backup {'仍存在' if exists else '已移除'}")

    test_file.unlink(missing_ok=True)


def _snake_to_camel(name: str) -> str:
    """snake_case → CamelCase"""
    return "".join(w.capitalize() for w in name.split("_"))


async def main():
    """主入口"""
    await demo_basic()
    await demo_tool_call()
    await demo_mcp_call()
    await demo_skill()
    await demo_intent_routing()
    await demo_new_tools()
    await demo_external_skills()
    await demo_skill_lifecycle()

    print("\n" + "=" * 60)
    print("所有 Demo 执行完毕！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())