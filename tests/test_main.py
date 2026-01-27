"""
main.py 入口测试用例
测试命令行参数解析和模式选择逻辑
"""

import sys
import pytest
import importlib.util
from pathlib import Path
from unittest.mock import patch, MagicMock

# 使用 importlib 直接加载本项目的 main.py，避免与 data_summary/main.py 冲突
PROJECT_ROOT = Path(__file__).parent.parent
MAIN_PATH = PROJECT_ROOT / "main.py"

spec = importlib.util.spec_from_file_location("large_data_main", MAIN_PATH)
large_data_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(large_data_main)

parse_args = large_data_main.parse_args
validate_args = large_data_main.validate_args
load_keywords_from_file = large_data_main.load_keywords_from_file


class TestArgumentParsing:
    """测试命令行参数解析"""

    def test_single_keyword_mode(self):
        """测试单关键词模式参数解析"""
        args = parse_args(['camping'])

        assert args.keyword == 'camping'
        assert args.batch is None
        assert args.country == 'us'
        assert args.max_pages == 100
        assert args.sales_threshold == 10
        assert args.top_categories == 3

    def test_single_keyword_with_options(self):
        """测试单关键词模式带参数"""
        args = parse_args(['hiking', '--max-pages', '50', '--top-categories', '5'])

        assert args.keyword == 'hiking'
        assert args.max_pages == 50
        assert args.top_categories == 5

    def test_batch_mode(self):
        """测试批量模式参数解析"""
        args = parse_args(['--batch', 'keywords.txt'])

        assert args.keyword is None
        assert args.batch == 'keywords.txt'

    def test_batch_mode_short_flag(self):
        """测试批量模式短参数"""
        args = parse_args(['-b', 'keywords.txt'])

        assert args.batch == 'keywords.txt'

    def test_no_argument_error(self):
        """测试无参数时报错"""
        # 无参数应该返回 None 或抛出异常
        args = parse_args([])
        assert args.keyword is None and args.batch is None

    def test_country_option(self):
        """测试国家代码参数"""
        args = parse_args(['camping', '-c', 'uk'])

        assert args.country == 'uk'

    def test_db_path_option(self):
        """测试数据库路径参数"""
        args = parse_args(['camping', '--db-path', 'custom/path.db'])

        assert args.db_path == 'custom/path.db'

    def test_no_sellerspirit_flag(self):
        """测试禁用卖家精灵参数"""
        args = parse_args(['camping', '--no-sellerspirit'])

        assert args.no_sellerspirit is True

    def test_ai_filter_default_enabled(self):
        """测试 AI 筛选默认启用"""
        args = parse_args(['camping'])

        assert not hasattr(args, 'ai_filter') or not args.no_ai_filter

    def test_no_ai_filter_flag(self):
        """测试禁用 AI 筛选参数"""
        args = parse_args(['camping', '--no-ai-filter'])

        assert args.no_ai_filter is True

    def test_ai_limit_with_value(self):
        """测试 AI 筛选带数量限制"""
        args = parse_args(['camping', '--ai-limit', '50'])

        assert args.ai_limit == 50

    def test_ai_limit_default(self):
        """测试 AI 筛选数量默认值"""
        args = parse_args(['camping'])

        assert args.ai_limit == 100


class TestModeSelection:
    """测试模式选择逻辑"""

    def test_validate_args_single_keyword(self):
        """测试单关键词模式验证"""
        args = parse_args(['camping'])
        mode, error = validate_args(args)

        assert mode == 'single'
        assert error is None

    def test_validate_args_batch_mode(self, tmp_path):
        """测试批量模式验证"""
        # 创建临时关键词文件
        keywords_file = tmp_path / "keywords.txt"
        keywords_file.write_text("camping\n", encoding='utf-8')

        args = parse_args(['--batch', str(keywords_file)])
        mode, error = validate_args(args)

        assert mode == 'batch'
        assert error is None

    def test_validate_args_batch_file_not_found(self):
        """测试批量模式文件不存在"""
        args = parse_args(['--batch', 'nonexistent.txt'])
        mode, error = validate_args(args)

        assert mode is None
        assert error is not None

    def test_validate_args_no_input(self):
        """测试无输入时返回错误"""
        args = parse_args([])
        mode, error = validate_args(args)

        assert mode is None
        assert error is not None


class TestKeywordFileLoading:
    """测试关键词文件加载"""

    def test_load_keywords_from_file(self, tmp_path):
        """测试从文件加载关键词"""
        # 创建临时关键词文件
        keywords_file = tmp_path / "keywords.txt"
        keywords_file.write_text("camping\nhiking\n# comment line\nbackpack\n", encoding='utf-8')

        keywords = load_keywords_from_file(str(keywords_file))

        assert keywords == ['camping', 'hiking', 'backpack']

    def test_load_keywords_empty_file(self, tmp_path):
        """测试空文件"""
        keywords_file = tmp_path / "empty.txt"
        keywords_file.write_text("", encoding='utf-8')

        keywords = load_keywords_from_file(str(keywords_file))

        assert keywords == []

    def test_load_keywords_file_not_found(self):
        """测试文件不存在"""
        with pytest.raises(FileNotFoundError):
            load_keywords_from_file('nonexistent.txt')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
