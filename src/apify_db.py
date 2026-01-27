"""
Apify 数据缓存数据库模块
缓存已抓取的 Apify 价格历史数据，避免重复抓取
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime, timedelta

from .logger import setup_logger

# 初始化日志
logger = setup_logger("apify_db")


class ApifyDB:
    """Apify 数据缓存数据库管理器"""

    def __init__(self, db_path: str = "data/apify_cache.db"):
        """
        初始化数据库

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript("""
                -- Apify 缓存表
                CREATE TABLE IF NOT EXISTS apify_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asin TEXT NOT NULL UNIQUE,
                    country TEXT DEFAULT 'us',
                    name TEXT,
                    brand TEXT,
                    rating REAL,
                    n_reviews INTEGER,
                    main_category TEXT,
                    primary_category TEXT,
                    sub_categories TEXT,  -- JSON 数组
                    seller_type TEXT,
                    in_stock INTEGER,
                    currency TEXT,
                    list_price REAL,
                    price REAL,
                    price_new REAL,
                    price_buybox REAL,
                    price_prime_exclusive REAL,
                    price_amazon REAL,
                    price_min REAL,           -- 历史最低价
                    price_max REAL,           -- 历史最高价
                    price_min_date TEXT,      -- 最低价日期
                    price_max_date TEXT,      -- 最高价日期
                    listed_at TEXT,           -- 上架日期
                    tracked_since TEXT,       -- 开始追踪日期
                    last_updated TEXT,        -- Apify 最后更新时间
                    data_captured_at TEXT,    -- 数据抓取时间
                    raw_data TEXT,            -- 原始 JSON 数据
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                -- 索引
                CREATE INDEX IF NOT EXISTS idx_apify_asin ON apify_cache(asin);
                CREATE INDEX IF NOT EXISTS idx_apify_created_at ON apify_cache(created_at);
            """)

    def save_apify_data(self, data: Dict) -> bool:
        """
        保存单个 Apify 数据

        Args:
            data: Apify 返回的原始数据

        Returns:
            是否保存成功
        """
        if not data or not data.get('asin'):
            return False

        try:
            # Keepa 等来源可能直接提供 price_min/price_max，在没有历史字段时不应被覆盖
            provided_price_min = data.get('price_min')
            provided_price_max = data.get('price_max')
            provided_price_min_date = data.get('price_min_date')
            provided_price_max_date = data.get('price_max_date')

            history_fields = ['price_amazon_history', 'price_buybox_history', 'price_new_history']
            has_history = any(data.get(field) for field in history_fields)

            if has_history:
                # 优先使用历史记录计算结果，缺失时再回落到提供值
                calc_min, calc_max, calc_min_date, calc_max_date = self._calc_price_history(data)
                price_min = calc_min if calc_min is not None else provided_price_min
                price_max = calc_max if calc_max is not None else provided_price_max
                price_min_date = calc_min_date if calc_min_date else provided_price_min_date
                price_max_date = calc_max_date if calc_max_date else provided_price_max_date
            else:
                price_min = provided_price_min
                price_max = provided_price_max
                price_min_date = provided_price_min_date
                price_max_date = provided_price_max_date

            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO apify_cache
                    (asin, country, name, brand, rating, n_reviews,
                     main_category, primary_category, sub_categories,
                     seller_type, in_stock, currency, list_price, price,
                     price_new, price_buybox, price_prime_exclusive, price_amazon,
                     price_min, price_max, price_min_date, price_max_date,
                     listed_at, tracked_since, last_updated, data_captured_at,
                     raw_data, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """, (
                    data.get('asin'),
                    data.get('country', 'us'),
                    data.get('name'),
                    data.get('brand'),
                    data.get('rating'),
                    data.get('n_reviews'),
                    data.get('main_category'),
                    data.get('primary_category'),
                    json.dumps(data.get('sub_categories', []), ensure_ascii=False),
                    data.get('seller_type'),
                    1 if data.get('in_stock') else 0,
                    data.get('currency'),
                    data.get('list_price'),
                    data.get('price'),
                    data.get('price_new'),
                    data.get('price_buybox'),
                    data.get('price_prime_exclusive'),
                    data.get('price_amazon'),
                    price_min,
                    price_max,
                    price_min_date,
                    price_max_date,
                    data.get('listed_at'),
                    data.get('tracked_since'),
                    data.get('last_updated'),
                    data.get('data_captured_at'),
                    json.dumps(data, ensure_ascii=False)
                ))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"保存 Apify 数据 {data.get('asin')} 失败: {e}")
            return False

    def _calc_price_history(self, data: Dict) -> tuple:
        """
        从价格历史中计算最低价和最高价

        Args:
            data: Apify 原始数据

        Returns:
            (price_min, price_max, price_min_date, price_max_date)
        """
        price_min = None
        price_max = None
        price_min_date = None
        price_max_date = None

        # 尝试多个历史价格字段（与 ApifyPriceFetcher 保持一致：Amazon > BuyBox > New）
        history_fields = ['price_amazon_history', 'price_buybox_history', 'price_new_history']
        price_history = []

        for field in history_fields:
            if field in data and data[field]:
                price_history = data[field]
                break

        if not price_history:
            return price_min, price_max, price_min_date, price_max_date

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

        return price_min, price_max, price_min_date, price_max_date

    def batch_save_apify_data(self, data_list: List[Dict]) -> int:
        """
        批量保存 Apify 数据

        Args:
            data_list: Apify 数据列表

        Returns:
            保存成功的数量
        """
        saved_count = 0
        for data in data_list:
            if self.save_apify_data(data):
                saved_count += 1
        return saved_count

    def get_cached_data(self, asin: str) -> Optional[Dict]:
        """
        获取缓存的 ASIN 数据

        Args:
            asin: ASIN 码

        Returns:
            缓存数据字典，不存在返回 None
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM apify_cache WHERE asin = ?", (asin,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_dict(row)

    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        """将数据库行转换为字典"""
        result = dict(row)
        # 解析 JSON 字段
        if result.get('sub_categories'):
            try:
                result['sub_categories'] = json.loads(result['sub_categories'])
            except (json.JSONDecodeError, TypeError):
                result['sub_categories'] = []
        # 转换布尔值
        result['in_stock'] = bool(result.get('in_stock'))
        return result

    def is_cached(self, asin: str, days: int = 20) -> bool:
        """
        检查 ASIN 是否在缓存有效期内

        Args:
            asin: ASIN 码
            days: 缓存有效天数（默认 20 天）

        Returns:
            是否在有效期内
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM apify_cache WHERE asin = ? AND created_at >= ?",
                (asin, cutoff_date)
            )
            return cursor.fetchone()[0] > 0

    def get_uncached_asins(self, asins: List[str], days: int = 20) -> List[str]:
        """
        获取未缓存或缓存已过期的 ASIN 列表

        Args:
            asins: ASIN 列表
            days: 缓存有效天数

        Returns:
            需要抓取的 ASIN 列表
        """
        if not asins:
            return []

        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

        with sqlite3.connect(str(self.db_path)) as conn:
            # 获取有效缓存的 ASIN
            placeholders = ','.join('?' * len(asins))
            cursor = conn.execute(
                f"SELECT asin FROM apify_cache WHERE asin IN ({placeholders}) AND created_at >= ?",
                (*asins, cutoff_date)
            )
            cached_asins = {row[0] for row in cursor.fetchall()}

        # 返回未缓存的 ASIN
        return [asin for asin in asins if asin not in cached_asins]

    def get_cached_data_batch(self, asins: List[str], days: int = 20) -> Dict[str, Dict]:
        """
        批量获取缓存数据

        Args:
            asins: ASIN 列表
            days: 缓存有效天数

        Returns:
            ASIN -> 数据的映射
        """
        if not asins:
            return {}

        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            placeholders = ','.join('?' * len(asins))
            cursor = conn.execute(
                f"SELECT * FROM apify_cache WHERE asin IN ({placeholders}) AND created_at >= ?",
                (*asins, cutoff_date)
            )
            rows = cursor.fetchall()

            return {row['asin']: self._row_to_dict(row) for row in rows}

    def get_cache_stats(self) -> Dict:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        cutoff_date = (datetime.now() - timedelta(days=20)).strftime('%Y-%m-%d %H:%M:%S')

        with sqlite3.connect(str(self.db_path)) as conn:
            # 总数
            cursor = conn.execute("SELECT COUNT(*) FROM apify_cache")
            total = cursor.fetchone()[0]

            # 有效缓存数（20天内）
            cursor = conn.execute(
                "SELECT COUNT(*) FROM apify_cache WHERE created_at >= ?",
                (cutoff_date,)
            )
            valid_count = cursor.fetchone()[0]

            # 过期缓存数
            expired_count = total - valid_count

            return {
                'total': total,
                'valid_count': valid_count,
                'expired_count': expired_count
            }

    def clean_expired_cache(self, days: int = 20) -> int:
        """
        清理过期缓存

        Args:
            days: 超过多少天的数据视为过期

        Returns:
            删除的记录数
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "DELETE FROM apify_cache WHERE created_at < ?",
                (cutoff_date,)
            )
            deleted = cursor.rowcount
            conn.commit()

        if deleted > 0:
            logger.info(f"清理了 {deleted} 条过期 Apify 缓存")

        return deleted
