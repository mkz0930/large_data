"""
Keepa 价格历史获取模块
使用 Keepa API 获取亚马逊商品的历史价格数据
复用 ApifyDB 做本地缓存，避免重复请求
"""

import os
import logging
from typing import Optional, Dict, List, Iterable, Tuple, Any
from pathlib import Path
from datetime import datetime, date

from dotenv import load_dotenv

# 优先加载当前项目根目录下的 .env，再兼容 data_summary/.env
ROOT_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ROOT_ENV_PATH)

DATA_SUMMARY_ENV_PATH = Path(__file__).resolve().parents[2] / "data_summary" / ".env"
if DATA_SUMMARY_ENV_PATH.exists():
    load_dotenv(DATA_SUMMARY_ENV_PATH)

logger = logging.getLogger(__name__)

# 尝试导入 keepa
KEEPA_AVAILABLE = False
keepa = None
try:
    import keepa  # type: ignore
    KEEPA_AVAILABLE = True
except ImportError:
    logger.warning("keepa 未安装，请运行: pip install keepa")

from .apify_db import ApifyDB


class KeepaPriceFetcher:
    """使用 Keepa API 获取亚马逊商品历史价格"""

    DEFAULT_CACHE_DAYS = 20
    DEFAULT_STATS_DAYS = 365

    # 国家/域名映射
    DOMAIN_MAP = {
        "US": "US",
        "UK": "UK",
        "GB": "UK",
        "DE": "DE",
        "FR": "FR",
        "JP": "JP",
        "CA": "CA",
        "IT": "IT",
        "ES": "ES",
        "IN": "IN",
        "MX": "MX",
        "BR": "BR",
        "AU": "AU",
    }

    # Keepa stats 数组中不同价格类型的索引
    PRICE_INDEX_PRIORITY = [0, 1, 10]  # Amazon, New, Buy Box

    # 历史价格字段优先级
    HISTORY_KEY_PRIORITY = ["AMAZON", "NEW", "BUY_BOX_SHIPPING"]

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_days: Optional[int] = None,
        timeout: float = 30.0,
        stats_days: int = DEFAULT_STATS_DAYS,
    ):
        if not KEEPA_AVAILABLE:
            raise ImportError("keepa 未安装，请运行: pip install keepa")

        self.api_key = api_key or os.getenv("KEEPA_API_KEY")
        if not self.api_key:
            raise ValueError("KEEPA_API_KEY 未配置，请在 .env 文件中设置")

        self.cache_days = cache_days or self.DEFAULT_CACHE_DAYS
        self.stats_days = stats_days

        # 初始化 Keepa API 客户端
        self.api = keepa.Keepa(self.api_key, timeout=timeout, logging_level="WARNING")
        self.db = ApifyDB()

    def get_price_history(self, asin: str, country: str = "US") -> Optional[Dict]:
        """获取单个商品的历史价格数据（优先使用缓存）"""
        if self.db.is_cached(asin, days=self.cache_days):
            logger.info(f"  [Keepa] {asin} 使用缓存数据")
            cached = self.db.get_cached_data(asin)
            if cached:
                return self._format_cached_data(cached)

        try:
            logger.info(f"  [Keepa] 获取 {asin} 的历史价格...")
            domain = self.DOMAIN_MAP.get(country.upper(), "US")

            products = self.api.query(
                items=[asin],
                domain=domain,
                history=True,
                stats=self.stats_days,
                offers=0,
                rating=False,
                to_datetime=True,
                progress_bar=False,
            )

            if not products:
                logger.warning(f"  [Keepa] 未找到 {asin} 的数据")
                return None

            product = products[0]
            parsed = self._parse_keepa_product(product)
            if parsed:
                cache_data = self._to_cache_format(parsed, product, country)
                self.db.save_apify_data(cache_data)
            return parsed

        except Exception as e:
            logger.error(f"  [Keepa] 获取 {asin} 失败: {e}")
            return None

    def get_multiple_price_history(self, asins: List[str], country: str = "US") -> Dict[str, Dict]:
        """批量获取多个商品的历史价格（优先使用缓存）"""
        if not asins:
            return {}

        results: Dict[str, Dict] = {}

        # 1) 先读缓存
        cached_data = self.db.get_cached_data_batch(asins, days=self.cache_days)
        for asin, data in cached_data.items():
            results[asin] = self._format_cached_data(data)

        cached_count = len(cached_data)
        if cached_count:
            logger.info(f"  [Keepa] 从缓存获取 {cached_count} 个商品的数据")

        # 2) 找出未缓存的 ASIN
        uncached_asins = self.db.get_uncached_asins(asins, days=self.cache_days)
        if not uncached_asins:
            logger.info(f"  [Keepa] 所有 {len(asins)} 个商品均命中缓存")
            return results

        # 3) 批量调用 Keepa API
        try:
            logger.info(f"  [Keepa] 从 API 获取 {len(uncached_asins)} 个商品的历史价格...")
            domain = self.DOMAIN_MAP.get(country.upper(), "US")

            batch_size = 100  # Keepa 建议单次最多 100 个
            api_success_count = 0

            for i in range(0, len(uncached_asins), batch_size):
                batch = uncached_asins[i : i + batch_size]

                products = self.api.query(
                    items=batch,
                    domain=domain,
                    history=True,
                    stats=self.stats_days,
                    offers=0,
                    rating=False,
                    to_datetime=True,
                    progress_bar=False,
                )

                if not products:
                    continue

                for product in products:
                    if not product or not product.get("asin"):
                        continue

                    parsed = self._parse_keepa_product(product)
                    if not parsed:
                        continue

                    asin = parsed["asin"]
                    results[asin] = parsed

                    cache_data = self._to_cache_format(parsed, product, country)
                    self.db.save_apify_data(cache_data)
                    api_success_count += 1

            logger.info(
                f"  [Keepa] 成功获取 {api_success_count} 个商品的价格历史（缓存: {cached_count}, API: {api_success_count}）"
            )

        except Exception as e:
            logger.error(f"  [Keepa] 批量获取失败: {e}")

        return results

    def _parse_keepa_product(self, product: Dict) -> Optional[Dict]:
        """解析 Keepa 返回的产品数据，提取历史最低/最高价及对应时间"""
        if not product:
            return None

        asin = product.get("asin")
        if not asin:
            return None

        price_min: Optional[float] = None
        price_max: Optional[float] = None
        price_min_date: Optional[str] = None
        price_max_date: Optional[str] = None
        history_count = 0

        # 1) 先从 stats 中读取 min/max（便宜且稳定）
        stats = product.get("stats") or {}
        if stats:
            min_prices = stats.get("min") or []
            max_prices = stats.get("max") or []

            # Keepa 可能返回 minTime/maxTime，也可能是 min_time/max_time
            min_times = stats.get("minTime") or stats.get("min_time") or []
            max_times = stats.get("maxTime") or stats.get("max_time") or []

            for idx in self.PRICE_INDEX_PRIORITY:
                min_val = self._safe_index(min_prices, idx)
                if min_val and min_val > 0:
                    price_min = min_val / 100.0
                    min_time_val = self._safe_index(min_times, idx)
                    if min_time_val:
                        price_min_date = self._format_datetime(min_time_val)
                    break

            for idx in self.PRICE_INDEX_PRIORITY:
                max_val = self._safe_index(max_prices, idx)
                if max_val and max_val > 0:
                    price_max = max_val / 100.0
                    max_time_val = self._safe_index(max_times, idx)
                    if max_time_val:
                        price_max_date = self._format_datetime(max_time_val)
                    break

        # 2) 再从历史序列中拿更细的时间信息
        data = product.get("data") or {}
        for price_key in self.HISTORY_KEY_PRIORITY:
            prices = data.get(price_key) or []
            times = data.get(f"{price_key}_time") or []

            valid_points = self._build_valid_points(prices, times)
            if not valid_points:
                continue

            history_count = len(valid_points)

            min_item = min(valid_points, key=lambda x: x[0])
            max_item = max(valid_points, key=lambda x: x[0])

            if price_min is None or min_item[0] < price_min:
                price_min = min_item[0]
                price_min_date = self._format_datetime(min_item[1]) if min_item[1] else price_min_date

            if price_max is None or max_item[0] > price_max:
                price_max = max_item[0]
                price_max_date = self._format_datetime(max_item[1]) if max_item[1] else price_max_date

            # 找到首个有效历史字段就结束，避免混合口径
            break

        return {
            "asin": asin,
            "price_min": price_min,
            "price_max": price_max,
            "price_min_date": price_min_date,
            "price_max_date": price_max_date,
            "history_count": history_count,
        }

    @staticmethod
    def _safe_index(values: Iterable[Any], idx: int) -> Any:
        try:
            return values[idx]  # type: ignore[index]
        except Exception:
            return None

    @staticmethod
    def _build_valid_points(prices: List[Any], times: List[Any]) -> List[Tuple[float, Any]]:
        """构建有效价格点列表，过滤掉 <=0 或 None 的价格"""
        valid: List[Tuple[float, Any]] = []
        if not prices:
            return valid

        for i, raw_price in enumerate(prices):
            if raw_price is None or raw_price <= 0:
                continue
            time_val = times[i] if i < len(times) else None
            valid.append((raw_price / 100.0, time_val))
        return valid

    @staticmethod
    def _format_datetime(dt: Any) -> Optional[str]:
        """将 Keepa 返回的时间值格式化为 ISO 字符串"""
        if dt is None:
            return None
        if isinstance(dt, datetime):
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        if isinstance(dt, date):
            return datetime(dt.year, dt.month, dt.day).strftime("%Y-%m-%dT%H:%M:%S")
        return str(dt)

    @staticmethod
    def _format_cached_data(cached: Dict) -> Dict:
        return {
            "asin": cached.get("asin"),
            "price_min": cached.get("price_min"),
            "price_max": cached.get("price_max"),
            "price_min_date": cached.get("price_min_date"),
            "price_max_date": cached.get("price_max_date"),
            "history_count": 0,
            "from_cache": True,
        }

    @staticmethod
    def _to_cache_format(parsed: Dict, product: Dict, country: str) -> Dict:
        """转换为 ApifyDB 兼容的缓存结构"""
        category_tree = product.get("categoryTree") or []
        main_category = category_tree[0].get("name") if category_tree else None

        now_iso = datetime.now().isoformat()

        return {
            "asin": parsed.get("asin"),
            "country": country.lower(),
            "name": product.get("title"),
            "brand": product.get("brand"),
            "rating": None,
            "n_reviews": None,
            "main_category": main_category,
            "primary_category": None,
            "sub_categories": [],
            "seller_type": None,
            "in_stock": True,
            "currency": "USD",
            "list_price": None,
            "price": None,
            "price_new": None,
            "price_buybox": None,
            "price_prime_exclusive": None,
            "price_amazon": None,
            "price_min": parsed.get("price_min"),
            "price_max": parsed.get("price_max"),
            "price_min_date": parsed.get("price_min_date"),
            "price_max_date": parsed.get("price_max_date"),
            "listed_at": None,
            "tracked_since": None,
            "last_updated": now_iso,
            "data_captured_at": now_iso,
        }

    def get_tokens_left(self) -> int:
        """获取剩余 API token 数量"""
        try:
            return int(self.api.tokens_left)
        except Exception:
            return -1


def is_keepa_available() -> bool:
    """检查 Keepa 是否可用"""
    if not KEEPA_AVAILABLE:
        return False
    return bool(os.getenv("KEEPA_API_KEY"))


def get_keepa_cache_stats() -> Dict:
    """获取 Keepa/Apify 共用缓存统计信息"""
    db = ApifyDB()
    return db.get_cache_stats()


def clean_keepa_cache(days: int = KeepaPriceFetcher.DEFAULT_CACHE_DAYS) -> int:
    """清理过期缓存"""
    db = ApifyDB()
    return db.clean_expired_cache(days)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if not is_keepa_available():
        print("Keepa 不可用，请检查 KEEPA_API_KEY 配置")
        sys.exit(1)

    fetcher = KeepaPriceFetcher()
    print(f"剩余 API tokens: {fetcher.get_tokens_left()}")

    test_asin = "B0BK9HFZ77"
    print(f"\n测试获取 {test_asin} 的价格历史...")
    result = fetcher.get_price_history(test_asin)
    if result:
        print(f"  最低价: ${result.get('price_min')} ({result.get('price_min_date')})")
        print(f"  最高价: ${result.get('price_max')} ({result.get('price_max_date')})")
        print(f"  历史记录数: {result.get('history_count')}")
    else:
        print("  获取失败")
