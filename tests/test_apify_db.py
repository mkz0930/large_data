"""
ApifyDB 数据库测试
"""

import pytest
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestApifyDB:
    """ApifyDB 测试类"""

    @pytest.fixture
    def db(self, tmp_path):
        """创建临时数据库"""
        from src.apify_db import ApifyDB
        db_path = tmp_path / "test_apify.db"
        return ApifyDB(str(db_path))

    @pytest.fixture
    def sample_apify_data(self):
        """示例 Apify 返回数据"""
        return {
            "data_captured_at": "2026-01-23T05:36:55.942247Z",
            "last_updated": "2026-01-23T04:16:00",
            "tracked_since": "2022-12-26T03:36:00",
            "listed_at": "2022-10-24T00:00:00Z",
            "country": "us",
            "asin": "B0BK9HFZ77",
            "name": "Amico 24 Pack LED Light",
            "brand": "Amico",
            "rating": 4.7,
            "n_reviews": 2270,
            "main_category": "Diy",
            "primary_category": "Tools & Home Improvement",
            "sub_categories": ["Recessed Lighting Housing & Trim Kits"],
            "seller_type": "FBA",
            "in_stock": True,
            "currency": "USD",
            "list_price": 179.99,
            "price": 179.99,
            "price_new": 179.99,
            "price_buybox": 179.99,
            "price_prime_exclusive": 109.98,
            "price_new_history": [
                {"date": "2022-12-26T03:36:00", "price": 249.99},
                {"date": "2023-01-14T03:52:00", "price": 179.99},
                {"date": "2023-08-07T07:28:00", "price": 139.99},  # 最低价
            ]
        }

    def test_init_creates_table(self, db):
        """测试初始化创建表"""
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='apify_cache'"
            )
            assert cursor.fetchone() is not None

    def test_save_apify_data(self, db, sample_apify_data):
        """测试保存 Apify 数据"""
        result = db.save_apify_data(sample_apify_data)
        assert result is True

        # 验证数据已保存
        data = db.get_cached_data("B0BK9HFZ77")
        assert data is not None
        assert data["asin"] == "B0BK9HFZ77"
        assert data["brand"] == "Amico"
        assert data["price"] == 179.99

    def test_save_calculates_price_min_max(self, db, sample_apify_data):
        """测试保存时计算历史最低价和最高价"""
        db.save_apify_data(sample_apify_data)
        data = db.get_cached_data("B0BK9HFZ77")

        assert data["price_min"] == 139.99
        assert data["price_max"] == 249.99

    def test_batch_save_apify_data(self, db, sample_apify_data):
        """测试批量保存"""
        data_list = [
            sample_apify_data,
            {**sample_apify_data, "asin": "B0TEST1234", "name": "Test Product"}
        ]
        count = db.batch_save_apify_data(data_list)
        assert count == 2

    def test_is_cached_within_days(self, db, sample_apify_data):
        """测试缓存有效期检查（20天内）"""
        db.save_apify_data(sample_apify_data)

        # 刚保存的数据应该在缓存有效期内
        assert db.is_cached("B0BK9HFZ77", days=20) is True

        # 不存在的 ASIN 应该返回 False
        assert db.is_cached("B0NOTEXIST", days=20) is False

    def test_is_cached_expired(self, db, sample_apify_data):
        """测试缓存过期"""
        db.save_apify_data(sample_apify_data)

        # 手动更新 created_at 为 25 天前
        with sqlite3.connect(db.db_path) as conn:
            old_date = (datetime.now() - timedelta(days=25)).strftime('%Y-%m-%d %H:%M:%S')
            conn.execute(
                "UPDATE apify_cache SET created_at = ? WHERE asin = ?",
                (old_date, "B0BK9HFZ77")
            )
            conn.commit()

        # 超过 20 天应该返回 False
        assert db.is_cached("B0BK9HFZ77", days=20) is False

    def test_get_uncached_asins(self, db, sample_apify_data):
        """测试获取未缓存的 ASIN 列表"""
        db.save_apify_data(sample_apify_data)

        asins = ["B0BK9HFZ77", "B0NEW12345", "B0NEW67890"]
        uncached = db.get_uncached_asins(asins, days=20)

        assert "B0BK9HFZ77" not in uncached
        assert "B0NEW12345" in uncached
        assert "B0NEW67890" in uncached
        assert len(uncached) == 2

    def test_get_cached_data_batch(self, db, sample_apify_data):
        """测试批量获取缓存数据"""
        data_list = [
            sample_apify_data,
            {**sample_apify_data, "asin": "B0TEST1234", "price": 99.99}
        ]
        db.batch_save_apify_data(data_list)

        cached = db.get_cached_data_batch(["B0BK9HFZ77", "B0TEST1234", "B0NOTEXIST"])
        assert len(cached) == 2
        assert "B0BK9HFZ77" in cached
        assert "B0TEST1234" in cached
        assert cached["B0TEST1234"]["price"] == 99.99

    def test_update_existing_data(self, db, sample_apify_data):
        """测试更新已存在的数据"""
        db.save_apify_data(sample_apify_data)

        # 更新价格
        updated_data = {**sample_apify_data, "price": 149.99}
        db.save_apify_data(updated_data)

        data = db.get_cached_data("B0BK9HFZ77")
        assert data["price"] == 149.99

    def test_get_cache_stats(self, db, sample_apify_data):
        """测试获取缓存统计"""
        db.batch_save_apify_data([
            sample_apify_data,
            {**sample_apify_data, "asin": "B0TEST1234"}
        ])

        stats = db.get_cache_stats()
        assert stats["total"] == 2
        assert stats["valid_count"] >= 0

    def test_clean_expired_cache(self, db, sample_apify_data):
        """测试清理过期缓存"""
        db.save_apify_data(sample_apify_data)

        # 手动设置为 30 天前
        with sqlite3.connect(db.db_path) as conn:
            old_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
            conn.execute(
                "UPDATE apify_cache SET created_at = ? WHERE asin = ?",
                (old_date, "B0BK9HFZ77")
            )
            conn.commit()

        # 清理 20 天前的数据
        deleted = db.clean_expired_cache(days=20)
        assert deleted == 1

        # 确认已删除
        assert db.get_cached_data("B0BK9HFZ77") is None
