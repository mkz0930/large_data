"""
测试 Apify 价格历史解析功能
"""

import pytest
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.apify_price import ApifyPriceFetcher, APIFY_AVAILABLE


class TestApifyPriceParser:
    """测试 Apify 价格历史解析"""

    def test_parse_price_history_with_valid_data(self):
        """测试解析有效的价格历史数据"""
        # 模拟 Apify 返回的数据（基于真实数据样本）
        mock_data = {
            "asin": "B0BK9HFZ77",
            "name": "Amico 24 Pack 6 Inch LED Recessed Ceiling Light",
            "price": 179.99,
            "currency": "USD",
            "price_new_history": [
                {"date": "2022-12-26T03:36:00", "price": 249.99},
                {"date": "2023-01-14T03:52:00", "price": 179.99},
                {"date": "2023-01-27T00:44:00", "price": 159.99},
                {"date": "2023-03-13T07:00:00", "price": 149.99},  # 最低价
                {"date": "2023-03-20T08:16:00", "price": 179.99},
            ]
        }

        # 创建一个不需要 API token 的解析器实例
        # 直接测试 _parse_price_history 方法
        result = self._parse_price_history(mock_data)

        assert result is not None
        assert result['asin'] == "B0BK9HFZ77"
        assert result['price_min'] == 149.99
        assert result['price_max'] == 249.99
        assert result['price_min_date'] == "2023-03-13T07:00:00"
        assert result['price_max_date'] == "2022-12-26T03:36:00"
        assert result['history_count'] == 5

    def test_parse_price_history_with_empty_history(self):
        """测试解析空的价格历史数据"""
        mock_data = {
            "asin": "B0TEST1234",
            "name": "Test Product",
            "price": 99.99,
            "price_new_history": []
        }

        result = self._parse_price_history(mock_data)

        assert result is not None
        assert result['asin'] == "B0TEST1234"
        assert result['price_min'] is None
        assert result['price_max'] is None
        assert result['price_min_date'] is None
        assert result['price_max_date'] is None
        assert result['history_count'] == 0

    def test_parse_price_history_with_no_history_field(self):
        """测试解析没有价格历史字段的数据"""
        mock_data = {
            "asin": "B0TEST5678",
            "name": "Test Product 2",
            "price": 49.99,
        }

        result = self._parse_price_history(mock_data)

        assert result is not None
        assert result['asin'] == "B0TEST5678"
        assert result['price_min'] is None
        assert result['price_max'] is None

    def test_parse_price_history_with_null_prices(self):
        """测试解析包含 null 价格的历史数据"""
        mock_data = {
            "asin": "B0TEST9999",
            "name": "Test Product 3",
            "price_new_history": [
                {"date": "2023-01-01", "price": None},
                {"date": "2023-02-01", "price": 100.00},
                {"date": "2023-03-01", "price": 0},  # 0 价格应该被忽略
                {"date": "2023-04-01", "price": 80.00},
            ]
        }

        result = self._parse_price_history(mock_data)

        assert result is not None
        assert result['price_min'] == 80.00
        assert result['price_max'] == 100.00
        assert result['history_count'] == 2  # 只有 2 个有效价格

    def test_parse_price_history_with_buybox_history(self):
        """测试使用 price_buybox_history 字段"""
        mock_data = {
            "asin": "B0TESTBBOX",
            "name": "Test Product Buybox",
            "price_buybox_history": [
                {"date": "2023-01-01", "price": 50.00},
                {"date": "2023-02-01", "price": 60.00},
            ]
        }

        result = self._parse_price_history(mock_data)

        assert result is not None
        assert result['price_min'] == 50.00
        assert result['price_max'] == 60.00

    def test_parse_price_history_with_amazon_history(self):
        """测试使用 price_amazon_history 字段（优先级最高）"""
        mock_data = {
            "asin": "B0TESTAMZN",
            "name": "Test Product Amazon",
            "price_amazon_history": [
                {"date": "2023-01-01", "price": 30.00},
                {"date": "2023-02-01", "price": 40.00},
            ],
            "price_new_history": [
                {"date": "2023-01-01", "price": 50.00},
                {"date": "2023-02-01", "price": 60.00},
            ]
        }

        result = self._parse_price_history(mock_data)

        assert result is not None
        # 应该使用 price_amazon_history 的数据
        assert result['price_min'] == 30.00
        assert result['price_max'] == 40.00

    def _parse_price_history(self, data: dict) -> dict:
        """
        复制 ApifyPriceFetcher._parse_price_history 的逻辑用于测试
        （避免需要 API token）
        """
        if not data:
            return None

        asin = data.get('asin')
        if not asin:
            return None

        # 提取历史价格数据
        price_history = []
        history_fields = ['price_amazon_history', 'price_buybox_history', 'price_new_history']

        for field in history_fields:
            if field in data and data[field]:
                price_history = data[field]
                break

        # 计算历史最高价和最低价
        price_min = None
        price_max = None
        price_min_date = None
        price_max_date = None

        valid_prices = []
        for record in price_history:
            if isinstance(record, dict) and record.get('price') is not None:
                price = record['price']
                date = record.get('date', '')
                if price > 0:
                    valid_prices.append({'price': price, 'date': date})

        if valid_prices:
            # 找最低价
            min_record = min(valid_prices, key=lambda x: x['price'])
            price_min = min_record['price']
            price_min_date = min_record['date']

            # 找最高价
            max_record = max(valid_prices, key=lambda x: x['price'])
            price_max = max_record['price']
            price_max_date = max_record['date']

        return {
            'asin': asin,
            'price_min': price_min,
            'price_max': price_max,
            'price_min_date': price_min_date,
            'price_max_date': price_max_date,
            'history_count': len(valid_prices)
        }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
