"""日志配置模块

初始化日志系统：
- 所有日志 → xiaohua/logs/configbot.log
- 错误日志 → xiaohua/logs/configbot_error.log
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> None:
    """初始化日志系统

    Args:
        level: 日志级别，默认 INFO
        max_bytes: 单个日志文件最大字节数
        backup_count: 保留的历史日志文件数
    """
    # 从 configbot/logger/__init__.py 向上三层找到项目根目录
    project_root = Path(__file__).resolve().parent.parent.parent
    logs_dir = project_root / "xiaohua" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # 根 Logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 清除已有的 handler（避免重复添加）
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── 全量日志 Handler ──
    all_handler = RotatingFileHandler(
        logs_dir / "configbot.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    all_handler.setLevel(level)
    all_handler.setFormatter(formatter)
    root_logger.addHandler(all_handler)

    # ── 错误日志 Handler ──
    error_handler = RotatingFileHandler(
        logs_dir / "configbot_error.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)

    # ── 控制台 Handler ──
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    root_logger.info("日志系统初始化完成: %s", logs_dir)


# ═══════════════════════════════════════════════════════════════
# 便捷输出函数：同时 print + 写入日志
# ═══════════════════════════════════════════════════════════════

_log = logging.getLogger("configbot")


def log_info(message: str, level: str = "info") -> None:
    """同时输出到控制台（print）和写入日志文件。

    统一替代项目中的 print()，确保用户可见输出 + 持久化存储。

    Args:
        message: 要输出的消息文本。
        level: 日志级别，可选 "debug" / "info" / "warning" / "error"。
    """
    print(message)
    _log_fn = getattr(_log, level, _log.info)
    _log_fn(message)