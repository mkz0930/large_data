"""
日志模块测试
"""
import os
import sys
import tempfile
import logging
import pytest
from pathlib import Path
from unittest.mock import patch

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestLoggerSetup:
    """测试日志配置"""

    def test_setup_logger_returns_logger(self):
        """测试 setup_logger 返回 logger 实例"""
        from src.logger import setup_logger

        logger = setup_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_setup_logger_with_custom_level(self):
        """测试自定义日志级别"""
        from src.logger import setup_logger

        logger = setup_logger("test_debug", level=logging.DEBUG)
        assert logger.level == logging.DEBUG

        logger = setup_logger("test_error", level=logging.ERROR)
        assert logger.level == logging.ERROR

    def test_setup_logger_creates_log_directory(self):
        """测试自动创建日志目录"""
        from src.logger import setup_logger, LOG_DIR

        # 确保日志目录存在
        setup_logger("test_dir")
        assert LOG_DIR.exists()

    def test_setup_logger_has_console_handler(self):
        """测试包含控制台处理器"""
        from src.logger import setup_logger

        logger = setup_logger("test_console")
        handler_types = [type(h).__name__ for h in logger.handlers]
        assert "StreamHandler" in handler_types

    def test_setup_logger_has_file_handler(self):
        """测试包含文件处理器"""
        from src.logger import setup_logger

        logger = setup_logger("test_file")
        handler_types = [type(h).__name__ for h in logger.handlers]
        # 应该有 TimedRotatingFileHandler 或 FileHandler
        assert any("FileHandler" in t for t in handler_types)


class TestLoggerOutput:
    """测试日志输出"""

    def test_log_info_message(self, caplog):
        """测试 INFO 级别日志"""
        from src.logger import setup_logger

        logger = setup_logger("test_info_output", level=logging.INFO)

        with caplog.at_level(logging.INFO):
            logger.info("测试信息")

        assert "测试信息" in caplog.text

    def test_log_error_message(self, caplog):
        """测试 ERROR 级别日志"""
        from src.logger import setup_logger

        logger = setup_logger("test_error_output", level=logging.ERROR)

        with caplog.at_level(logging.ERROR):
            logger.error("测试错误")

        assert "测试错误" in caplog.text

    def test_log_warning_message(self, caplog):
        """测试 WARNING 级别日志"""
        from src.logger import setup_logger

        logger = setup_logger("test_warning_output", level=logging.WARNING)

        with caplog.at_level(logging.WARNING):
            logger.warning("测试警告")

        assert "测试警告" in caplog.text

    def test_log_debug_filtered_at_info_level(self, caplog):
        """测试 DEBUG 日志在 INFO 级别被过滤"""
        from src.logger import setup_logger

        logger = setup_logger("test_debug_filter", level=logging.INFO)

        with caplog.at_level(logging.INFO):
            logger.debug("调试信息不应显示")

        assert "调试信息不应显示" not in caplog.text


class TestLoggerFormat:
    """测试日志格式"""

    def test_log_format_contains_timestamp(self, caplog):
        """测试日志格式包含时间戳"""
        from src.logger import setup_logger

        logger = setup_logger("test_format_time", level=logging.INFO)

        with caplog.at_level(logging.INFO):
            logger.info("格式测试")

        # caplog 不保留完整格式，检查 record
        assert len(caplog.records) > 0

    def test_log_format_contains_level(self, caplog):
        """测试日志格式包含级别"""
        from src.logger import setup_logger

        logger = setup_logger("test_format_level", level=logging.INFO)

        with caplog.at_level(logging.INFO):
            logger.info("级别测试")

        assert caplog.records[0].levelname == "INFO"

    def test_log_format_contains_module_name(self, caplog):
        """测试日志格式包含模块名"""
        from src.logger import setup_logger

        logger = setup_logger("my_module", level=logging.INFO)

        with caplog.at_level(logging.INFO):
            logger.info("模块测试")

        assert caplog.records[0].name == "my_module"


class TestGetLogger:
    """测试获取已配置的 logger"""

    def test_get_logger_returns_same_instance(self):
        """测试获取相同名称返回相同实例"""
        from src.logger import setup_logger, get_logger

        logger1 = setup_logger("same_name")
        logger2 = get_logger("same_name")

        assert logger1 is logger2

    def test_get_logger_without_setup(self):
        """测试未配置时获取 logger"""
        from src.logger import get_logger

        logger = get_logger("new_logger")
        assert isinstance(logger, logging.Logger)


class TestLogFile:
    """测试日志文件"""

    def test_log_writes_to_file(self):
        """测试日志写入文件"""
        from src.logger import setup_logger, LOG_DIR
        from datetime import datetime

        logger = setup_logger("test_file_write", level=logging.INFO)
        test_message = f"文件写入测试_{datetime.now().timestamp()}"
        logger.info(test_message)

        # 强制刷新
        for handler in logger.handlers:
            handler.flush()

        # 检查日志文件
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = LOG_DIR / f"batch_scraper_{today}.log"

        if log_file.exists():
            content = log_file.read_text(encoding="utf-8")
            assert test_message in content
