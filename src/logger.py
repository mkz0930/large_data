"""
统一日志模块

提供项目级别的日志配置，支持：
- 同时输出到控制台和文件
- 日志文件按日期轮转
- 统一的日志格式
"""
import logging
import sys
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

# 日志目录
LOG_DIR = Path(__file__).parent.parent / "logs"

# 日志格式
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 已配置的 logger 缓存
_loggers: dict[str, logging.Logger] = {}


def setup_logger(
    name: str,
    level: int = logging.INFO,
    log_to_file: bool = True,
    log_to_console: bool = True,
) -> logging.Logger:
    """
    配置并返回 logger 实例

    Args:
        name: logger 名称（通常是模块名）
        level: 日志级别，默认 INFO
        log_to_file: 是否输出到文件，默认 True
        log_to_console: 是否输出到控制台，默认 True

    Returns:
        配置好的 logger 实例
    """
    # 如果已配置，直接返回
    if name in _loggers:
        return _loggers[name]

    # 创建 logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 清除已有的 handlers（避免重复添加）
    logger.handlers.clear()

    # 创建格式器
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    # 添加控制台处理器
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # 添加文件处理器
    if log_to_file:
        # 确保日志目录存在
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        # 日志文件名：batch_scraper_YYYY-MM-DD.log
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = LOG_DIR / f"batch_scraper_{today}.log"

        file_handler = TimedRotatingFileHandler(
            log_file,
            when="midnight",
            interval=1,
            backupCount=30,  # 保留30天
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # 缓存 logger
    _loggers[name] = logger

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    获取已配置的 logger，如果不存在则创建默认配置

    Args:
        name: logger 名称

    Returns:
        logger 实例
    """
    if name in _loggers:
        return _loggers[name]

    # 返回标准 logging 的 logger（未配置）
    return logging.getLogger(name)
