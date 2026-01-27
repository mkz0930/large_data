"""
数据库管理模块
提供 SQLite 数据库操作，包括 ASIN 存储、分类统计、任务管理
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Optional

from .utils import parse_price, parse_sales
from .logger import setup_logger

# 初始化日志
logger = setup_logger("database")


class BatchScraperDB:
    """批量抓取数据库管理器"""

    def __init__(self, db_path: str = "data/batch_scraper.db"):
        """
        初始化数据库

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._migrate_db()

    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript("""
                -- ASIN 主表
                CREATE TABLE IF NOT EXISTS asins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asin TEXT NOT NULL,
                    keyword TEXT NOT NULL,
                    source_type TEXT,  -- 'keyword_search' 或 'category_search'
                    source_value TEXT, -- 关键词或类目名称
                    name TEXT,
                    brand TEXT,
                    category TEXT,
                    category_path TEXT,   -- 完整类目路径（卖家精灵）
                    category_main TEXT,   -- 大类目（卖家精灵）
                    category_sub TEXT,    -- 小类目（卖家精灵）
                    price REAL,
                    rating REAL,
                    reviews_count INTEGER,
                    sales_volume INTEGER,
                    page_rank INTEGER,
                    url TEXT,             -- 产品URL
                    is_sponsored INTEGER DEFAULT 0,  -- 是否为广告 (0=否, 1=是)
                    filter_status TEXT,  -- 筛选状态 (NULL=保留, 'sponsored'=广告筛选, 'category_filtered'=分类筛选, 'sales_filtered'=销量筛选)
                    created_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(asin, keyword)
                );

                -- 类目统计表
                CREATE TABLE IF NOT EXISTS category_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT NOT NULL,
                    category TEXT NOT NULL,
                    asin_count INTEGER,
                    avg_price REAL,
                    avg_rating REAL,
                    total_reviews INTEGER,
                    created_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(keyword, category)
                );

                -- 抓取任务记录表
                CREATE TABLE IF NOT EXISTS scrape_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT NOT NULL,
                    task_type TEXT,  -- 'initial', 'category_expansion'
                    status TEXT,     -- 'pending', 'running', 'completed', 'failed'
                    total_asins INTEGER,
                    pages_scraped INTEGER,
                    error_message TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                -- 卖家精灵数据表
                CREATE TABLE IF NOT EXISTS sellerspirit_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asin TEXT NOT NULL,
                    keyword TEXT NOT NULL,
                    source TEXT,  -- 'collector' 或 'hook'
                    category_path TEXT,
                    category_main TEXT,
                    category_sub TEXT,
                    raw_data TEXT,  -- JSON 格式的原始数据
                    created_at TEXT DEFAULT (datetime('now')),
                    created_date TEXT DEFAULT (date('now')),  -- 用于按天去重
                    UNIQUE(asin, keyword, created_date)
                );

                -- 卖家精灵历史数据缓存表（用于步骤7.5数据补充）
                CREATE TABLE IF NOT EXISTS sellerspirit_history_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asin TEXT NOT NULL UNIQUE,
                    sales_3m INTEGER,              -- 最近3个月销量
                    ss_monthly_sales INTEGER,      -- 卖家精灵月销量
                    listing_date TEXT,             -- 上架日期
                    avg_monthly_sales INTEGER,     -- 平均月销量
                    sales_months_count INTEGER,    -- 有销量数据的月份数
                    ss_rating REAL,                -- 卖家精灵评分
                    ss_reviews INTEGER,            -- 卖家精灵评论数
                    raw_trends TEXT,               -- 原始 trends 数据（JSON）
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                -- 索引
                CREATE INDEX IF NOT EXISTS idx_asins_keyword ON asins(keyword);
                CREATE INDEX IF NOT EXISTS idx_asins_category ON asins(category);
                CREATE INDEX IF NOT EXISTS idx_asins_asin ON asins(asin);
                CREATE INDEX IF NOT EXISTS idx_category_stats_keyword ON category_stats(keyword);
                CREATE INDEX IF NOT EXISTS idx_sellerspirit_keyword ON sellerspirit_data(keyword);
                CREATE INDEX IF NOT EXISTS idx_sellerspirit_asin ON sellerspirit_data(asin);
                CREATE INDEX IF NOT EXISTS idx_ss_history_cache_asin ON sellerspirit_history_cache(asin);
            """)

    def _migrate_db(self):
        """迁移数据库结构（添加新列）"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("PRAGMA table_info(asins)")
            columns = {row[1] for row in cursor.fetchall()}

            # 添加缺失的列
            new_columns = [
                ('category_path', 'TEXT'),
                ('category_main', 'TEXT'),
                ('category_sub', 'TEXT'),
                ('url', 'TEXT'),
                ('is_sponsored', 'INTEGER DEFAULT 0'),
                ('filter_status', 'TEXT'),
                # 卖家精灵历史数据字段
                ('sales_3m', 'INTEGER'),           # 最近3个月销量
                ('price_min', 'REAL'),             # 历史最低价
                ('price_max', 'REAL'),             # 历史最高价
                ('price_min_date', 'TEXT'),        # 最低价日期
                ('price_max_date', 'TEXT'),        # 最高价日期
                ('ss_monthly_sales', 'INTEGER'),   # 卖家精灵月销量
                ('listing_date', 'TEXT'),          # 上架日期（卖家精灵）
                ('avg_monthly_sales', 'INTEGER'),  # 平均月销量
                ('sales_months_count', 'INTEGER'), # 有销量数据的月份数
            ]
            for col_name, col_type in new_columns:
                if col_name not in columns:
                    conn.execute(f"ALTER TABLE asins ADD COLUMN {col_name} {col_type}")
                    logger.debug(f"  数据库迁移: 添加列 {col_name}")

            conn.execute("CREATE INDEX IF NOT EXISTS idx_asins_category_sub ON asins(category_sub)")
            conn.commit()

    def save_asins(self, asins: List[Dict], keyword: str, source_type: str, source_value: str) -> int:
        """
        批量保存 ASIN 数据

        Args:
            asins: ASIN 数据列表
            keyword: 搜索关键词
            source_type: 来源类型 ('keyword_search' 或 'category_search')
            source_value: 来源值

        Returns:
            保存成功的数量
        """
        saved_count = 0
        with sqlite3.connect(str(self.db_path)) as conn:
            for item in asins:
                asin = item.get('asin')
                if not asin:
                    continue
                try:
                    conn.execute("""
                        INSERT OR REPLACE INTO asins
                        (asin, keyword, source_type, source_value, name, brand, category,
                         category_path, category_main, category_sub,
                         price, rating, reviews_count, sales_volume, page_rank, url, is_sponsored)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        asin,
                        keyword,
                        source_type,
                        source_value,
                        item.get('name'),
                        item.get('brand'),
                        item.get('category'),
                        item.get('category_path'),
                        item.get('category_main'),
                        item.get('category_sub'),
                        parse_price(item.get('price')),
                        item.get('stars') or item.get('rating'),
                        item.get('total_reviews') or item.get('ratings_total'),
                        item.get('sales_volume') if item.get('sales_volume') is not None else parse_sales(item.get('purchase_history_message')),
                        item.get('page'),
                        item.get('url'),
                        1 if item.get('is_sponsored') else 0
                    ))
                    saved_count += 1
                except Exception as e:
                    logger.error(f"保存 ASIN {asin} 失败: {e}")
            conn.commit()
        return saved_count

    def save_category_stats(self, keyword: str, stats: List[Dict]) -> int:
        """
        保存类目统计数据

        Args:
            keyword: 搜索关键词
            stats: 统计数据列表

        Returns:
            保存成功的数量
        """
        saved_count = 0
        with sqlite3.connect(str(self.db_path)) as conn:
            for stat in stats:
                try:
                    conn.execute("""
                        INSERT OR REPLACE INTO category_stats
                        (keyword, category, asin_count, avg_price, avg_rating, total_reviews)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        keyword,
                        stat['category'],
                        stat['count'],
                        stat.get('avg_price'),
                        stat.get('avg_rating'),
                        stat.get('total_reviews')
                    ))
                    saved_count += 1
                except Exception as e:
                    logger.error(f"保存类目统计失败: {e}")
            conn.commit()
        return saved_count

    def create_task(self, keyword: str, task_type: str) -> int:
        """
        创建抓取任务

        Args:
            keyword: 搜索关键词
            task_type: 任务类型

        Returns:
            任务 ID
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                INSERT INTO scrape_tasks (keyword, task_type, status, started_at)
                VALUES (?, ?, 'running', datetime('now'))
            """, (keyword, task_type))
            conn.commit()
            return cursor.lastrowid

    def update_task(self, task_id: int, status: str, total_asins: int = None,
                    pages_scraped: int = None, error_message: str = None):
        """
        更新任务状态

        Args:
            task_id: 任务 ID
            status: 状态 ('completed' 或 'failed')
            total_asins: 总 ASIN 数
            pages_scraped: 抓取页数
            error_message: 错误信息
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            if status == 'completed':
                conn.execute("""
                    UPDATE scrape_tasks
                    SET status = ?, total_asins = ?, pages_scraped = ?, completed_at = datetime('now')
                    WHERE id = ?
                """, (status, total_asins, pages_scraped, task_id))
            elif status == 'failed':
                conn.execute("""
                    UPDATE scrape_tasks
                    SET status = ?, error_message = ?, completed_at = datetime('now')
                    WHERE id = ?
                """, (status, error_message, task_id))
            conn.commit()

    def get_existing_asins(self, keyword: str) -> set:
        """获取已存在的 ASIN 集合"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "SELECT DISTINCT asin FROM asins WHERE keyword = ?", (keyword,)
            )
            return {row[0] for row in cursor.fetchall()}

    def get_asin_count(self, keyword: str, include_filtered: bool = False) -> int:
        """
        获取关键词的 ASIN 数量

        Args:
            keyword: 搜索关键词
            include_filtered: 是否包含已筛选的记录（默认 False，只统计未被筛选的）

        Returns:
            ASIN 数量
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            if include_filtered:
                cursor = conn.execute(
                    "SELECT COUNT(DISTINCT asin) FROM asins WHERE keyword = ?", (keyword,)
                )
            else:
                cursor = conn.execute(
                    "SELECT COUNT(DISTINCT asin) FROM asins WHERE keyword = ? AND filter_status IS NULL",
                    (keyword,)
                )
            return cursor.fetchone()[0]

    def has_today_data(self, keyword: str, source_type: str = 'keyword_search') -> bool:
        """检查当天是否已有该关键词的数据"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) FROM asins
                WHERE keyword = ? AND source_type = ?
                AND date(created_at) = date('now')
            """, (keyword, source_type))
            return cursor.fetchone()[0] > 0

    def has_today_category_data(self, keyword: str, source_type: str, source_value: str) -> bool:
        """
        检查当天是否已有该关键词+分类的数据

        Args:
            keyword: 搜索关键词
            source_type: 来源类型 ('category_search' 或 'round3_category')
            source_value: 分类名称

        Returns:
            是否已有数据
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) FROM asins
                WHERE keyword = ? AND source_type = ? AND source_value = ?
                AND date(created_at) = date('now')
            """, (keyword, source_type, source_value))
            return cursor.fetchone()[0] > 0

    def get_today_scraped_categories(self, keyword: str, source_type: str = None) -> set:
        """
        获取当天已抓取的分类名称集合（小写）

        Args:
            keyword: 搜索关键词
            source_type: 来源类型，如果为 None 则获取所有类型

        Returns:
            分类名称集合（小写）
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            if source_type:
                cursor = conn.execute("""
                    SELECT DISTINCT source_value FROM asins
                    WHERE keyword = ? AND source_type = ?
                    AND date(created_at) = date('now')
                """, (keyword, source_type))
            else:
                cursor = conn.execute("""
                    SELECT DISTINCT source_value FROM asins
                    WHERE keyword = ?
                    AND source_type IN ('category_search', 'round3_category')
                    AND date(created_at) = date('now')
                """, (keyword,))
            return {row[0].lower() for row in cursor.fetchall() if row[0]}

    def save_sellerspirit_data(self, keyword: str, category_map: Dict[str, Dict], source: str = 'collector') -> int:
        """
        保存卖家精灵数据

        Args:
            keyword: 搜索关键词
            category_map: ASIN -> 分类信息的映射
            source: 数据来源 ('collector' 或 'hook')

        Returns:
            保存成功的数量
        """
        import json
        saved_count = 0
        with sqlite3.connect(str(self.db_path)) as conn:
            for asin, info in category_map.items():
                try:
                    conn.execute("""
                        INSERT OR REPLACE INTO sellerspirit_data
                        (asin, keyword, source, category_path, category_main, category_sub, raw_data)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        asin,
                        keyword,
                        source,
                        info.get('category_path'),
                        info.get('category_main'),
                        info.get('category_sub'),
                        json.dumps(info, ensure_ascii=False) if info else None
                    ))
                    saved_count += 1
                except Exception as e:
                    logger.error(f"保存卖家精灵数据 {asin} 失败: {e}")
            conn.commit()
        return saved_count

    def has_today_sellerspirit_data(self, keyword: str) -> bool:
        """检查当天是否已有该关键词的卖家精灵数据"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) FROM sellerspirit_data
                WHERE keyword = ?
                AND date(created_at) = date('now')
            """, (keyword,))
            return cursor.fetchone()[0] > 0

    def get_today_sellerspirit_data(self, keyword: str) -> Dict[str, Dict]:
        """
        获取当天该关键词的卖家精灵数据

        Args:
            keyword: 搜索关键词

        Returns:
            ASIN -> 分类信息的映射
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT asin, category_path, category_main, category_sub
                FROM sellerspirit_data
                WHERE keyword = ?
                AND date(created_at) = date('now')
            """, (keyword,))
            rows = cursor.fetchall()

            category_map = {}
            for row in rows:
                category_map[row[0]] = {
                    'category_path': row[1],
                    'category_main': row[2],
                    'category_sub': row[3]
                }
            return category_map

    def reset_filter_status(self, keyword: str) -> int:
        """
        重置指定关键词所有 ASIN 的筛选状态

        在重新运行筛选流程前调用，确保所有 ASIN 都参与筛选

        Args:
            keyword: 搜索关键词

        Returns:
            重置的记录数
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                UPDATE asins
                SET filter_status = NULL
                WHERE keyword = ? AND filter_status IS NOT NULL
            """, (keyword,))
            reset_count = cursor.rowcount
            conn.commit()
            return reset_count

    def filter_sponsored_asins(self, keyword: str) -> Dict[str, int]:
        """
        筛选广告 ASIN，删除 is_sponsored=1 的记录

        Args:
            keyword: 搜索关键词

        Returns:
            包含筛选统计的字典：
            - total: 筛选前总数
            - sponsored_count: 广告数量
            - removed: 删除的数量
            - kept: 保留的数量
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            # 获取筛选前的总数
            cursor = conn.execute(
                "SELECT COUNT(*) FROM asins WHERE keyword = ?", (keyword,)
            )
            total = cursor.fetchone()[0]

            # 获取广告数量
            cursor = conn.execute(
                "SELECT COUNT(*) FROM asins WHERE keyword = ? AND is_sponsored = 1",
                (keyword,)
            )
            sponsored_count = cursor.fetchone()[0]

            # 标记广告记录
            cursor = conn.execute("""
                UPDATE asins
                SET filter_status = 'sponsored'
                WHERE keyword = ? AND is_sponsored = 1 AND filter_status IS NULL
            """, (keyword,))
            removed = cursor.rowcount

            conn.commit()

            kept = total - removed
            return {
                'total': total,
                'sponsored_count': sponsored_count,
                'removed': removed,
                'kept': kept
            }

    def get_sponsored_distribution(self, keyword: str) -> Dict[str, int]:
        """
        获取广告分布统计

        Args:
            keyword: 搜索关键词

        Returns:
            广告分布字典
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            # 广告数量
            cursor = conn.execute(
                "SELECT COUNT(*) FROM asins WHERE keyword = ? AND is_sponsored = 1",
                (keyword,)
            )
            sponsored = cursor.fetchone()[0]

            # 非广告数量
            cursor = conn.execute(
                "SELECT COUNT(*) FROM asins WHERE keyword = ? AND is_sponsored = 0",
                (keyword,)
            )
            organic = cursor.fetchone()[0]

            return {
                'sponsored': sponsored,
                'organic': organic,
                'total': sponsored + organic
            }

    def filter_low_sales_asins(self, keyword: str, max_sales: int = 100) -> Dict[str, int]:
        """
        筛选低销量 ASIN，删除销量大于阈值的记录

        Args:
            keyword: 搜索关键词
            max_sales: 销量阈值，保留小于等于此值的 ASIN（默认 100）

        Returns:
            包含筛选统计的字典：
            - total: 筛选前总数
            - removed: 删除的数量
            - kept: 保留的数量
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            # 获取筛选前的总数（只统计未被筛选的记录）
            cursor = conn.execute(
                "SELECT COUNT(*) FROM asins WHERE keyword = ? AND filter_status IS NULL",
                (keyword,)
            )
            total = cursor.fetchone()[0]

            # 标记销量大于阈值的记录
            # sales_volume = 0 或 NULL 表示没有销量数据，保留这些记录
            cursor = conn.execute("""
                UPDATE asins
                SET filter_status = 'sales_filtered'
                WHERE keyword = ? AND sales_volume > ? AND filter_status IS NULL
            """, (keyword, max_sales))
            removed = cursor.rowcount

            conn.commit()

            kept = total - removed
            return {
                'total': total,
                'removed': removed,
                'kept': kept
            }

    def get_sales_distribution(self, keyword: str, max_sales: int = 100) -> Dict[str, int]:
        """
        获取销量分布统计

        Args:
            keyword: 搜索关键词
            max_sales: 销量阈值

        Returns:
            销量分布字典
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            # 只统计未被筛选的记录 (filter_status IS NULL)
            # 无销量数据
            cursor = conn.execute(
                "SELECT COUNT(*) FROM asins WHERE keyword = ? AND (sales_volume IS NULL OR sales_volume = 0) AND filter_status IS NULL",
                (keyword,)
            )
            no_data = cursor.fetchone()[0]

            # 销量 <= max_sales
            cursor = conn.execute(
                "SELECT COUNT(*) FROM asins WHERE keyword = ? AND sales_volume > 0 AND sales_volume <= ? AND filter_status IS NULL",
                (keyword, max_sales)
            )
            under_threshold = cursor.fetchone()[0]

            # 销量 > max_sales
            cursor = conn.execute(
                "SELECT COUNT(*) FROM asins WHERE keyword = ? AND sales_volume > ? AND filter_status IS NULL",
                (keyword, max_sales)
            )
            over_threshold = cursor.fetchone()[0]

            return {
                'no_data': no_data,
                'under_threshold': under_threshold,
                'over_threshold': over_threshold,
                'total': no_data + under_threshold + over_threshold
            }

    def filter_by_top_category(self, keyword: str) -> Dict[str, any]:
        """
        按分类筛选，只保留数量最多的分类的产品

        Args:
            keyword: 搜索关键词

        Returns:
            包含筛选统计的字典：
            - total: 筛选前总数
            - top_category: 保留的分类名称
            - top_category_count: 该分类的产品数量
            - removed: 删除的数量
            - kept: 保留的数量
            - avg_price: 该分类的平均价格
            - median_price: 该分类的价格中位数
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            # 获取筛选前未被过滤的总数
            cursor = conn.execute(
                "SELECT COUNT(*) FROM asins WHERE keyword = ? AND filter_status IS NULL", (keyword,)
            )
            total = cursor.fetchone()[0]

            if total == 0:
                return {
                    'total': 0,
                    'top_category': None,
                    'top_category_count': 0,
                    'removed': 0,
                    'kept': 0,
                    'avg_price': None,
                    'median_price': None
                }

            # 按 category_sub 分组统计数量，找出最大的分类（只统计未被过滤的）
            cursor = conn.execute("""
                SELECT category_sub, COUNT(*) as cnt
                FROM asins
                WHERE keyword = ? AND category_sub IS NOT NULL AND category_sub != ''
                    AND filter_status IS NULL
                GROUP BY category_sub
                ORDER BY cnt DESC
                LIMIT 1
            """, (keyword,))
            row = cursor.fetchone()

            if not row:
                # 没有分类数据，不做筛选
                return {
                    'total': total,
                    'top_category': None,
                    'top_category_count': 0,
                    'removed': 0,
                    'kept': total,
                    'avg_price': None,
                    'median_price': None
                }

            top_category = row[0]
            top_category_count = row[1]

            # 计算该分类的平均价格
            cursor = conn.execute("""
                SELECT AVG(price)
                FROM asins
                WHERE keyword = ? AND category_sub = ? AND price IS NOT NULL AND price > 0
            """, (keyword, top_category))
            avg_price_row = cursor.fetchone()
            avg_price = round(avg_price_row[0], 2) if avg_price_row[0] else None

            # 计算该分类的价格中位数
            cursor = conn.execute("""
                SELECT price
                FROM asins
                WHERE keyword = ? AND category_sub = ? AND price IS NOT NULL AND price > 0
                ORDER BY price
            """, (keyword, top_category))
            prices = [row[0] for row in cursor.fetchall()]

            median_price = None
            if prices:
                n = len(prices)
                if n % 2 == 1:
                    median_price = round(prices[n // 2], 2)
                else:
                    median_price = round((prices[n // 2 - 1] + prices[n // 2]) / 2, 2)

            # 标记不属于该分类的记录
            cursor = conn.execute("""
                UPDATE asins
                SET filter_status = 'category_filtered'
                WHERE keyword = ? AND (category_sub IS NULL OR category_sub != ?) AND filter_status IS NULL
            """, (keyword, top_category))
            removed = cursor.rowcount

            conn.commit()

            kept = total - removed
            return {
                'total': total,
                'top_category': top_category,
                'top_category_count': top_category_count,
                'removed': removed,
                'kept': kept,
                'avg_price': avg_price,
                'median_price': median_price
            }

    def get_category_distribution(self, keyword: str) -> List[Dict]:
        """
        获取分类分布统计（只统计未被过滤的记录）

        Args:
            keyword: 搜索关键词

        Returns:
            分类分布列表，按数量降序排列
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT category_sub, COUNT(*) as cnt
                FROM asins
                WHERE keyword = ? AND category_sub IS NOT NULL AND category_sub != ''
                    AND filter_status IS NULL
                GROUP BY category_sub
                ORDER BY cnt DESC
            """, (keyword,))
            rows = cursor.fetchall()

            return [{'category': row[0], 'count': row[1]} for row in rows]

    def get_today_asins(self, keyword: str, source_type: str = 'keyword_search') -> List[Dict]:
        """
        获取当天该关键词的所有 ASIN 数据

        Args:
            keyword: 搜索关键词
            source_type: 来源类型

        Returns:
            ASIN 数据列表
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT asin, name, brand, category, category_path, category_main, category_sub,
                       price, rating, reviews_count, sales_volume, page_rank
                FROM asins
                WHERE keyword = ? AND source_type = ?
                AND date(created_at) = date('now')
                ORDER BY page_rank
            """, (keyword, source_type))
            rows = cursor.fetchall()

            results = []
            for row in rows:
                results.append({
                    'asin': row['asin'],
                    'name': row['name'],
                    'brand': row['brand'],
                    'category': row['category'],
                    'category_path': row['category_path'],
                    'category_main': row['category_main'],
                    'category_sub': row['category_sub'],
                    'price': row['price'],
                    'stars': row['rating'],
                    'rating': row['rating'],
                    'total_reviews': row['reviews_count'],
                    'reviews_count': row['reviews_count'],
                    'sales_volume': row['sales_volume'],
                    'page': row['page_rank']
                })
            return results

    def get_category_coverage(self, keyword: str) -> Dict[str, int]:
        """
        获取分类数据覆盖率统计

        Args:
            keyword: 搜索关键词

        Returns:
            包含覆盖率统计的字典：
            - total: 总 ASIN 数
            - has_category: 有分类数据的数量
            - missing_category: 缺少分类数据的数量
            - coverage_rate: 覆盖率 (0-1)
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN category_sub IS NOT NULL AND category_sub != '' THEN 1 ELSE 0 END) as has_category
                FROM asins WHERE keyword = ?
            """, (keyword,))
            row = cursor.fetchone()
            total = row[0] or 0
            has_category = row[1] or 0
            missing_category = total - has_category
            coverage_rate = has_category / total if total > 0 else 0

            return {
                'total': total,
                'has_category': has_category,
                'missing_category': missing_category,
                'coverage_rate': coverage_rate
            }

    def get_asins_missing_category(self, keyword: str) -> List[str]:
        """
        获取缺少分类数据的 ASIN 列表

        Args:
            keyword: 搜索关键词

        Returns:
            ASIN 列表
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT asin FROM asins
                WHERE keyword = ? AND (category_sub IS NULL OR category_sub = '')
            """, (keyword,))
            return [row[0] for row in cursor.fetchall()]

    def update_asin_category(self, keyword: str, asin: str, category_info: Dict) -> bool:
        """
        更新单个 ASIN 的分类信息

        Args:
            keyword: 搜索关键词
            asin: ASIN
            category_info: 分类信息字典

        Returns:
            是否更新成功
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("""
                    UPDATE asins
                    SET category_path = ?, category_main = ?, category_sub = ?
                    WHERE asin = ? AND keyword = ?
                """, (
                    category_info.get('category_path'),
                    category_info.get('category_main'),
                    category_info.get('category_sub'),
                    asin,
                    keyword
                ))
                conn.commit()
                return True
        except Exception:
            return False

    def batch_update_asin_categories(self, keyword: str, category_map: Dict[str, Dict]) -> int:
        """
        批量更新 ASIN 的分类信息

        Args:
            keyword: 搜索关键词
            category_map: ASIN -> 分类信息的映射

        Returns:
            更新成功的数量
        """
        updated = 0
        with sqlite3.connect(str(self.db_path)) as conn:
            for asin, info in category_map.items():
                try:
                    conn.execute("""
                        UPDATE asins
                        SET category_path = ?, category_main = ?, category_sub = ?
                        WHERE asin = ? AND keyword = ?
                    """, (
                        info.get('category_path'),
                        info.get('category_main'),
                        info.get('category_sub'),
                        asin,
                        keyword
                    ))
                    updated += 1
                except Exception:
                    pass
            conn.commit()
        return updated

    def filter_by_price(self, keyword: str, max_price: float) -> Dict[str, any]:
        """
        按价格筛选，只保留价格小于等于阈值的产品

        Args:
            keyword: 搜索关键词
            max_price: 价格阈值，保留小于等于此值的 ASIN

        Returns:
            包含筛选统计的字典：
            - total: 筛选前总数
            - max_price: 价格阈值
            - removed: 删除的数量
            - kept: 保留的数量
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            # 获取筛选前的总数（只统计未被筛选的记录）
            cursor = conn.execute(
                "SELECT COUNT(*) FROM asins WHERE keyword = ? AND filter_status IS NULL",
                (keyword,)
            )
            total = cursor.fetchone()[0]

            if total == 0:
                return {
                    'total': 0,
                    'max_price': max_price,
                    'removed': 0,
                    'kept': 0
                }

            # 标记价格大于阈值的记录
            # price = NULL 或 price = 0 表示没有价格数据，保留这些记录
            cursor = conn.execute("""
                UPDATE asins
                SET filter_status = 'price_filtered'
                WHERE keyword = ? AND price > ? AND filter_status IS NULL
            """, (keyword, max_price))
            removed = cursor.rowcount

            conn.commit()

            kept = total - removed
            return {
                'total': total,
                'max_price': max_price,
                'removed': removed,
                'kept': kept
            }

    def get_price_distribution(self, keyword: str, max_price: float) -> Dict[str, int]:
        """
        获取价格分布统计

        Args:
            keyword: 搜索关键词
            max_price: 价格阈值

        Returns:
            价格分布字典
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            # 无价格数据（只统计未被筛选的记录）
            cursor = conn.execute(
                "SELECT COUNT(*) FROM asins WHERE keyword = ? AND (price IS NULL OR price = 0) AND filter_status IS NULL",
                (keyword,)
            )
            no_data = cursor.fetchone()[0]

            # 价格 <= max_price
            cursor = conn.execute(
                "SELECT COUNT(*) FROM asins WHERE keyword = ? AND price > 0 AND price <= ? AND filter_status IS NULL",
                (keyword, max_price)
            )
            under_threshold = cursor.fetchone()[0]

            # 价格 > max_price
            cursor = conn.execute(
                "SELECT COUNT(*) FROM asins WHERE keyword = ? AND price > ? AND filter_status IS NULL",
                (keyword, max_price)
            )
            over_threshold = cursor.fetchone()[0]

            return {
                'no_data': no_data,
                'under_threshold': under_threshold,
                'over_threshold': over_threshold,
                'total': no_data + under_threshold + over_threshold
            }

    def update_sellerspirit_history(self, keyword: str, asin: str, history_data: Dict) -> bool:
        """
        更新单个 ASIN 的卖家精灵历史数据

        Args:
            keyword: 搜索关键词
            asin: ASIN
            history_data: 历史数据字典，包含：
                - sales_3m: 最近3个月销量
                - price_min: 历史最低价
                - price_max: 历史最高价
                - price_min_date: 最低价日期
                - price_max_date: 最高价日期
                - ss_monthly_sales: 卖家精灵月销量
                - listing_date: 上架日期
                - avg_monthly_sales: 平均月销量
                - sales_months_count: 有销量数据的月份数

        Returns:
            是否更新成功
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("""
                    UPDATE asins
                    SET sales_3m = ?, price_min = ?, price_max = ?,
                        price_min_date = ?, price_max_date = ?, ss_monthly_sales = ?,
                        listing_date = ?, avg_monthly_sales = ?, sales_months_count = ?
                    WHERE asin = ? AND keyword = ?
                """, (
                    history_data.get('sales_3m'),
                    history_data.get('price_min'),
                    history_data.get('price_max'),
                    history_data.get('price_min_date'),
                    history_data.get('price_max_date'),
                    history_data.get('ss_monthly_sales'),
                    history_data.get('listing_date'),
                    history_data.get('avg_monthly_sales'),
                    history_data.get('sales_months_count'),
                    asin,
                    keyword
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"更新卖家精灵历史数据 {asin} 失败: {e}")
            return False

    def batch_update_sellerspirit_history(self, keyword: str, history_map: Dict[str, Dict]) -> int:
        """
        批量更新 ASIN 的卖家精灵历史数据

        当 ScraperAPI 的 rating/reviews_count 为空时，用卖家精灵数据填充

        Args:
            keyword: 搜索关键词
            history_map: ASIN -> 历史数据的映射，包含：
                - sales_3m, ss_monthly_sales, listing_date 等历史数据
                - ss_rating, ss_reviews: 卖家精灵的评分和评论数（用于填充空值）

        Returns:
            更新成功的数量
        """
        updated = 0
        with sqlite3.connect(str(self.db_path)) as conn:
            for asin, data in history_map.items():
                try:
                    # 更新历史数据字段
                    conn.execute("""
                        UPDATE asins
                        SET sales_3m = ?, price_min = ?, price_max = ?,
                            price_min_date = ?, price_max_date = ?, ss_monthly_sales = ?,
                            listing_date = ?, avg_monthly_sales = ?, sales_months_count = ?
                        WHERE asin = ? AND keyword = ?
                    """, (
                        data.get('sales_3m'),
                        data.get('price_min'),
                        data.get('price_max'),
                        data.get('price_min_date'),
                        data.get('price_max_date'),
                        data.get('ss_monthly_sales'),
                        data.get('listing_date'),
                        data.get('avg_monthly_sales'),
                        data.get('sales_months_count'),
                        asin,
                        keyword
                    ))

                    # 当 ScraperAPI 的 rating 为空时，用卖家精灵数据填充
                    ss_rating = data.get('ss_rating')
                    if ss_rating is not None:
                        conn.execute("""
                            UPDATE asins
                            SET rating = ?
                            WHERE asin = ? AND keyword = ? AND (rating IS NULL OR rating = 0)
                        """, (ss_rating, asin, keyword))

                    # 当 ScraperAPI 的 reviews_count 为空时，用卖家精灵数据填充
                    ss_reviews = data.get('ss_reviews')
                    if ss_reviews is not None:
                        conn.execute("""
                            UPDATE asins
                            SET reviews_count = ?
                            WHERE asin = ? AND keyword = ? AND (reviews_count IS NULL OR reviews_count = 0)
                        """, (ss_reviews, asin, keyword))

                    updated += 1
                except Exception:
                    pass
            conn.commit()
        return updated

    def get_asins_for_enrichment(self, keyword: str) -> List[str]:
        """
        获取需要补充历史数据的 ASIN 列表（筛选后的 ASIN）

        Args:
            keyword: 搜索关键词

        Returns:
            ASIN 列表
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT asin FROM asins
                WHERE keyword = ? AND filter_status IS NULL
            """, (keyword,))
            return [row[0] for row in cursor.fetchall()]

    def filter_by_listing_date(self, keyword: str, months: int = 6) -> Dict[str, any]:
        """
        按上架日期筛选，只保留最近 N 个月内上架的新品

        筛选条件（满足任一条件即为老品，会被过滤）：
        1. 上架日期早于截止日期
        2. 有超过 N 个月的销量数据（sales_months_count > months）

        Args:
            keyword: 搜索关键词
            months: 保留最近多少个月的新品（默认 6 个月）

        Returns:
            包含筛选统计的字典：
            - total: 筛选前总数
            - cutoff_date: 截止日期
            - removed: 删除的数量
            - removed_by_date: 因上架日期过滤的数量
            - removed_by_sales_months: 因销量月份数过滤的数量
            - kept: 保留的数量
        """
        from datetime import datetime, timedelta

        # 计算截止日期
        cutoff_date = (datetime.now() - timedelta(days=months * 30)).strftime('%Y-%m-%d')

        with sqlite3.connect(str(self.db_path)) as conn:
            # 获取筛选前的总数（只统计未被筛选的记录）
            cursor = conn.execute(
                "SELECT COUNT(*) FROM asins WHERE keyword = ? AND filter_status IS NULL",
                (keyword,)
            )
            total = cursor.fetchone()[0]

            if total == 0:
                return {
                    'total': 0,
                    'cutoff_date': cutoff_date,
                    'removed': 0,
                    'removed_by_date': 0,
                    'removed_by_sales_months': 0,
                    'kept': 0
                }

            # 1. 标记上架日期早于截止日期的记录（老品）
            cursor = conn.execute("""
                UPDATE asins
                SET filter_status = 'listing_date_filtered'
                WHERE keyword = ? AND listing_date IS NOT NULL
                    AND listing_date < ? AND filter_status IS NULL
            """, (keyword, cutoff_date))
            removed_by_date = cursor.rowcount

            # 2. 标记销量数据超过 N 个月的记录（老品）
            cursor = conn.execute("""
                UPDATE asins
                SET filter_status = 'sales_months_filtered'
                WHERE keyword = ? AND sales_months_count IS NOT NULL
                    AND sales_months_count > ? AND filter_status IS NULL
            """, (keyword, months))
            removed_by_sales_months = cursor.rowcount

            conn.commit()

            removed = removed_by_date + removed_by_sales_months
            kept = total - removed
            return {
                'total': total,
                'cutoff_date': cutoff_date,
                'removed': removed,
                'removed_by_date': removed_by_date,
                'removed_by_sales_months': removed_by_sales_months,
                'kept': kept
            }

    def get_listing_date_distribution(self, keyword: str, months: int = 6) -> Dict[str, int]:
        """
        获取上架日期和销量月份数分布统计

        Args:
            keyword: 搜索关键词
            months: 新品阈值（月数）

        Returns:
            分布统计字典
        """
        from datetime import datetime, timedelta

        cutoff_date = (datetime.now() - timedelta(days=months * 30)).strftime('%Y-%m-%d')

        with sqlite3.connect(str(self.db_path)) as conn:
            # 无上架日期数据（只统计未被筛选的记录）
            cursor = conn.execute(
                "SELECT COUNT(*) FROM asins WHERE keyword = ? AND listing_date IS NULL AND filter_status IS NULL",
                (keyword,)
            )
            no_date_data = cursor.fetchone()[0]

            # 新品（上架日期 >= cutoff_date）
            cursor = conn.execute(
                "SELECT COUNT(*) FROM asins WHERE keyword = ? AND listing_date >= ? AND filter_status IS NULL",
                (keyword, cutoff_date)
            )
            new_by_date = cursor.fetchone()[0]

            # 老品（上架日期 < cutoff_date）
            cursor = conn.execute(
                "SELECT COUNT(*) FROM asins WHERE keyword = ? AND listing_date IS NOT NULL AND listing_date < ? AND filter_status IS NULL",
                (keyword, cutoff_date)
            )
            old_by_date = cursor.fetchone()[0]

            # 销量月份数 > months（老品）
            cursor = conn.execute(
                "SELECT COUNT(*) FROM asins WHERE keyword = ? AND sales_months_count IS NOT NULL AND sales_months_count > ? AND filter_status IS NULL",
                (keyword, months)
            )
            old_by_sales_months = cursor.fetchone()[0]

            # 销量月份数 <= months（新品）
            cursor = conn.execute(
                "SELECT COUNT(*) FROM asins WHERE keyword = ? AND sales_months_count IS NOT NULL AND sales_months_count <= ? AND filter_status IS NULL",
                (keyword, months)
            )
            new_by_sales_months = cursor.fetchone()[0]

            # 无销量月份数据
            cursor = conn.execute(
                "SELECT COUNT(*) FROM asins WHERE keyword = ? AND sales_months_count IS NULL AND filter_status IS NULL",
                (keyword,)
            )
            no_sales_months_data = cursor.fetchone()[0]

            # 总数
            cursor = conn.execute(
                "SELECT COUNT(*) FROM asins WHERE keyword = ? AND filter_status IS NULL",
                (keyword,)
            )
            total = cursor.fetchone()[0]

            return {
                'no_date_data': no_date_data,
                'new_by_date': new_by_date,
                'old_by_date': old_by_date,
                'no_sales_months_data': no_sales_months_data,
                'new_by_sales_months': new_by_sales_months,
                'old_by_sales_months': old_by_sales_months,
                'total': total,
                'cutoff_date': cutoff_date
            }

    def get_filtered_asins(self, keyword: str, order_by: str = 'price') -> List[Dict]:
        """
        获取筛选后的 ASIN 数据（filter_status IS NULL）

        Args:
            keyword: 搜索关键词
            order_by: 排序字段，默认按价格排序

        Returns:
            ASIN 数据列表
        """
        valid_order_fields = ['price', 'sales_volume', 'rating', 'reviews_count', 'page_rank']
        if order_by not in valid_order_fields:
            order_by = 'price'

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(f"""
                SELECT asin, name, brand, category_sub, category_main, category_path,
                       price, rating, reviews_count, sales_volume, page_rank, url,
                       sales_3m, price_min, price_max, price_min_date, price_max_date, ss_monthly_sales,
                       listing_date, avg_monthly_sales, sales_months_count
                FROM asins
                WHERE keyword = ? AND filter_status IS NULL
                ORDER BY {order_by} ASC NULLS LAST
            """, (keyword,))
            rows = cursor.fetchall()

            results = []
            for row in rows:
                results.append({
                    'asin': row['asin'],
                    'name': row['name'],
                    'brand': row['brand'],
                    'category_sub': row['category_sub'],
                    'category_main': row['category_main'],
                    'category_path': row['category_path'],
                    'price': row['price'],
                    'rating': row['rating'],
                    'reviews_count': row['reviews_count'],
                    'sales_volume': row['sales_volume'],
                    'page_rank': row['page_rank'],
                    'url': row['url'],
                    'sales_3m': row['sales_3m'],
                    'price_min': row['price_min'],
                    'price_max': row['price_max'],
                    'price_min_date': row['price_min_date'],
                    'price_max_date': row['price_max_date'],
                    'ss_monthly_sales': row['ss_monthly_sales'],
                    'listing_date': row['listing_date'],
                    'avg_monthly_sales': row['avg_monthly_sales'],
                    'sales_months_count': row['sales_months_count']
                })
            return results

    def update_price_history(self, keyword: str, asin: str, price_data: Dict) -> bool:
        """
        更新单个 ASIN 的价格历史数据

        Args:
            keyword: 搜索关键词
            asin: ASIN
            price_data: 价格历史数据字典，包含：
                - price_min: 历史最低价
                - price_max: 历史最高价
                - price_min_date: 最低价日期
                - price_max_date: 最高价日期

        Returns:
            是否更新成功
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("""
                    UPDATE asins
                    SET price_min = ?, price_max = ?, price_min_date = ?, price_max_date = ?
                    WHERE asin = ? AND keyword = ?
                """, (
                    price_data.get('price_min'),
                    price_data.get('price_max'),
                    price_data.get('price_min_date'),
                    price_data.get('price_max_date'),
                    asin,
                    keyword
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"更新价格历史 {asin} 失败: {e}")
            return False

    # ==================== 卖家精灵历史数据缓存方法 ====================

    def get_cached_sellerspirit_history(self, asins: List[str], cache_days: int = 20) -> Dict[str, Dict]:
        """
        获取缓存的卖家精灵历史数据（在缓存有效期内）

        Args:
            asins: ASIN 列表
            cache_days: 缓存有效期（天），默认 20 天

        Returns:
            ASIN -> 历史数据的映射
        """
        if not asins:
            return {}

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            # 使用参数化查询，避免 SQL 注入
            placeholders = ','.join('?' * len(asins))
            cursor = conn.execute(f"""
                SELECT asin, sales_3m, ss_monthly_sales, listing_date,
                       avg_monthly_sales, sales_months_count, ss_rating, ss_reviews
                FROM sellerspirit_history_cache
                WHERE asin IN ({placeholders})
                AND datetime(updated_at) >= datetime('now', '-{cache_days} days')
            """, asins)
            rows = cursor.fetchall()

            result = {}
            for row in rows:
                result[row['asin']] = {
                    'sales_3m': row['sales_3m'],
                    'ss_monthly_sales': row['ss_monthly_sales'],
                    'listing_date': row['listing_date'],
                    'avg_monthly_sales': row['avg_monthly_sales'],
                    'sales_months_count': row['sales_months_count'],
                    'ss_rating': row['ss_rating'],
                    'ss_reviews': row['ss_reviews']
                }
            return result

    def save_sellerspirit_history_cache(self, history_map: Dict[str, Dict]) -> int:
        """
        保存卖家精灵历史数据到缓存

        Args:
            history_map: ASIN -> 历史数据的映射

        Returns:
            保存成功的数量
        """
        import json
        saved_count = 0
        with sqlite3.connect(str(self.db_path)) as conn:
            for asin, data in history_map.items():
                try:
                    # 使用 INSERT OR REPLACE 更新缓存
                    conn.execute("""
                        INSERT OR REPLACE INTO sellerspirit_history_cache
                        (asin, sales_3m, ss_monthly_sales, listing_date,
                         avg_monthly_sales, sales_months_count, ss_rating, ss_reviews,
                         raw_trends, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """, (
                        asin,
                        data.get('sales_3m'),
                        data.get('ss_monthly_sales'),
                        data.get('listing_date'),
                        data.get('avg_monthly_sales'),
                        data.get('sales_months_count'),
                        data.get('ss_rating'),
                        data.get('ss_reviews'),
                        json.dumps(data.get('raw_trends'), ensure_ascii=False) if data.get('raw_trends') else None
                    ))
                    saved_count += 1
                except Exception as e:
                    logger.error(f"保存卖家精灵历史缓存 {asin} 失败: {e}")
            conn.commit()
        return saved_count

    def get_asins_needing_history_fetch(self, asins: List[str], cache_days: int = 20) -> List[str]:
        """
        获取需要从 API 获取历史数据的 ASIN 列表（排除已缓存的）

        Args:
            asins: 待检查的 ASIN 列表
            cache_days: 缓存有效期（天），默认 20 天

        Returns:
            需要获取的 ASIN 列表
        """
        if not asins:
            return []

        cached_data = self.get_cached_sellerspirit_history(asins, cache_days)
        return [asin for asin in asins if asin not in cached_data]
