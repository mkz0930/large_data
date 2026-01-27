"""
Apify 价格历史获取模块
使用 Apify API 获取亚马逊商品的历史价格数据
支持数据库缓存，最近 20 天内抓取过的数据不再重复抓取

使用 data_summary 中的 ApifyAmazonScraper 实现，通过 REST API 调用
"""

import os
import sys
import logging
from typing import Optional, Dict, List
from pathlib import Path

# 加载环境变量
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent.parent / "data_summary" / ".env"
load_dotenv(env_path)

logger = logging.getLogger(__name__)

# 添加 data_summary 路径以导入 ApifyAmazonScraper
data_summary_path = Path(__file__).parent.parent.parent / "data_summary"
if str(data_summary_path) not in sys.path:
    sys.path.insert(0, str(data_summary_path))

# 尝试导入 ApifyAmazonScraper
APIFY_AVAILABLE = False
ApifyAmazonScraper = None
try:
    from external_apis.apify_scraper import ApifyAmazonScraper
    APIFY_AVAILABLE = True
except ImportError as e:
    logger.warning(f"ApifyAmazonScraper 导入失败: {e}，价格历史功能不可用")

# 导入缓存数据库
from .apify_db import ApifyDB


class ApifyPriceFetcher:
    """使用 Apify API 获取亚马逊商品历史价格"""

    # 默认缓存有效期（天）
    DEFAULT_CACHE_DAYS = 20

    def __init__(self, api_token: Optional[str] = None, cache_days: int = None):
        """
        初始化 Apify 价格获取器

        Args:
            api_token: Apify API token，如果不提供则从环境变量读取
            cache_days: 缓存有效期（天），默认 20 天
        """
        if not APIFY_AVAILABLE:
            raise ImportError("ApifyAmazonScraper 导入失败，请检查 data_summary 项目")

        self.api_token = api_token or os.getenv('APIFY_API_TOKEN')
        if not self.api_token:
            raise ValueError("APIFY_API_TOKEN 未设置，请在 .env 文件中配置")

        # 使用 data_summary 中的 ApifyAmazonScraper
        self.scraper = ApifyAmazonScraper(
            api_token=self.api_token,
            max_concurrent=25,
            rate_limit_delay=0.1,
        )
        self.cache_days = cache_days or self.DEFAULT_CACHE_DAYS
        self.db = ApifyDB()

    def get_price_history(self, asin: str, country: str = "US") -> Optional[Dict]:
        """
        获取单个商品的历史价格数据（优先使用缓存）

        Args:
            asin: 亚马逊商品 ASIN 码
            country: 国家代码 (US, UK, DE, FR, IT, ES, JP, CA 等)

        Returns:
            包含价格历史的字典，如果失败返回 None
        """
        # 检查缓存
        if self.db.is_cached(asin, days=self.cache_days):
            logger.info(f"  [Apify] {asin} 使用缓存数据")
            cached = self.db.get_cached_data(asin)
            if cached:
                return self._format_cached_data(cached)

        try:
            logger.info(f"  [Apify] 获取 {asin} 的历史价格...")

            # 使用 ApifyAmazonScraper 的 get_product_history 方法
            result = self.scraper.get_product_history(
                asin=asin,
                country=country,
                use_cache=False,  # 我们自己管理缓存
            )

            if not result or 'raw_data' not in result:
                logger.warning(f"  [Apify] 未找到 {asin} 的数据")
                return None

            # 保存原始数据到缓存
            raw_data = result['raw_data']
            self.db.save_apify_data(raw_data)

            return self._parse_price_history(raw_data)

        except Exception as e:
            logger.error(f"  [Apify] 获取 {asin} 失败: {e}")
            return None

    def _format_cached_data(self, cached: Dict) -> Dict:
        """将缓存数据格式化为标准输出格式"""
        return {
            'asin': cached.get('asin'),
            'price_min': cached.get('price_min'),
            'price_max': cached.get('price_max'),
            'price_min_date': cached.get('price_min_date'),
            'price_max_date': cached.get('price_max_date'),
            'history_count': 0,  # 缓存数据不保存历史记录数
            'from_cache': True
        }

    def get_multiple_price_history(self, asins: List[str], country: str = "US") -> Dict[str, Dict]:
        """
        批量获取多个商品的历史价格（优先使用缓存）

        Args:
            asins: 商品 ASIN 码列表
            country: 国家代码

        Returns:
            ASIN -> 价格历史数据的映射
        """
        if not asins:
            return {}

        results = {}

        # 1. 先从缓存获取有效数据
        cached_data = self.db.get_cached_data_batch(asins, days=self.cache_days)
        for asin, data in cached_data.items():
            results[asin] = self._format_cached_data(data)

        cached_count = len(cached_data)
        if cached_count > 0:
            logger.info(f"  [Apify] 从缓存获取 {cached_count} 个商品数据")

        # 2. 获取未缓存的 ASIN
        uncached_asins = self.db.get_uncached_asins(asins, days=self.cache_days)

        if not uncached_asins:
            logger.info(f"  [Apify] 所有 {len(asins)} 个商品都有有效缓存")
            return results

        # 3. 从 API 批量获取未缓存的数据
        try:
            logger.info(f"  [Apify] 从 API 获取 {len(uncached_asins)} 个商品的历史价格...")

            # 使用 ApifyAmazonScraper 的批量方法
            batch_results = self.scraper.scrape_products_by_asins(
                asins=uncached_asins,
                country_code=country.lower(),
                use_cache=False,  # 我们自己管理缓存
                show_progress=True,
            )

            # 处理结果
            api_success_count = 0
            for asin, result in zip(uncached_asins, batch_results):
                if result and 'items' in result and result['items']:
                    raw_data = result['items'][0]
                    # 保存到缓存
                    self.db.save_apify_data(raw_data)
                    # 解析结果
                    parsed = self._parse_price_history(raw_data)
                    if parsed and parsed.get('asin'):
                        results[parsed['asin']] = parsed
                        api_success_count += 1

            logger.info(f"  [Apify] 成功获取 {api_success_count} 个商品的价格历史（缓存: {cached_count}, API: {api_success_count}）")

        except Exception as e:
            logger.error(f"  [Apify] 批量获取失败: {e}")

        return results

    def _parse_price_history(self, data: Dict) -> Optional[Dict]:
        """
        解析 Apify 返回的价格历史数据

        Args:
            data: Apify 返回的原始数据

        Returns:
            标准化的价格历史字典
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


def is_apify_available() -> bool:
    """检查 Apify 是否可用"""
    if not APIFY_AVAILABLE:
        return False
    api_token = os.getenv('APIFY_API_TOKEN')
    return bool(api_token)


def get_apify_cache_stats() -> Dict:
    """获取 Apify 缓存统计信息"""
    db = ApifyDB()
    return db.get_cache_stats()


def clean_apify_cache(days: int = 20) -> int:
    """清理过期的 Apify 缓存"""
    db = ApifyDB()
    return db.clean_expired_cache(days)


if __name__ == "__main__":
    # 测试代码
    import sys
    logging.basicConfig(level=logging.INFO)

    if not is_apify_available():
        print("Apify 不可用，请检查配置")
        sys.exit(1)

    fetcher = ApifyPriceFetcher()

    # 测试单个 ASIN
    test_asin = "B0BK9HFZ77"
    print(f"\n测试获取 {test_asin} 的价格历史...")
    result = fetcher.get_price_history(test_asin)
    if result:
        print(f"  最低价: ${result.get('price_min')} ({result.get('price_min_date')})")
        print(f"  最高价: ${result.get('price_max')} ({result.get('price_max_date')})")
    else:
        print("  获取失败")
