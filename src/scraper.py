"""
主抓取器模块
提供 BatchScraper 类，执行完整的抓取流程
"""

import sys
import time
import csv
import importlib.util
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# 添加 data_summary 路径
DATA_SUMMARY_PATH = Path(__file__).parent.parent.parent / "data_summary"
sys.path.insert(0, str(DATA_SUMMARY_PATH))
sys.path.insert(0, str(DATA_SUMMARY_PATH / "external_apis"))

from amazon_scraper import AmazonScraper

# 尝试导入卖家精灵采集器（可选依赖）- 使用动态导入避免包名冲突
SELLERSPIRIT_AVAILABLE = False
SellerSpiritCollector = None
try:
    spec = importlib.util.spec_from_file_location(
        "sellerspirit_collector",
        DATA_SUMMARY_PATH / "src" / "collectors" / "sellerspirit_collector.py"
    )
    if spec and spec.loader:
        sellerspirit_collector_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sellerspirit_collector_module)
        SellerSpiritCollector = sellerspirit_collector_module.SellerSpiritCollector
        SELLERSPIRIT_AVAILABLE = True
except Exception:
    pass

# 尝试导入卖家精灵 Hook（用于补充 ASIN 数据）- 使用动态导入
SELLERSPIRIT_HOOK_AVAILABLE = False
sellerspirit_hook = None
try:
    spec = importlib.util.spec_from_file_location(
        "sellerspirit_hook",
        DATA_SUMMARY_PATH / "src" / "collectors" / "sellerspirit_hook.py"
    )
    if spec and spec.loader:
        sellerspirit_hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sellerspirit_hook)
        SELLERSPIRIT_HOOK_AVAILABLE = True
except Exception:
    pass

from .database import BatchScraperDB
from .category import analyze_category_distribution, print_category_stats, extract_product_types
from .utils import chunk_list
from .logger import setup_logger

# 初始化日志
logger = setup_logger("scraper")

# 尝试导入 AI 分析器
try:
    from .ai_analyzer import GeminiCategoryAnalyzer, GEMINI_AVAILABLE
except ImportError:
    GEMINI_AVAILABLE = False

# 尝试导入 Apify 价格获取器
try:
    from .apify_price import ApifyPriceFetcher, is_apify_available, APIFY_AVAILABLE
except ImportError:
    APIFY_AVAILABLE = False
    is_apify_available = lambda: False


class BatchScraper:
    """大批量 ASIN 抓取器"""

    def __init__(
        self,
        api_key: str,
        db_path: str = "data/batch_scraper.db",
        use_sellerspirit: bool = True,
        use_ai_filter: bool = False,
        gemini_api_key: str = None
    ):
        """
        初始化抓取器

        Args:
            api_key: ScraperAPI 密钥
            db_path: 数据库路径
            use_sellerspirit: 是否使用卖家精灵分类数据
            use_ai_filter: 是否使用 AI 筛选（每个分类只保留前100个相关产品）
            gemini_api_key: Gemini API 密钥（默认从环境变量读取）
        """
        self.scraper = AmazonScraper(
            api_key=api_key,
            max_concurrent=10,
            max_retries=5,
            request_timeout=60
        )
        self.db = BatchScraperDB(db_path)
        self.use_sellerspirit = use_sellerspirit and SELLERSPIRIT_AVAILABLE
        self._sellerspirit_cache = {}

        # AI 筛选配置
        self.use_ai_filter = use_ai_filter and GEMINI_AVAILABLE
        self.gemini_api_key = gemini_api_key
        self._ai_analyzer = None

        if self.use_ai_filter:
            try:
                self._ai_analyzer = GeminiCategoryAnalyzer(api_key=gemini_api_key)
                logger.info("  [AI] Gemini 分类分析器已启用")
            except Exception as e:
                logger.error(f"  [AI] Gemini 初始化失败: {e}")
                self.use_ai_filter = False

    def _format_duration(self, seconds: float) -> str:
        """格式化时间显示"""
        if seconds >= 3600:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours} 小时 {minutes} 分钟"
        elif seconds >= 60:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes} 分钟 {secs} 秒"
        else:
            return f"{seconds:.1f} 秒"

    def scrape_keyword(
        self,
        keyword: str,
        country_code: str = 'us',
        max_pages: int = 100,
        sales_threshold: int = 10
    ) -> Dict[str, Any]:
        """
        步骤1：抓取关键词的所有 ASIN

        Args:
            keyword: 搜索关键词
            country_code: 国家代码
            max_pages: 最大页数
            sales_threshold: 销量阈值

        Returns:
            抓取结果字典
        """
        logger.info(f"{'='*60}")
        logger.info(f"[步骤1] 抓取关键词: {keyword}")
        logger.info(f"{'='*60}")

        # 检查当天是否已有数据
        if self.db.has_today_data(keyword, 'keyword_search'):
            cached_results = self.db.get_today_asins(keyword, 'keyword_search')
            logger.info(f"✓ 使用当天缓存数据:")
            logger.info(f"  - 缓存 ASIN 数: {len(cached_results)}")
            logger.info(f"  - 来源: 数据库 (当天已抓取)")

            return {
                'success': True,
                'keyword': keyword,
                'search_results': cached_results,
                'pages_scraped': 0,
                'saved_count': len(cached_results),
                'from_cache': True
            }

        task_id = self.db.create_task(keyword, 'initial')

        try:
            result = self.scraper.search_keyword_with_smart_stop(
                keyword=keyword,
                country_code=country_code,
                max_pages=max_pages,
                sales_threshold=sales_threshold,
                fetch_product_details=False,
                show_progress=True
            )

            search_results = result.get('search_results', [])
            pages_scraped = result.get('pages_scraped', 0)

            # 保存到数据库
            saved_count = self.db.save_asins(
                search_results, keyword, 'keyword_search', keyword
            )

            self.db.update_task(task_id, 'completed', saved_count, pages_scraped)

            logger.info(f"✓ 关键词抓取完成:")
            logger.info(f"  - 抓取页数: {pages_scraped}")
            logger.info(f"  - 保存 ASIN: {saved_count}")
            logger.info(f"  - 停止原因: {result.get('stop_reason', 'N/A')}")

            return {
                'success': True,
                'keyword': keyword,
                'search_results': search_results,
                'pages_scraped': pages_scraped,
                'saved_count': saved_count,
                'from_cache': False
            }

        except Exception as e:
            self.db.update_task(task_id, 'failed', error_message=str(e))
            logger.error(f"✗ 关键词抓取失败: {e}")
            return {'success': False, 'error': str(e)}

    def _fetch_sellerspirit_data(self, keyword: str) -> Dict[str, Dict]:
        """从卖家精灵获取分类数据（支持当天缓存）"""
        if not self.use_sellerspirit:
            return {}

        if keyword in self._sellerspirit_cache:
            return self._sellerspirit_cache[keyword]

        # 检查数据库中是否有当天的数据
        if self.db.has_today_sellerspirit_data(keyword):
            cached_data = self.db.get_today_sellerspirit_data(keyword)
            if cached_data:
                logger.info(f"  ✓ 使用当天缓存的卖家精灵数据: {len(cached_data)} 个 ASIN")
                self._sellerspirit_cache[keyword] = cached_data
                return cached_data

        logger.info(f"  正在从卖家精灵获取分类数据...")

        try:
            collector = SellerSpiritCollector()
            aggregated_data, asin_list, brand_list = collector.collect_data(
                keyword=keyword,
                wait_time=60,
                max_wait=300,
                force_download=False
            )

            category_map = {}
            for product in asin_list:
                if product.asin:
                    category_map[product.asin] = {
                        'category_path': product.category_path,
                        'category_main': product.category_main,
                        'category_sub': product.category_sub
                    }

            logger.info(f"  ✓ 卖家精灵数据获取成功: {len(category_map)} 个 ASIN")

            # 保存到数据库
            if category_map:
                saved = self.db.save_sellerspirit_data(keyword, category_map, source='collector')
                logger.info(f"  ✓ 卖家精灵数据已保存: {saved} 条")

            self._sellerspirit_cache[keyword] = category_map
            return category_map

        except Exception as e:
            logger.error(f"  ✗ 卖家精灵数据获取失败: {e}")
            logger.warning(f"  将使用关键词匹配方式进行分类")
            return {}

    def _fetch_sellerspirit_hook_data(self, asins: List[str], keyword: str = None) -> Dict[str, Dict]:
        """使用卖家精灵 Hook 补充 ASIN 分类数据（支持当天缓存）"""
        if not SELLERSPIRIT_HOOK_AVAILABLE or not asins:
            return {}

        # 如果提供了 keyword，先检查数据库中已有的数据
        cached_data = {}
        asins_to_fetch = asins
        if keyword and self.db.has_today_sellerspirit_data(keyword):
            cached_data = self.db.get_today_sellerspirit_data(keyword)
            # 过滤出需要获取的 ASIN
            asins_to_fetch = [asin for asin in asins if asin not in cached_data]
            if cached_data:
                logger.info(f"  ✓ 从缓存获取 {len(cached_data)} 个 ASIN 的分类数据")

        if not asins_to_fetch:
            return cached_data

        logger.info(f"  正在使用卖家精灵 Hook 补充 {len(asins_to_fetch)} 个 ASIN...")

        try:
            token = sellerspirit_hook.login()
            if not token:
                logger.error(f"  ✗ 卖家精灵 Hook 登录失败")
                return cached_data

            sellerspirit_hook.token = token
            category_map = {}
            chunks = chunk_list(asins_to_fetch, 40)

            for i, chunk in enumerate(chunks):
                asins_str = ",".join(chunk)
                data = sellerspirit_hook.getData(asins_str)

                if data:
                    for item in data:
                        asin = item.get('asin')
                        if asin:
                            node_label_path = item.get('node_label_path') or ''
                            parts = node_label_path.split(':') if node_label_path else []

                            category_main = parts[0] if len(parts) > 0 else ''
                            category_sub = parts[-1] if len(parts) > 1 else category_main
                            category_path = ' > '.join(parts) if parts else ''

                            if not category_sub:
                                bsr_list = item.get('bsrList') or []
                                if bsr_list:
                                    category_main = bsr_list[0].get('label', '') if len(bsr_list) > 0 else ''
                                    category_sub = bsr_list[-1].get('label', '') if len(bsr_list) > 1 else category_main

                            if category_sub:
                                category_map[asin] = {
                                    'category_path': category_path,
                                    'category_main': category_main,
                                    'category_sub': category_sub
                                }

                if i < len(chunks) - 1:
                    time.sleep(2)

            logger.info(f"  ✓ Hook 补充成功: {len(category_map)} 个 ASIN")

            # 保存到数据库
            if category_map and keyword:
                saved = self.db.save_sellerspirit_data(keyword, category_map, source='hook')
                logger.info(f"  ✓ Hook 数据已保存: {saved} 条")

            # 合并缓存数据和新获取的数据
            cached_data.update(category_map)
            return cached_data

        except Exception as e:
            logger.error(f"  ✗ 卖家精灵 Hook 失败: {e}")
            return cached_data

    def fetch_sellerspirit_categories(self, keyword: str, search_results: List[Dict]) -> Dict[str, Any]:
        """
        步骤1.5：获取卖家精灵分类数据并更新 ASIN
        支持两种方式：卖家精灵采集器 或 Hook API
        """
        logger.info(f"{'='*60}")
        logger.info(f"[步骤1.5] 获取分类数据")
        logger.info(f"{'='*60}")

        # 检查数据是否已有分类信息
        has_category_data = sum(1 for item in search_results if item.get('category_sub'))
        if has_category_data > len(search_results) * 0.5:
            logger.info(f"  数据已有分类信息 ({has_category_data}/{len(search_results)})，跳过")
            return {'success': True, 'updated_count': has_category_data, 'use_sellerspirit': True}

        ss_category_map = {}

        # 方式1：使用卖家精灵采集器（如果启用）
        if self.use_sellerspirit:
            logger.info(f"  尝试使用卖家精灵采集器...")
            ss_category_map = self._fetch_sellerspirit_data(keyword)

        # 更新 search_results 中的分类信息
        updated_count = 0
        missing_asins = []

        for item in search_results:
            asin = item.get('asin')
            if not asin:
                continue
            if item.get('category_sub'):
                updated_count += 1
                continue
            if asin in ss_category_map:
                ss_info = ss_category_map[asin]
                item['category_path'] = ss_info.get('category_path')
                item['category_main'] = ss_info.get('category_main')
                item['category_sub'] = ss_info.get('category_sub')
                updated_count += 1
            else:
                missing_asins.append(asin)

        if ss_category_map:
            logger.info(f"  ✓ 卖家精灵采集器: {updated_count} 个 ASIN")

        # 方式2：使用 Hook 补充缺失的 ASIN（无论卖家精灵是否启用）
        hook_updated = 0
        if missing_asins and SELLERSPIRIT_HOOK_AVAILABLE:
            logger.info(f"  使用 Hook 获取 {len(missing_asins)} 个 ASIN 的分类数据...")
            hook_category_map = self._fetch_sellerspirit_hook_data(missing_asins, keyword)

            if hook_category_map:
                for item in search_results:
                    asin = item.get('asin')
                    if asin and asin in hook_category_map and not item.get('category_sub'):
                        hook_info = hook_category_map[asin]
                        item['category_path'] = hook_info.get('category_path')
                        item['category_main'] = hook_info.get('category_main')
                        item['category_sub'] = hook_info.get('category_sub')
                        hook_updated += 1

                ss_category_map.update(hook_category_map)

            logger.info(f"  ✓ Hook 获取: {hook_updated} 个 ASIN")
        elif missing_asins and not SELLERSPIRIT_HOOK_AVAILABLE:
            logger.warning(f"  Hook 不可用，{len(missing_asins)} 个 ASIN 无法获取分类数据")

        total_updated = updated_count + hook_updated

        if total_updated > 0:
            self.db.save_asins(search_results, keyword, 'keyword_search', keyword)
            logger.info(f"  ✓ 总计更新 {total_updated} 个 ASIN 的分类信息")
        else:
            logger.warning("  未能获取分类数据，将使用动态关键词提取")

        return {
            'success': True,
            'updated_count': total_updated,
            'use_sellerspirit': total_updated > 0,
            'category_map': ss_category_map
        }

    def analyze_categories(
        self,
        keyword: str,
        search_results: List[Dict],
        use_sellerspirit: bool = None,
        ai_filter_limit: int = 10
    ) -> List[Dict]:
        """
        步骤2：分析类目分布

        Args:
            keyword: 搜索关键词
            search_results: 搜索结果列表
            use_sellerspirit: 是否使用卖家精灵分类数据
            ai_filter_limit: AI 筛选后保留的最大分类数量
        """
        logger.info(f"{'='*60}")
        logger.info(f"[步骤2] 分析产品类型分布")
        if self.use_ai_filter:
            logger.info(f"  [AI 筛选已启用，将筛选与关键词相关的分类]")
        logger.info(f"{'='*60}")

        has_ss_data = any(item.get('category_sub') for item in search_results)

        if use_sellerspirit is None:
            use_sellerspirit = has_ss_data

        if use_sellerspirit and has_ss_data:
            logger.info(f"  使用卖家精灵分类数据")
        else:
            use_sellerspirit = False
            logger.info(f"  使用动态关键词提取分类")
            product_type_keywords = extract_product_types(
                search_results, keyword, min_count=3, top_n=30
            )
            logger.info(f"  发现 {len(product_type_keywords)} 个高频产品类型词组")
            if product_type_keywords:
                logger.info(f"  前10个: {', '.join(product_type_keywords[:10])}")

        stats = analyze_category_distribution(search_results, keyword, use_sellerspirit)
        self.db.save_category_stats(keyword, stats)
        print_category_stats(stats, use_sellerspirit)

        # AI 筛选：过滤与关键词相关的分类
        if self.use_ai_filter and self._ai_analyzer and stats:
            logger.info(f"\n[步骤2.5] AI 筛选相关分类")
            stats = self._ai_analyzer.filter_categories(
                stats,
                keyword,
                max_categories=ai_filter_limit
            )
            logger.info(f"  筛选后保留 {len(stats)} 个相关分类")

        return stats

    def scrape_top_categories(
        self,
        keyword: str,
        category_stats: List[Dict],
        top_n: int = 3,
        country_code: str = 'us',
        max_pages_per_category: int = 50,
        sales_threshold: int = 10
    ) -> Dict[str, Any]:
        """
        步骤3：抓取前 N 个热门产品类型的更多 ASIN

        Args:
            keyword: 搜索关键词
            category_stats: 分类统计列表（已经过 AI 筛选）
            top_n: 抓取前 N 个分类
            country_code: 国家代码
            max_pages_per_category: 每个分类最大页数
            sales_threshold: 销量阈值
        """
        logger.info(f"{'='*60}")
        logger.info(f"[步骤3] 抓取前 {top_n} 个热门产品类型")
        logger.info(f"{'='*60}")

        valid_categories = [s for s in category_stats if s['category'] != 'Other']
        top_categories = valid_categories[:top_n]

        if not top_categories:
            logger.warning("没有找到有效的产品类型，跳过类目扩展")
            return {'success': True, 'categories_scraped': 0, 'new_asins': 0}

        all_results = []

        for i, stat in enumerate(top_categories, 1):
            product_type = stat['category']
            logger.info(f"--- [{i}/{len(top_categories)}] 产品类型: {product_type} ---")

            # 检查当天是否已有该分类的数据
            if self.db.has_today_category_data(keyword, 'category_search', product_type):
                logger.info(f"  ✓ 跳过: 当天已抓取过该分类")
                continue

            task_id = self.db.create_task(keyword, f'category_expansion:{product_type}')

            try:
                search_query = f"{keyword} {product_type.lower()}"
                logger.info(f"  搜索: {search_query}")

                result = self.scraper.search_keyword_with_smart_stop(
                    keyword=search_query,
                    country_code=country_code,
                    max_pages=max_pages_per_category,
                    sales_threshold=sales_threshold,
                    fetch_product_details=False,
                    show_progress=True
                )

                search_results = result.get('search_results', [])
                pages_scraped = result.get('pages_scraped', 0)

                existing_asins = self.db.get_existing_asins(keyword)
                new_results = [r for r in search_results if r.get('asin') and r.get('asin') not in existing_asins]

                saved_count = self.db.save_asins(
                    new_results, keyword, 'category_search', product_type
                )

                self.db.update_task(task_id, 'completed', saved_count, pages_scraped)
                logger.info(f"  ✓ 完成: 抓取 {len(search_results)} 个, 新增 {saved_count} 个")

                all_results.extend(new_results)

            except Exception as e:
                self.db.update_task(task_id, 'failed', error_message=str(e))
                logger.error(f"  ✗ 失败: {e}")

        return {
            'success': True,
            'categories_scraped': len(top_categories),
            'new_asins': len(all_results)
        }

    def scrape_round3(
        self,
        keyword: str,
        search_results: List[Dict],
        top_n_asins: int = 300,
        top_n_categories: int = 3,
        country_code: str = 'us',
        max_pages_per_category: int = 50,
        sales_threshold: int = 10
    ) -> Dict[str, Any]:
        """
        步骤4（第3轮抓取）：对前N个ASIN进行分类分析并扩展抓取

        流程：
        1. 从步骤2的结果中取前300个ASIN
        2. 使用卖家精灵hook获取这些ASIN的分类数据
        3. 分析分类分布
        4. 抓取前3个分类的更多ASIN

        Args:
            keyword: 搜索关键词
            search_results: 步骤2的搜索结果列表
            top_n_asins: 取前N个ASIN进行分析（默认300）
            top_n_categories: 抓取前N个分类（默认3）
            country_code: 国家代码
            max_pages_per_category: 每个分类最大页数
            sales_threshold: 销量阈值

        Returns:
            抓取结果字典
        """
        logger.info(f"{'='*60}")
        logger.info(f"[步骤4] 第3轮抓取 - 深度分类扩展")
        logger.info(f"{'='*60}")

        if not SELLERSPIRIT_HOOK_AVAILABLE:
            logger.warning("  卖家精灵 Hook 不可用，跳过第3轮抓取")
            return {'success': False, 'error': 'sellerspirit_hook not available'}

        # 1. 取前N个ASIN
        top_asins = []
        for item in search_results[:top_n_asins]:
            asin = item.get('asin')
            if asin:
                top_asins.append(asin)

        if not top_asins:
            logger.warning("  没有可用的ASIN，跳过第3轮抓取")
            return {'success': False, 'error': 'no asins available'}

        logger.info(f"  选取前 {len(top_asins)} 个ASIN进行深度分析")

        # 2. 使用卖家精灵hook获取分类数据
        logger.info(f"  正在获取 {len(top_asins)} 个ASIN的分类数据...")
        category_map = self._fetch_sellerspirit_hook_data(top_asins, keyword)

        if not category_map:
            logger.warning("  无法获取分类数据，跳过第3轮抓取")
            return {'success': False, 'error': 'failed to fetch category data'}

        logger.info(f"  成功获取 {len(category_map)} 个ASIN的分类数据")

        # 3. 分析分类分布
        logger.info(f"  分析分类分布...")
        category_counts = {}
        for asin, info in category_map.items():
            category_sub = info.get('category_sub', '')
            if category_sub:
                if category_sub not in category_counts:
                    category_counts[category_sub] = {
                        'category': category_sub,
                        'category_main': info.get('category_main', ''),
                        'count': 0,
                        'asins': []
                    }
                category_counts[category_sub]['count'] += 1
                category_counts[category_sub]['asins'].append(asin)

        # 按数量排序
        sorted_categories = sorted(
            category_counts.values(),
            key=lambda x: x['count'],
            reverse=True
        )

        logger.info(f"  分类分布（前10）:")
        for i, cat in enumerate(sorted_categories[:10], 1):
            logger.info(f"    {i}. {cat['category']}: {cat['count']} 个ASIN")

        # 4. 抓取前N个分类
        top_categories_list = sorted_categories[:top_n_categories]

        if not top_categories_list:
            logger.warning("  没有有效分类，跳过抓取")
            return {'success': True, 'categories_scraped': 0, 'new_asins': 0}

        logger.info(f"  开始抓取前 {len(top_categories_list)} 个分类...")

        all_results = []
        existing_asins = self.db.get_existing_asins(keyword)

        # 获取步骤3已抓取的分类（小写），用于去重
        step3_scraped_categories = self.db.get_today_scraped_categories(keyword, 'category_search')
        if step3_scraped_categories:
            logger.info(f"  步骤3已抓取 {len(step3_scraped_categories)} 个分类，将跳过重复分类")

        for i, cat_info in enumerate(top_categories_list, 1):
            category_name = cat_info['category']

            # 检查是否已在步骤3中抓取过该分类
            if category_name.lower() in step3_scraped_categories:
                logger.info(f"--- [{i}/{len(top_categories_list)}] 分类: {category_name} (已在步骤3抓取，跳过) ---")
                continue

            logger.info(f"--- [{i}/{len(top_categories_list)}] 分类: {category_name} (来自 {cat_info['count']} 个ASIN) ---")

            # 检查当天是否已有该分类的数据（步骤4自身的去重）
            if self.db.has_today_category_data(keyword, 'round3_category', category_name):
                logger.info(f"  ✓ 跳过: 当天已抓取过该分类")
                continue

            task_id = self.db.create_task(keyword, f'round3_category:{category_name}')

            try:
                # 构建搜索查询
                search_query = f"{keyword} {category_name.lower()}"
                logger.info(f"  搜索: {search_query}")

                result = self.scraper.search_keyword_with_smart_stop(
                    keyword=search_query,
                    country_code=country_code,
                    max_pages=max_pages_per_category,
                    sales_threshold=sales_threshold,
                    fetch_product_details=False,
                    show_progress=True
                )

                search_results_cat = result.get('search_results', [])
                pages_scraped = result.get('pages_scraped', 0)

                # 过滤已存在的ASIN
                new_results = [
                    r for r in search_results_cat
                    if r.get('asin') and r.get('asin') not in existing_asins
                ]

                # 保存到数据库
                saved_count = self.db.save_asins(
                    new_results, keyword, 'round3_category', category_name
                )

                self.db.update_task(task_id, 'completed', saved_count, pages_scraped)
                logger.info(f"  完成: 抓取 {len(search_results_cat)} 个, 新增 {saved_count} 个")

                # 更新已存在集合
                for r in new_results:
                    if r.get('asin'):
                        existing_asins.add(r['asin'])

                all_results.extend(new_results)

            except Exception as e:
                self.db.update_task(task_id, 'failed', error_message=str(e))
                logger.error(f"  失败: {e}")

        logger.info(f"  [步骤4完成] 第3轮抓取新增 {len(all_results)} 个ASIN")

        return {
            'success': True,
            'categories_scraped': len(top_categories_list),
            'new_asins': len(all_results),
            'category_distribution': [
                {'category': c['category'], 'count': c['count']}
                for c in sorted_categories[:10]
            ]
        }

    def filter_by_sponsored(self, keyword: str) -> Dict[str, Any]:
        """
        步骤5：剔除广告 ASIN

        Args:
            keyword: 搜索关键词

        Returns:
            筛选结果字典
        """
        logger.info(f"{'='*60}")
        logger.info(f"[步骤5] 广告筛选 - 剔除广告 ASIN")
        logger.info(f"{'='*60}")

        # 获取筛选前的广告分布
        distribution = self.db.get_sponsored_distribution(keyword)
        logger.info(f"  筛选前广告分布:")
        logger.info(f"    - 广告 ASIN: {distribution['sponsored']} 个")
        logger.info(f"    - 自然 ASIN: {distribution['organic']} 个")
        logger.info(f"    - 总计: {distribution['total']} 个")

        # 执行筛选
        result = self.db.filter_sponsored_asins(keyword)

        logger.info(f"  ✓ 筛选完成:")
        logger.info(f"    - 删除广告 ASIN: {result['removed']} 个")
        logger.info(f"    - 保留自然 ASIN: {result['kept']} 个")

        return {
            'success': True,
            'total_before': result['total'],
            'sponsored_count': result['sponsored_count'],
            'removed': result['removed'],
            'kept': result['kept'],
            'distribution_before': distribution
        }

    def fill_missing_categories(self, keyword: str, min_coverage: float = 0.9) -> Dict[str, Any]:
        """
        补充缺失的分类数据

        当分类数据覆盖率低于阈值时，使用卖家精灵 Hook 补充分类数据

        Args:
            keyword: 搜索关键词
            min_coverage: 最低覆盖率阈值（默认 0.9 即 90%）

        Returns:
            补充结果字典
        """
        # 检查覆盖率
        coverage = self.db.get_category_coverage(keyword)
        total = coverage['total']
        has_category = coverage['has_category']
        coverage_rate = coverage['coverage_rate']

        logger.info(f"  分类数据覆盖率: {has_category}/{total} ({coverage_rate*100:.1f}%)")

        if coverage_rate >= min_coverage:
            logger.info(f"  ✓ 覆盖率已达标 (>= {min_coverage*100:.0f}%)，无需补充")
            return {
                'success': True,
                'needed': False,
                'coverage_before': coverage_rate,
                'coverage_after': coverage_rate,
                'filled_count': 0
            }

        if not SELLERSPIRIT_HOOK_AVAILABLE:
            logger.warning(f"  ✗ 卖家精灵 Hook 不可用，无法补充分类数据")
            return {
                'success': False,
                'needed': True,
                'coverage_before': coverage_rate,
                'coverage_after': coverage_rate,
                'filled_count': 0,
                'error': 'sellerspirit_hook not available'
            }

        # 获取缺失分类的 ASIN
        missing_asins = self.db.get_asins_missing_category(keyword)
        logger.info(f"  需要补充 {len(missing_asins)} 个 ASIN 的分类数据...")

        # 使用 Hook 获取分类数据
        category_map = self._fetch_category_via_hook(missing_asins)

        if not category_map:
            logger.warning(f"  ✗ Hook 未能获取分类数据")
            return {
                'success': False,
                'needed': True,
                'coverage_before': coverage_rate,
                'coverage_after': coverage_rate,
                'filled_count': 0,
                'error': 'hook returned no data'
            }

        # 更新数据库
        updated = self.db.batch_update_asin_categories(keyword, category_map)
        logger.info(f"  ✓ 成功补充 {updated} 个 ASIN 的分类数据")

        # 重新计算覆盖率
        new_coverage = self.db.get_category_coverage(keyword)
        new_rate = new_coverage['coverage_rate']
        logger.info(f"  补充后覆盖率: {new_coverage['has_category']}/{new_coverage['total']} ({new_rate*100:.1f}%)")

        return {
            'success': True,
            'needed': True,
            'coverage_before': coverage_rate,
            'coverage_after': new_rate,
            'filled_count': updated
        }

    def _fetch_category_via_hook(self, asins: List[str]) -> Dict[str, Dict]:
        """
        使用卖家精灵 Hook 批量获取分类数据

        Args:
            asins: ASIN 列表

        Returns:
            ASIN -> 分类信息的映射
        """
        if not SELLERSPIRIT_HOOK_AVAILABLE or not asins:
            return {}

        try:
            token = sellerspirit_hook.login()
            if not token:
                logger.error(f"  ✗ 卖家精灵 Hook 登录失败")
                return {}

            sellerspirit_hook.token = token
            category_map = {}
            chunks = chunk_list(asins, 40)
            total_chunks = (len(asins) + 39) // 40

            for i, chunk in enumerate(chunks):
                if i % 20 == 0:  # 每 20 批输出一次进度
                    logger.info(f"  处理进度: {i+1}/{total_chunks} 批...")

                asins_str = ",".join(chunk)
                data = sellerspirit_hook.getData(asins_str)

                if data:
                    for item in data:
                        asin = item.get('asin')
                        if asin:
                            node_label_path = item.get('node_label_path') or ''
                            parts = node_label_path.split(':') if node_label_path else []

                            category_main = parts[0] if len(parts) > 0 else ''
                            category_sub = parts[-1] if len(parts) > 1 else category_main
                            category_path = ' > '.join(parts) if parts else ''

                            # 如果没有 node_label_path，尝试从 bsrList 获取
                            if not category_sub:
                                bsr_list = item.get('bsrList') or []
                                if bsr_list:
                                    category_main = bsr_list[0].get('label', '') if len(bsr_list) > 0 else ''
                                    category_sub = bsr_list[-1].get('label', '') if len(bsr_list) > 1 else category_main

                            if category_sub:
                                category_map[asin] = {
                                    'category_path': category_path,
                                    'category_main': category_main,
                                    'category_sub': category_sub
                                }

                if i < total_chunks - 1:
                    time.sleep(2)

            logger.info(f"  Hook 获取完成: {len(category_map)} 个 ASIN 有分类数据")
            return category_map

        except Exception as e:
            logger.error(f"  ✗ 卖家精灵 Hook 失败: {e}")
            return {}

    def filter_by_category(self, keyword: str, min_coverage: float = 0.9) -> Dict[str, Any]:
        """
        步骤6：按分类筛选，只保留数量最多的分类的产品

        在筛选前会检查分类数据覆盖率，不足时自动补充

        Args:
            keyword: 搜索关键词
            min_coverage: 最低分类覆盖率阈值（默认 0.9 即 90%）

        Returns:
            筛选结果字典
        """
        logger.info(f"{'='*60}")
        logger.info(f"[步骤6] 分类筛选 - 只保留数量最多的分类")
        logger.info(f"{'='*60}")

        # 检查并补充分类数据
        fill_result = self.fill_missing_categories(keyword, min_coverage)

        # 获取筛选前的分类分布
        distribution = self.db.get_category_distribution(keyword)
        if distribution:
            logger.info(f"  筛选前分类分布（前10）:")
            for i, cat in enumerate(distribution[:10], 1):
                logger.info(f"    {i}. {cat['category']}: {cat['count']} 个")

        # 执行筛选
        result = self.db.filter_by_top_category(keyword)

        if result['top_category']:
            logger.info(f"  ✓ 筛选完成:")
            logger.info(f"    - 保留分类: {result['top_category']}")
            logger.info(f"    - 保留 ASIN: {result['kept']} 个")
            logger.info(f"    - 删除 ASIN: {result['removed']} 个")
            if result.get('avg_price') is not None:
                logger.info(f"    - 平均价格: ${result['avg_price']}")
            if result.get('median_price') is not None:
                logger.info(f"    - 价格中位数: ${result['median_price']}")
        else:
            logger.info(f"  ✓ 无分类数据，跳过筛选")

        return {
            'success': True,
            'total_before': result['total'],
            'top_category': result['top_category'],
            'removed': result['removed'],
            'kept': result['kept'],
            'avg_price': result.get('avg_price'),
            'median_price': result.get('median_price'),
            'distribution_before': distribution[:10] if distribution else [],
            'category_fill': fill_result
        }

    def filter_by_sales(
        self,
        keyword: str,
        max_sales: int = 100
    ) -> Dict[str, Any]:
        """
        步骤7：按销量筛选 ASIN，保留销量小于等于阈值的记录

        Args:
            keyword: 搜索关键词
            max_sales: 销量阈值，保留小于等于此值的 ASIN（默认 100）

        Returns:
            筛选结果字典
        """
        logger.info(f"{'='*60}")
        logger.info(f"[步骤7] 销量筛选 - 剔除销量 > {max_sales} 的 ASIN")
        logger.info(f"{'='*60}")

        # 获取筛选前的销量分布
        distribution = self.db.get_sales_distribution(keyword, max_sales)
        logger.info(f"  筛选前销量分布:")
        logger.info(f"    - 无销量数据: {distribution['no_data']} 个")
        logger.info(f"    - 销量 <= {max_sales}: {distribution['under_threshold']} 个")
        logger.info(f"    - 销量 > {max_sales}: {distribution['over_threshold']} 个")
        logger.info(f"    - 总计: {distribution['total']} 个")

        # 执行筛选
        result = self.db.filter_low_sales_asins(keyword, max_sales)

        logger.info(f"  ✓ 筛选完成:")
        logger.info(f"    - 删除高销量 ASIN: {result['removed']} 个")
        logger.info(f"    - 保留低销量 ASIN: {result['kept']} 个")

        return {
            'success': True,
            'total_before': result['total'],
            'removed': result['removed'],
            'kept': result['kept'],
            'distribution_before': distribution
        }

    def filter_by_price(
        self,
        keyword: str,
        avg_price: float = None,
        median_price: float = None
    ) -> Dict[str, Any]:
        """
        步骤8：按价格筛选 ASIN，保留价格小于平均价格和中位数中较小值的记录

        Args:
            keyword: 搜索关键词
            avg_price: 平均价格（来自步骤6）
            median_price: 价格中位数（来自步骤6）

        Returns:
            筛选结果字典
        """
        # 确定价格阈值：取平均价格和中位数中较小的值
        if avg_price is None and median_price is None:
            logger.info(f"{'='*60}")
            logger.info(f"[步骤8] 价格筛选 - 跳过（无价格数据）")
            logger.info(f"{'='*60}")
            return {
                'success': True,
                'skipped': True,
                'reason': '无价格数据',
                'total_before': 0,
                'removed': 0,
                'kept': 0
            }

        # 取较小值作为阈值
        if avg_price is not None and median_price is not None:
            max_price = min(avg_price, median_price)
            price_source = f"min(平均价${avg_price}, 中位数${median_price})"
        elif avg_price is not None:
            max_price = avg_price
            price_source = f"平均价${avg_price}"
        else:
            max_price = median_price
            price_source = f"中位数${median_price}"

        logger.info(f"{'='*60}")
        logger.info(f"[步骤8] 价格筛选 - 剔除价格 > ${max_price} 的 ASIN")
        logger.info(f"  价格阈值来源: {price_source}")
        logger.info(f"{'='*60}")

        # 获取筛选前的价格分布
        distribution = self.db.get_price_distribution(keyword, max_price)
        logger.info(f"  筛选前价格分布:")
        logger.info(f"    - 无价格数据: {distribution['no_data']} 个")
        logger.info(f"    - 价格 <= ${max_price}: {distribution['under_threshold']} 个")
        logger.info(f"    - 价格 > ${max_price}: {distribution['over_threshold']} 个")
        logger.info(f"    - 总计: {distribution['total']} 个")

        # 执行筛选
        result = self.db.filter_by_price(keyword, max_price)

        logger.info(f"  ✓ 筛选完成:")
        logger.info(f"    - 删除高价 ASIN: {result['removed']} 个")
        logger.info(f"    - 保留低价 ASIN: {result['kept']} 个")

        return {
            'success': True,
            'skipped': False,
            'total_before': result['total'],
            'max_price': max_price,
            'avg_price': avg_price,
            'median_price': median_price,
            'removed': result['removed'],
            'kept': result['kept'],
            'distribution_before': distribution
        }

    def enrich_with_sellerspirit_history(self, keyword: str) -> Dict[str, Any]:
        """
        步骤8.5：使用卖家精灵数据补充历史信息，并使用 Apify 获取价格历史

        补充以下数据：
        - 最近3个月销量 (sales_3m)
        - 卖家精灵月销量 (ss_monthly_sales)
        - 历史最高价/最低价及对应时间（通过 Apify 获取）

        Args:
            keyword: 搜索关键词

        Returns:
            补充结果字典
        """
        logger.info(f"{'='*60}")
        logger.info(f"[步骤8.5] 数据补充 - 卖家精灵历史数据 + Apify 价格历史")
        logger.info(f"{'='*60}")

        # 获取需要补充数据的 ASIN 列表
        asins = self.db.get_asins_for_enrichment(keyword)
        if not asins:
            logger.info("  没有需要补充数据的 ASIN")
            return {
                'success': True,
                'enriched_count': 0,
                'total_asins': 0
            }

        logger.info(f"  需要补充 {len(asins)} 个 ASIN 的历史数据...")

        history_map = {}
        has_price_history = 0

        # 第一步：使用卖家精灵 Hook 获取销量数据
        if SELLERSPIRIT_HOOK_AVAILABLE:
            try:
                token = sellerspirit_hook.login()
                if token:
                    sellerspirit_hook.token = token
                    chunks = chunk_list(asins, 40)
                    total_chunks = len(chunks)

                    logger.info(f"  [卖家精灵] 获取销量数据...")
                    for i, chunk in enumerate(chunks):
                        if i % 10 == 0:
                            logger.info(f"    处理进度: {i+1}/{total_chunks} 批...")

                        asins_str = ",".join(chunk)
                        data = sellerspirit_hook.getData(asins_str)

                        if data:
                            for item in data:
                                asin = item.get('asin')
                                if not asin:
                                    continue

                                # 解析历史销量数据
                                trends = item.get('trends') or []
                                sales_stats = self._calculate_sales_stats(trends)

                                # 获取卖家精灵月销量
                                ss_monthly_sales = item.get('units')

                                # 获取上架日期（available 是时间戳，毫秒）
                                available_ts = item.get('available')
                                listing_date = None
                                if available_ts:
                                    try:
                                        listing_date = datetime.fromtimestamp(available_ts / 1000).strftime('%Y-%m-%d')
                                    except (ValueError, TypeError, OSError):
                                        pass

                                # 获取评论相关数据（用于填充 ScraperAPI 数据为空的情况）
                                ss_rating = item.get('rating')
                                ss_reviews = item.get('reviews')

                                history_map[asin] = {
                                    'sales_3m': sales_stats['sales_3m'],
                                    'ss_monthly_sales': ss_monthly_sales,
                                    'price_min': None,
                                    'price_max': None,
                                    'price_min_date': None,
                                    'price_max_date': None,
                                    'listing_date': listing_date,
                                    'avg_monthly_sales': sales_stats['avg_monthly_sales'],
                                    'sales_months_count': sales_stats['sales_months_count'],
                                    'ss_rating': ss_rating,
                                    'ss_reviews': ss_reviews
                                }

                        if i < total_chunks - 1:
                            time.sleep(2)

                    logger.info(f"  [卖家精灵] 获取完成: {len(history_map)} 个 ASIN")
                else:
                    logger.warning("  [卖家精灵] 登录失败")
            except Exception as e:
                logger.error(f"  [卖家精灵] 获取失败: {e}")
        else:
            logger.warning("  [卖家精灵] Hook 不可用")
            # 初始化空的 history_map
            for asin in asins:
                history_map[asin] = {
                    'sales_3m': None,
                    'ss_monthly_sales': None,
                    'price_min': None,
                    'price_max': None,
                    'price_min_date': None,
                    'price_max_date': None,
                    'listing_date': None,
                    'avg_monthly_sales': None,
                    'sales_months_count': None,
                    'ss_rating': None,
                    'ss_reviews': None
                }

        # 第二步：使用 Apify 获取价格历史
        if is_apify_available():
            try:
                logger.info(f"  [Apify] 获取价格历史数据...")
                apify_fetcher = ApifyPriceFetcher()

                # 批量获取价格历史（Apify 支持批量）
                price_history_map = apify_fetcher.get_multiple_price_history(asins, country='US')

                # 合并价格历史到 history_map
                for asin, price_data in price_history_map.items():
                    if asin in history_map:
                        history_map[asin]['price_min'] = price_data.get('price_min')
                        history_map[asin]['price_max'] = price_data.get('price_max')
                        history_map[asin]['price_min_date'] = price_data.get('price_min_date')
                        history_map[asin]['price_max_date'] = price_data.get('price_max_date')
                        if price_data.get('price_min') is not None:
                            has_price_history += 1
                    else:
                        history_map[asin] = {
                            'sales_3m': None,
                            'ss_monthly_sales': None,
                            'price_min': price_data.get('price_min'),
                            'price_max': price_data.get('price_max'),
                            'price_min_date': price_data.get('price_min_date'),
                            'price_max_date': price_data.get('price_max_date'),
                            'listing_date': None,
                            'avg_monthly_sales': None,
                            'sales_months_count': None,
                            'ss_rating': None,
                            'ss_reviews': None
                        }
                        if price_data.get('price_min') is not None:
                            has_price_history += 1

                logger.info(f"  [Apify] 获取完成: {has_price_history} 个 ASIN 有价格历史")

            except Exception as e:
                logger.error(f"  [Apify] 获取失败: {e}")
        else:
            logger.warning("  [Apify] 不可用（未配置 APIFY_API_TOKEN 或未安装 apify-client）")

        # 批量更新数据库
        updated = 0
        if history_map:
            updated = self.db.batch_update_sellerspirit_history(keyword, history_map)
            logger.info(f"  ✓ 数据补充完成: {updated} 个 ASIN")

            # 统计补充结果
            has_sales_3m = sum(1 for v in history_map.values() if v.get('sales_3m'))
            has_ss_sales = sum(1 for v in history_map.values() if v.get('ss_monthly_sales'))
            has_listing = sum(1 for v in history_map.values() if v.get('listing_date'))
            logger.info(f"    - 有3个月销量数据: {has_sales_3m} 个")
            logger.info(f"    - 有卖家精灵月销量: {has_ss_sales} 个")
            logger.info(f"    - 有上架日期: {has_listing} 个")
            logger.info(f"    - 有价格历史: {has_price_history} 个")
        else:
            logger.warning("  未能获取任何历史数据")

        return {
            'success': True,
            'enriched_count': updated,
            'total_asins': len(asins),
            'has_sales_3m': sum(1 for v in history_map.values() if v.get('sales_3m')) if history_map else 0,
            'has_ss_monthly_sales': sum(1 for v in history_map.values() if v.get('ss_monthly_sales')) if history_map else 0,
            'has_listing_date': sum(1 for v in history_map.values() if v.get('listing_date')) if history_map else 0,
            'has_price_history': has_price_history
        }

    def filter_by_listing_date(
        self,
        keyword: str,
        months: int = 6
    ) -> Dict[str, Any]:
        """
        步骤7.6：按上架日期和销量月份数筛选，只保留最近 N 个月内的新品

        筛选条件（满足任一条件即为老品，会被过滤）：
        1. 上架日期早于截止日期
        2. 有超过 N 个月的销量数据

        Args:
            keyword: 搜索关键词
            months: 保留最近多少个月的新品（默认 6 个月）

        Returns:
            筛选结果字典
        """
        logger.info(f"{'='*60}")
        logger.info(f"[步骤7.6] 新品筛选 - 只保留最近 {months} 个月内的产品")
        logger.info(f"{'='*60}")

        # 获取筛选前的分布
        distribution = self.db.get_listing_date_distribution(keyword, months)
        logger.info(f"  筛选前分布:")
        logger.info(f"  [上架日期]")
        logger.info(f"    - 无数据: {distribution['no_date_data']} 个")
        logger.info(f"    - 新品 (>= {distribution['cutoff_date']}): {distribution['new_by_date']} 个")
        logger.info(f"    - 老品 (< {distribution['cutoff_date']}): {distribution['old_by_date']} 个")
        logger.info(f"  [销量月份数]")
        logger.info(f"    - 无数据: {distribution['no_sales_months_data']} 个")
        logger.info(f"    - 新品 (<= {months} 个月): {distribution['new_by_sales_months']} 个")
        logger.info(f"    - 老品 (> {months} 个月): {distribution['old_by_sales_months']} 个")
        logger.info(f"  总计: {distribution['total']} 个")

        # 执行筛选
        result = self.db.filter_by_listing_date(keyword, months)

        logger.info(f"  ✓ 筛选完成:")
        logger.info(f"    - 因上架日期过滤: {result['removed_by_date']} 个")
        logger.info(f"    - 因销量月份数过滤: {result['removed_by_sales_months']} 个")
        logger.info(f"    - 总删除: {result['removed']} 个")
        logger.info(f"    - 保留: {result['kept']} 个")

        return {
            'success': True,
            'total_before': result['total'],
            'cutoff_date': result['cutoff_date'],
            'months': months,
            'removed': result['removed'],
            'removed_by_date': result['removed_by_date'],
            'removed_by_sales_months': result['removed_by_sales_months'],
            'kept': result['kept'],
            'distribution_before': distribution
        }

    def _calculate_sales_3m(self, trends: List[Dict]) -> Optional[int]:
        """
        计算最近3个月的销量总和

        Args:
            trends: 销量趋势数据列表，格式: [{"dk": "202501", "sales": 100}, ...]

        Returns:
            最近3个月销量总和，如果数据不足返回 None
        """
        if not trends:
            return None

        # 按日期排序（降序，最新的在前）
        sorted_trends = sorted(trends, key=lambda x: x.get('dk', ''), reverse=True)

        # 取最近3个月
        recent_3m = sorted_trends[:3]
        if len(recent_3m) < 1:
            return None

        total_sales = sum(item.get('sales', 0) for item in recent_3m)
        return total_sales if total_sales > 0 else None

    def _calculate_sales_stats(self, trends: List[Dict]) -> Dict[str, Optional[int]]:
        """
        计算销量统计数据

        Args:
            trends: 销量趋势数据列表，格式: [{"dk": "202501", "sales": 100}, ...]

        Returns:
            包含以下字段的字典：
            - sales_3m: 最近3个月销量总和
            - avg_monthly_sales: 平均月销量
            - sales_months_count: 有销量数据的月份数
        """
        if not trends:
            return {
                'sales_3m': None,
                'avg_monthly_sales': None,
                'sales_months_count': None
            }

        # 按日期排序（降序，最新的在前）
        sorted_trends = sorted(trends, key=lambda x: x.get('dk', ''), reverse=True)

        # 计算有销量数据的月份数（销量 > 0 的月份）
        valid_months = [t for t in sorted_trends if t.get('sales', 0) > 0]
        sales_months_count = len(valid_months)

        # 计算最近3个月销量
        recent_3m = sorted_trends[:3]
        sales_3m = sum(item.get('sales', 0) for item in recent_3m) if recent_3m else None
        if sales_3m == 0:
            sales_3m = None

        # 计算平均月销量（基于有销量的月份）
        avg_monthly_sales = None
        if valid_months:
            total_sales = sum(t.get('sales', 0) for t in valid_months)
            avg_monthly_sales = int(total_sales / len(valid_months))

        return {
            'sales_3m': sales_3m,
            'avg_monthly_sales': avg_monthly_sales,
            'sales_months_count': sales_months_count if sales_months_count > 0 else None
        }

    def export_to_csv(self, keyword: str, output_dir: str = "outputs") -> Dict[str, Any]:
        """
        将筛选后的结果导出为 CSV 文件

        Args:
            keyword: 搜索关键词
            output_dir: 输出目录

        Returns:
            导出结果字典
        """
        # 创建输出目录
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 获取筛选后的数据，按价格排序
        data = self.db.get_filtered_asins(keyword, order_by='price')

        if not data:
            logger.warning(f"  没有数据可导出")
            return {'success': False, 'error': '没有数据可导出', 'count': 0}

        # 生成文件名：关键词_时间.csv
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_keyword = keyword.replace(' ', '_').replace('/', '_').replace('\\', '_')
        filename = f"{safe_keyword}_{timestamp}.csv"
        filepath = output_path / filename

        # 写入 CSV（包含价格历史字段和销量统计）
        fieldnames = ['asin', 'name', 'brand', 'price', 'rating', 'reviews_count',
                      'sales_volume', 'ss_monthly_sales', 'avg_monthly_sales', 'sales_3m',
                      'listing_date', 'sales_months_count',
                      'price_min', 'price_max', 'price_min_date', 'price_max_date',
                      'category_sub', 'category_main', 'url']

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(data)

        logger.info(f"  ✓ 导出完成: {filepath}")
        logger.info(f"    - 导出数量: {len(data)} 条")

        return {
            'success': True,
            'filepath': str(filepath),
            'count': len(data)
        }

    def run(
        self,
        keyword: str,
        country_code: str = 'us',
        max_pages: int = 100,
        sales_threshold: int = 10,
        top_categories: int = 3,
        max_pages_per_category: int = 50,
        ai_filter_limit: int = 100,
        enable_round3: bool = False,
        round3_top_asins: int = 300,
        round3_top_categories: int = 3,
        filter_max_sales: int = 100
    ) -> Dict[str, Any]:
        """
        执行完整的批量抓取流程

        Args:
            keyword: 搜索关键词
            country_code: 国家代码
            max_pages: 最大页数
            sales_threshold: 销量阈值
            top_categories: 热门分类数量
            max_pages_per_category: 每个分类最大页数
            ai_filter_limit: AI 筛选后每个分类保留的最大数量
            enable_round3: 是否启用第3轮抓取（步骤4）
            round3_top_asins: 第3轮抓取分析的ASIN数量
            round3_top_categories: 第3轮抓取的分类数量
            filter_max_sales: 销量筛选阈值，保留销量小于此值的 ASIN（默认 100）

        Returns:
            抓取结果字典
        """
        logger.info(f"{'#'*60}")
        logger.info(f"# 大批量 ASIN 抓取器")
        logger.info(f"# 关键词: {keyword}")
        if self.use_ai_filter:
            logger.info(f"# AI 筛选: 已启用 (筛选与关键词相关的分类)")
        if enable_round3:
            logger.info(f"# 第3轮抓取: 已启用 (前{round3_top_asins}个ASIN, 前{round3_top_categories}个分类)")
        logger.info(f"# 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'#'*60}")

        start_time = datetime.now()
        step_stats = []  # 记录每个步骤的统计信息

        # 步骤1: 抓取关键词
        step1_start = time.time()
        step1_result = self.scrape_keyword(
            keyword=keyword,
            country_code=country_code,
            max_pages=max_pages,
            sales_threshold=sales_threshold
        )
        step1_duration = time.time() - step1_start

        if not step1_result.get('success'):
            return step1_result

        search_results = step1_result.get('search_results', [])
        step_stats.append({
            'step': '步骤1',
            'name': '关键词搜索',
            'data_count': step1_result.get('saved_count', len(search_results)),
            'pages': step1_result.get('pages_scraped', 0),
            'duration': step1_duration,
            'from_cache': step1_result.get('from_cache', False)
        })

        # 步骤1.5: 获取卖家精灵分类数据
        step1_5_start = time.time()
        ss_result = self.fetch_sellerspirit_categories(keyword, search_results)
        step1_5_duration = time.time() - step1_5_start
        use_sellerspirit = ss_result.get('use_sellerspirit', False)

        step_stats.append({
            'step': '步骤1.5',
            'name': '获取分类数据',
            'data_count': ss_result.get('updated_count', 0),
            'pages': 0,
            'duration': step1_5_duration,
            'from_cache': False
        })

        # 步骤2: 分析类目（包含 AI 筛选分类）
        step2_start = time.time()
        category_stats = self.analyze_categories(
            keyword, search_results, use_sellerspirit, ai_filter_limit
        )
        step2_duration = time.time() - step2_start

        step_stats.append({
            'step': '步骤2',
            'name': '分析类目分布',
            'data_count': len(category_stats),
            'pages': 0,
            'duration': step2_duration,
            'from_cache': False
        })

        # 步骤3: 抓取热门类目
        step3_start = time.time()
        if category_stats and top_categories > 0:
            step3_result = self.scrape_top_categories(
                keyword=keyword,
                category_stats=category_stats,
                top_n=top_categories,
                country_code=country_code,
                max_pages_per_category=max_pages_per_category,
                sales_threshold=sales_threshold
            )
        else:
            step3_result = {'success': True, 'categories_scraped': 0, 'new_asins': 0}
        step3_duration = time.time() - step3_start

        step_stats.append({
            'step': '步骤3',
            'name': '扩展热门类目',
            'data_count': step3_result.get('new_asins', 0),
            'categories': step3_result.get('categories_scraped', 0),
            'pages': 0,
            'duration': step3_duration,
            'from_cache': False
        })

        # 步骤4: 第3轮抓取（可选）
        step4_result = {'success': True, 'categories_scraped': 0, 'new_asins': 0}
        step4_duration = 0
        if enable_round3 and search_results:
            step4_start = time.time()
            step4_result = self.scrape_round3(
                keyword=keyword,
                search_results=search_results,
                top_n_asins=round3_top_asins,
                top_n_categories=round3_top_categories,
                country_code=country_code,
                max_pages_per_category=max_pages_per_category,
                sales_threshold=sales_threshold
            )
            step4_duration = time.time() - step4_start

        step_stats.append({
            'step': '步骤4',
            'name': '深度分类扩展',
            'data_count': step4_result.get('new_asins', 0),
            'categories': step4_result.get('categories_scraped', 0),
            'pages': 0,
            'duration': step4_duration,
            'from_cache': False,
            'skipped': not enable_round3
        })

        # 重置筛选状态（确保重复运行时所有 ASIN 都参与筛选）
        reset_count = self.db.reset_filter_status(keyword)
        if reset_count > 0:
            logger.info(f"已重置 {reset_count} 条记录的筛选状态")

        # 步骤5: 广告筛选（剔除广告 ASIN）
        step5_start = time.time()
        step5_result = self.filter_by_sponsored(keyword)
        step5_duration = time.time() - step5_start

        step_stats.append({
            'step': '步骤5',
            'name': '广告筛选',
            'data_count': step5_result.get('kept', 0),
            'removed': step5_result.get('removed', 0),
            'pages': 0,
            'duration': step5_duration,
            'from_cache': False
        })

        # 步骤6: 分类筛选（只保留数量最多的分类）
        step6_start = time.time()
        step6_result = self.filter_by_category(keyword)
        step6_duration = time.time() - step6_start

        step_stats.append({
            'step': '步骤6',
            'name': '分类筛选',
            'data_count': step6_result.get('kept', 0),
            'removed': step6_result.get('removed', 0),
            'top_category': step6_result.get('top_category'),
            'pages': 0,
            'duration': step6_duration,
            'from_cache': False
        })

        # 步骤7: 销量筛选（剔除销量 > filter_max_sales 的 ASIN）
        step7_start = time.time()
        step7_result = self.filter_by_sales(keyword, filter_max_sales)
        step7_duration = time.time() - step7_start

        step_stats.append({
            'step': '步骤7',
            'name': '销量筛选',
            'data_count': step7_result.get('kept', 0),
            'removed': step7_result.get('removed', 0),
            'pages': 0,
            'duration': step7_duration,
            'from_cache': False
        })

        # 步骤7.5: 数据补充（卖家精灵历史数据，包含上架日期）
        step7_5_start = time.time()
        step7_5_result = self.enrich_with_sellerspirit_history(keyword)
        step7_5_duration = time.time() - step7_5_start

        step_stats.append({
            'step': '步骤7.5',
            'name': '数据补充',
            'data_count': step7_5_result.get('enriched_count', 0),
            'removed': 0,
            'pages': 0,
            'duration': step7_5_duration,
            'from_cache': False,
            'skipped': not step7_5_result.get('success', False)
        })

        # 步骤7.6: 新品筛选（只保留最近6个月内上架的产品）
        step7_6_start = time.time()
        step7_6_result = self.filter_by_listing_date(keyword, months=6)
        step7_6_duration = time.time() - step7_6_start

        step_stats.append({
            'step': '步骤7.6',
            'name': '新品筛选',
            'data_count': step7_6_result.get('kept', 0),
            'removed': step7_6_result.get('removed', 0),
            'pages': 0,
            'duration': step7_6_duration,
            'from_cache': False
        })

        # 步骤8: 价格筛选（剔除价格高于平均价/中位数的 ASIN）
        step8_start = time.time()
        step8_result = self.filter_by_price(
            keyword,
            avg_price=step6_result.get('avg_price'),
            median_price=step6_result.get('median_price')
        )
        step8_duration = time.time() - step8_start

        step_stats.append({
            'step': '步骤8',
            'name': '价格筛选',
            'data_count': step8_result.get('kept', 0),
            'removed': step8_result.get('removed', 0),
            'pages': 0,
            'duration': step8_duration,
            'from_cache': False,
            'skipped': step8_result.get('skipped', False)
        })

        # 步骤9: 导出 CSV（按价格排序）
        step9_start = time.time()
        logger.info(f"{'='*60}")
        logger.info(f"[步骤9] 导出结果到 CSV")
        logger.info(f"{'='*60}")
        export_result = self.export_to_csv(keyword)
        step9_duration = time.time() - step9_start

        step_stats.append({
            'step': '步骤9',
            'name': '导出CSV',
            'data_count': export_result.get('count', 0),
            'removed': 0,
            'pages': 0,
            'duration': step9_duration,
            'from_cache': False,
            'skipped': not export_result.get('success', False)
        })

        # 汇总结果
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        total_asins = self.db.get_asin_count(keyword)

        # 输出详细的步骤统计报告
        logger.info(f"")
        logger.info(f"{'='*60}")
        logger.info(f"[完成] 抓取汇总报告")
        logger.info(f"{'='*60}")
        logger.info(f"  关键词: {keyword}")
        logger.info(f"")
        logger.info(f"  ┌{'─'*56}┐")
        logger.info(f"  │ {'步骤':<10} {'名称':<16} {'数据量':>10} {'耗时':>14} │")
        logger.info(f"  ├{'─'*56}┤")

        for stat in step_stats:
            step_name = stat['step']
            name = stat['name']
            data_count = stat['data_count']
            step_duration = stat['duration']
            cache_mark = ' (缓存)' if stat.get('from_cache') else ''

            # 跳过的步骤
            if stat.get('skipped'):
                logger.info(f"  │ {step_name:<10} {name:<16} {'(跳过)':>10} {'-':>14} │")
                continue

            # 格式化耗时
            if step_duration >= 60:
                duration_str = f"{step_duration/60:.1f} 分钟"
            else:
                duration_str = f"{step_duration:.1f} 秒"

            # 数据量描述
            if stat.get('categories'):
                data_str = f"{data_count} ASIN"
            elif stat['step'] == '步骤2':
                data_str = f"{data_count} 分类"
            elif stat['step'] in ('步骤5', '步骤6', '步骤7', '步骤7.6', '步骤8'):
                removed = stat.get('removed', 0)
                data_str = f"保留{data_count}(-{removed})"
            elif stat['step'] == '步骤7.5':
                data_str = f"{data_count} 条"
            elif stat['step'] == '步骤9':
                data_str = f"{data_count} 条"
            else:
                data_str = f"{data_count} ASIN"

            logger.info(f"  │ {step_name:<10} {name:<16} {data_str:>10}{cache_mark} {duration_str:>10} │")

        logger.info(f"  └{'─'*56}┘")
        logger.info(f"")
        logger.info(f"  ────────────────────────────────────────────────────────")
        logger.info(f"  总 ASIN 数: {total_asins}")
        logger.info(f"  总耗时: {self._format_duration(duration)}")
        logger.info(f"  数据库: {self.db.db_path}")
        logger.info(f"  ────────────────────────────────────────────────────────")

        result = {
            'success': True,
            'keyword': keyword,
            'total_asins': total_asins,
            'categories_count': len(category_stats),
            'top_categories': [s['category'] for s in category_stats[:top_categories]],
            'duration_seconds': duration,
            'duration_formatted': self._format_duration(duration),
            'database_path': str(self.db.db_path),
            'step_stats': [
                {
                    'step': s['step'],
                    'name': s['name'],
                    'data_count': s['data_count'],
                    'duration_seconds': round(s['duration'], 2),
                    'duration_formatted': self._format_duration(s['duration']),
                    'from_cache': s.get('from_cache', False)
                }
                for s in step_stats
            ]
        }

        if enable_round3:
            result['round3'] = {
                'enabled': True,
                'categories_scraped': step4_result.get('categories_scraped', 0),
                'new_asins': step4_result.get('new_asins', 0),
                'category_distribution': step4_result.get('category_distribution', [])
            }

        # 添加广告筛选结果
        result['sponsored_filter'] = {
            'total_before': step5_result.get('total_before', 0),
            'sponsored_count': step5_result.get('sponsored_count', 0),
            'removed': step5_result.get('removed', 0),
            'kept': step5_result.get('kept', 0)
        }

        # 添加分类筛选结果
        result['category_filter'] = {
            'top_category': step6_result.get('top_category'),
            'total_before': step6_result.get('total_before', 0),
            'removed': step6_result.get('removed', 0),
            'kept': step6_result.get('kept', 0),
            'avg_price': step6_result.get('avg_price'),
            'median_price': step6_result.get('median_price')
        }

        # 添加销量筛选结果
        result['sales_filter'] = {
            'max_sales': filter_max_sales,
            'total_before': step7_result.get('total_before', 0),
            'removed': step7_result.get('removed', 0),
            'kept': step7_result.get('kept', 0)
        }

        # 添加数据补充结果
        result['data_enrichment'] = {
            'success': step7_5_result.get('success', False),
            'enriched_count': step7_5_result.get('enriched_count', 0),
            'total_asins': step7_5_result.get('total_asins', 0),
            'has_sales_3m': step7_5_result.get('has_sales_3m', 0),
            'has_ss_monthly_sales': step7_5_result.get('has_ss_monthly_sales', 0),
            'has_listing_date': step7_5_result.get('has_listing_date', 0),
            'has_price_history': step7_5_result.get('has_price_history', 0)
        }

        # 添加新品筛选结果
        result['listing_date_filter'] = {
            'months': step7_6_result.get('months', 6),
            'cutoff_date': step7_6_result.get('cutoff_date'),
            'total_before': step7_6_result.get('total_before', 0),
            'removed': step7_6_result.get('removed', 0),
            'removed_by_date': step7_6_result.get('removed_by_date', 0),
            'removed_by_sales_months': step7_6_result.get('removed_by_sales_months', 0),
            'kept': step7_6_result.get('kept', 0)
        }

        # 添加价格筛选结果
        result['price_filter'] = {
            'max_price': step8_result.get('max_price'),
            'avg_price': step8_result.get('avg_price'),
            'median_price': step8_result.get('median_price'),
            'total_before': step8_result.get('total_before', 0),
            'removed': step8_result.get('removed', 0),
            'kept': step8_result.get('kept', 0),
            'skipped': step8_result.get('skipped', False)
        }

        # 添加导出结果
        result['export'] = {
            'success': export_result.get('success', False),
            'filepath': export_result.get('filepath'),
            'count': export_result.get('count', 0)
        }

        return result
