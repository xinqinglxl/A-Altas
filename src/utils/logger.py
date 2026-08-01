"""
统一日志模块。

- 控制台输出：Streamlit 运行时可见
- 文件输出：data/a-altas.log，自动轮转（保留最近 5 个，每个最大 5MB）
- 通过环境变量 AALTAS_LOG_LEVEL 控制级别，默认 DEBUG
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_log_dir() -> Path:
    """获取日志目录，确保存在。"""
    # 从模块路径推导项目根目录
    _dir = Path(__file__).resolve().parent.parent.parent / "data"
    _dir.mkdir(parents=True, exist_ok=True)
    return _dir


LOG_LEVEL = os.environ.get("AALTAS_LOG_LEVEL", "DEBUG").upper()
LOG_FILE = get_log_dir() / "a-altas.log"

# 格式：[2026-08-01 17:30:05] [DEBUG] [module] message
LOG_FORMAT = logging.Formatter(
    "[%(asctime)s] [%(levelname)-5s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# 文件 handler：自动轮转
_file_handler = RotatingFileHandler(
    str(LOG_FILE),
    maxBytes=5 * 1024 * 1024,   # 5 MB
    backupCount=5,
    encoding="utf-8",
)
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(LOG_FORMAT)

# 控制台 handler
_console_handler = logging.StreamHandler()
_console_handler.setLevel(getattr(logging, LOG_LEVEL, logging.DEBUG))
_console_handler.setFormatter(LOG_FORMAT)


def get_logger(name: str) -> logging.Logger:
    """
    获取指定模块的 logger。

    用法：
        from src.utils.logger import get_logger
        logger = get_logger(__name__)
        logger.debug("一些调试信息")
        logger.info("关键流程节点")
        logger.warning("需要注意的情况")
        logger.error("出错啦", exc_info=True)
    """
    _logger = logging.getLogger(name)
    _logger.setLevel(logging.DEBUG)

    # 避免重复添加 handler
    if not _logger.handlers:
        _logger.addHandler(_file_handler)
        _logger.addHandler(_console_handler)
        _logger.propagate = False  # 不往根 logger 传递，避免重复

    return _logger


# 根 logger 也配上 handler，防止某些库的日志丢失
_root = logging.getLogger()
_root.setLevel(logging.DEBUG)
if not _root.handlers:
    _root.addHandler(_file_handler)
    _root.addHandler(_console_handler)
