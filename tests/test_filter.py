"""
筛选功能测试用例
测试分类筛选和销量筛选逻辑
"""

import pytest
import sqlite3
from pathlib import Path
import sys

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database import BatchScraperDB


class TestCategoryFilter:
    """测试分类筛选功能"""

    @pytest.fixture
    def db(self, tmp_path):
        """创建临时数据库"""
        db_path = tmp_path / "test.db"
        return BatchScraperDB(str(db_path))

    @pytest.fixture
    def sample_data(self, db):
        """插入测试数据"""
        keyword = "camping"
        asins = [
            # 分类 A: 5 个产品
            {'asin': 'A001', 'category_sub': 'Tents', 'sales_volume': 50},
            {'asin': 'A002', 'category_sub': 'Tents', 'sales_volume': 80},
            {'asin': 'A003', 'category_sub': 'Tents', 'sales_volume': 120},
            {'asin': 'A004', 'category_sub': 'Tents', 'sales_volume': 30},
            {'asin': 'A005', 'category_sub': 'Tents', 'sales_volume': 200},
            # 分类 B: 3 个产品
            {'asin': 'B001', 'category_sub': 'Sleeping Bags', 'sales_volume': 40},
            {'asin': 'B002', 'category_sub': 'Sleeping Bags', 'sales_volume': 150},
            {'asin': 'B003', 'category_sub': 'Sleeping Bags', 'sales_volume': 60},
            # 分类 C: 2 个产品
            {'asin': 'C001', 'category_sub': 'Backpacks', 'sales_volume': 90},
            {'asin': 'C002', 'category_sub': 'Backpacks', 'sales_volume': 10},
            # 无分类: 1 个产品
            {'asin': 'D001', 'category_sub': None, 'sales_volume': 25},
        ]
        db.save_asins(asins, keyword, 'keyword_search', keyword)
        return keyword

    def test_get_category_distribution(self, db, sample_data):
        """测试获取分类分布"""
        keyword = sample_data
        distribution = db.get_category_distribution(keyword)

        assert len(distribution) == 3
        assert distribution[0]['category'] == 'Tents'
        assert distribution[0]['count'] == 5
        assert distribution[1]['category'] == 'Sleeping Bags'
        assert distribution[1]['count'] == 3
        assert distribution[2]['category'] == 'Backpacks'
        assert distribution[2]['count'] == 2

    def test_filter_by_top_category(self, db, sample_data):
        """测试分类筛选 - 只保留最大分类"""
        keyword = sample_data

        # 筛选前总数
        total_before = db.get_asin_count(keyword)
        assert total_before == 11

        # 执行筛选
        result = db.filter_by_top_category(keyword)

        assert result['total'] == 11
        assert result['top_category'] == 'Tents'
        assert result['top_category_count'] == 5
        assert result['kept'] == 5
        assert result['removed'] == 6

        # 验证筛选后只剩 Tents 分类
        total_after = db.get_asin_count(keyword)
        assert total_after == 5

    def test_filter_by_top_category_empty(self, db):
        """测试分类筛选 - 空数据"""
        result = db.filter_by_top_category("nonexistent")

        assert result['total'] == 0
        assert result['top_category'] is None
        assert result['kept'] == 0
        assert result['removed'] == 0


class TestSalesFilter:
    """测试销量筛选功能"""

    @pytest.fixture
    def db(self, tmp_path):
        """创建临时数据库"""
        db_path = tmp_path / "test.db"
        return BatchScraperDB(str(db_path))

    @pytest.fixture
    def sample_data(self, db):
        """插入测试数据"""
        keyword = "camping"
        asins = [
            {'asin': 'A001', 'category_sub': 'Tents', 'sales_volume': 50},
            {'asin': 'A002', 'category_sub': 'Tents', 'sales_volume': 100},  # 边界值
            {'asin': 'A003', 'category_sub': 'Tents', 'sales_volume': 101},  # 超过阈值
            {'asin': 'A004', 'category_sub': 'Tents', 'sales_volume': 200},
            {'asin': 'A005', 'category_sub': 'Tents', 'sales_volume': 0},    # 无销量数据
            {'asin': 'A006', 'category_sub': 'Tents', 'sales_volume': None}, # NULL
        ]
        db.save_asins(asins, keyword, 'keyword_search', keyword)
        return keyword

    def test_get_sales_distribution(self, db, sample_data):
        """测试获取销量分布"""
        keyword = sample_data
        distribution = db.get_sales_distribution(keyword, max_sales=100)

        assert distribution['no_data'] == 2  # sales_volume = 0 或 NULL
        assert distribution['under_threshold'] == 2  # 50, 100
        assert distribution['over_threshold'] == 2  # 101, 200
        assert distribution['total'] == 6

    def test_filter_low_sales_asins(self, db, sample_data):
        """测试销量筛选 - 剔除销量 > 100"""
        keyword = sample_data

        # 执行筛选
        result = db.filter_low_sales_asins(keyword, max_sales=100)

        assert result['total'] == 6
        assert result['removed'] == 2  # 101, 200
        assert result['kept'] == 4  # 50, 100, 0, NULL

        # 验证筛选后数量
        total_after = db.get_asin_count(keyword)
        assert total_after == 4

    def test_filter_sales_boundary(self, db, sample_data):
        """测试销量筛选边界值 - 销量=100 应该保留"""
        keyword = sample_data

        # 执行筛选
        db.filter_low_sales_asins(keyword, max_sales=100)

        # 验证 sales_volume=100 的记录被保留
        with sqlite3.connect(str(db.db_path)) as conn:
            cursor = conn.execute(
                "SELECT asin FROM asins WHERE keyword = ? AND sales_volume = 100",
                (keyword,)
            )
            rows = cursor.fetchall()
            assert len(rows) == 1
            assert rows[0][0] == 'A002'


class TestCombinedFilter:
    """测试组合筛选流程"""

    @pytest.fixture
    def db(self, tmp_path):
        """创建临时数据库"""
        db_path = tmp_path / "test.db"
        return BatchScraperDB(str(db_path))

    @pytest.fixture
    def sample_data(self, db):
        """插入测试数据"""
        keyword = "camping"
        asins = [
            # Tents 分类: 5 个
            {'asin': 'A001', 'category_sub': 'Tents', 'sales_volume': 50},
            {'asin': 'A002', 'category_sub': 'Tents', 'sales_volume': 80},
            {'asin': 'A003', 'category_sub': 'Tents', 'sales_volume': 120},  # 会被销量筛选删除
            {'asin': 'A004', 'category_sub': 'Tents', 'sales_volume': 30},
            {'asin': 'A005', 'category_sub': 'Tents', 'sales_volume': 200},  # 会被销量筛选删除
            # Sleeping Bags 分类: 3 个 (会被分类筛选删除)
            {'asin': 'B001', 'category_sub': 'Sleeping Bags', 'sales_volume': 40},
            {'asin': 'B002', 'category_sub': 'Sleeping Bags', 'sales_volume': 150},
            {'asin': 'B003', 'category_sub': 'Sleeping Bags', 'sales_volume': 60},
        ]
        db.save_asins(asins, keyword, 'keyword_search', keyword)
        return keyword

    def test_combined_filter_flow(self, db, sample_data):
        """测试组合筛选流程：先分类筛选，再销量筛选"""
        keyword = sample_data

        # 初始数量
        assert db.get_asin_count(keyword) == 8

        # 步骤1: 分类筛选 - 只保留 Tents (5个)
        cat_result = db.filter_by_top_category(keyword)
        assert cat_result['top_category'] == 'Tents'
        assert cat_result['kept'] == 5
        assert db.get_asin_count(keyword) == 5

        # 步骤2: 销量筛选 - 剔除销量 > 100 (删除 A003, A005)
        sales_result = db.filter_low_sales_asins(keyword, max_sales=100)
        assert sales_result['removed'] == 2
        assert sales_result['kept'] == 3

        # 最终结果: 3 个 ASIN (A001, A002, A004)
        assert db.get_asin_count(keyword) == 3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
