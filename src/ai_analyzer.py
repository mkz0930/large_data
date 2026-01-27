"""
AI 产品分析模块
使用 Gemini API 快速并行验证产品与关键词的相关性
"""

import os
import json
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# 尝试导入 Google Gemini
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


@dataclass
class ProductValidation:
    """产品验证结果"""
    asin: str
    is_relevant: bool
    reason: str
    suggested_category: Optional[str] = None
    validated_at: datetime = None

    def __post_init__(self):
        if self.validated_at is None:
            self.validated_at = datetime.now()


class GeminiProductAnalyzer:
    """Gemini AI 产品分析器"""

    def __init__(
        self,
        api_key: str = None,
        model: str = "gemini-2.0-flash",
        max_concurrent: int = 50,
        rate_limit_delay: float = 0.01
    ):
        """
        初始化分析器

        Args:
            api_key: Google API 密钥（默认从环境变量读取）
            model: 模型名称
            max_concurrent: 最大并发数
            rate_limit_delay: API 调用间隔（秒）
        """
        if not GEMINI_AVAILABLE:
            raise ImportError("请安装 google-genai: pip install google-genai")

        self.api_key = api_key or os.environ.get('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("请设置 GEMINI_API_KEY 环境变量")

        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model
        self.max_concurrent = max_concurrent
        self.rate_limit_delay = rate_limit_delay

        # 动态并发控制
        self._current_concurrent = 5
        self._consecutive_successes = 0
        self._success_threshold = 3
        self._concurrency_lock = None

    async def _adjust_concurrency(self, success: bool, error_msg: str = ""):
        """动态调整并发数"""
        if self._concurrency_lock is None:
            self._concurrency_lock = asyncio.Lock()

        async with self._concurrency_lock:
            if success:
                self._consecutive_successes += 1
                if self._consecutive_successes >= self._success_threshold:
                    old = self._current_concurrent
                    self._current_concurrent = min(self._current_concurrent + 2, self.max_concurrent)
                    if self._current_concurrent > old:
                        print(f"  [AI] 并发数增加: {old} -> {self._current_concurrent}")
                    self._consecutive_successes = 0
            else:
                is_server_error = any(err in error_msg for err in ['503', '504', 'RESOURCE_EXHAUSTED', 'timeout'])
                if is_server_error:
                    self._consecutive_successes = 0
                    old = self._current_concurrent
                    self._current_concurrent = max(1, self._current_concurrent // 2)
                    if self._current_concurrent < old:
                        print(f"  [AI] 并发数降低: {old} -> {self._current_concurrent}")

    def _build_prompt(self, product: Dict, keyword: str) -> str:
        """构建验证提示词"""
        return f"""你是产品分类专家。判断以下产品是否与搜索关键词"{keyword}"相关。

产品信息：
- ASIN: {product.get('asin', 'N/A')}
- 标题: {product.get('name', 'N/A')}
- 品牌: {product.get('brand', '未知')}
- 分类: {product.get('category_sub') or product.get('category', '未知')}
- 价格: ${product.get('price', 'N/A')}

判断标准：
- 只判断产品本身是否与关键词"{keyword}"相关
- 只要产品标题、功能、用途与关键词相关，就返回 true

返回JSON格式：
{{"is_relevant": true/false, "reason": "简要理由(30字内)"}}

只返回JSON，不要其他内容。"""

    def _parse_response(self, response_text: str, asin: str) -> Optional[ProductValidation]:
        """解析 API 响应"""
        import re

        try:
            text = response_text.strip()

            # 提取 JSON
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
            if json_match:
                text = json_match.group(1).strip()

            data = json.loads(text)

            is_relevant = data.get('is_relevant')
            if isinstance(is_relevant, str):
                is_relevant = is_relevant.lower() in ['true', 'yes', '1']

            reason = data.get('reason', '')

            return ProductValidation(
                asin=asin,
                is_relevant=bool(is_relevant),
                reason=str(reason)[:100]
            )

        except Exception as e:
            print(f"  [AI] 解析失败 {asin}: {e}")
            return None

    async def validate_product_async(self, product: Dict, keyword: str, max_retries: int = 3) -> Optional[ProductValidation]:
        """异步验证单个产品"""
        prompt = self._build_prompt(product, keyword)
        asin = product.get('asin', 'unknown')

        for attempt in range(max_retries):
            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.client.models.generate_content(
                        model=self.model_name,
                        contents=prompt
                    )
                )

                result = self._parse_response(response.text, asin)
                if result:
                    await self._adjust_concurrency(success=True)
                    if self.rate_limit_delay > 0:
                        await asyncio.sleep(self.rate_limit_delay)
                    return result

                # 解析失败，重试
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5)

            except Exception as e:
                error_msg = str(e)
                await self._adjust_concurrency(success=False, error_msg=error_msg)
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)

        return None

    async def filter_products_async(
        self,
        products: List[Dict],
        keyword: str,
        max_results: int = 100
    ) -> List[Dict]:
        """
        异步批量筛选相关产品

        Args:
            products: 产品列表
            keyword: 搜索关键词
            max_results: 最大返回数量

        Returns:
            筛选后的相关产品列表
        """
        # 重置并发控制
        self._current_concurrent = 5
        self._consecutive_successes = 0
        self._concurrency_lock = asyncio.Lock()

        print(f"\n  [AI] 开始分析 {len(products)} 个产品 (最大并发: {self.max_concurrent})")

        results = []
        relevant_products = []
        pending_indices = list(range(len(products)))
        active_tasks = {}

        while pending_indices or active_tasks:
            # 如果已找到足够的相关产品，停止
            if len(relevant_products) >= max_results:
                # 取消剩余任务
                for task in active_tasks:
                    task.cancel()
                break

            # 启动新任务
            while pending_indices and len(active_tasks) < self._current_concurrent:
                idx = pending_indices.pop(0)
                product = products[idx]
                task = asyncio.create_task(self.validate_product_async(product, keyword))
                active_tasks[task] = idx

            if not active_tasks:
                break

            # 等待任务完成
            done, _ = await asyncio.wait(active_tasks.keys(), return_when=asyncio.FIRST_COMPLETED)

            for task in done:
                idx = active_tasks.pop(task)
                try:
                    result = task.result()
                    if result:
                        results.append((idx, result))
                        if result.is_relevant:
                            relevant_products.append(products[idx])
                            # 打印进度
                            if len(relevant_products) % 10 == 0:
                                print(f"  [AI] 已找到 {len(relevant_products)} 个相关产品...")
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(f"  [AI] 任务异常: {e}")

        # 统计
        total_validated = len(results)
        relevant_count = len(relevant_products)
        print(f"  [AI] 分析完成: 验证 {total_validated} 个, 相关 {relevant_count} 个")

        return relevant_products[:max_results]

    def filter_products(
        self,
        products: List[Dict],
        keyword: str,
        max_results: int = 100
    ) -> List[Dict]:
        """
        同步接口：筛选相关产品

        Args:
            products: 产品列表
            keyword: 搜索关键词
            max_results: 最大返回数量

        Returns:
            筛选后的相关产品列表
        """
        return asyncio.run(self.filter_products_async(products, keyword, max_results))


@dataclass
class CategoryValidation:
    """分类验证结果"""
    category: str
    is_relevant: bool
    reason: str
    validated_at: datetime = None

    def __post_init__(self):
        if self.validated_at is None:
            self.validated_at = datetime.now()


class GeminiCategoryAnalyzer:
    """Gemini AI 分类分析器 - 判断分类是否与关键词相关"""

    def __init__(
        self,
        api_key: str = None,
        model: str = "gemini-2.0-flash",
        max_concurrent: int = 20
    ):
        """
        初始化分析器

        Args:
            api_key: Google API 密钥（默认从环境变量读取）
            model: 模型名称
            max_concurrent: 最大并发数
        """
        if not GEMINI_AVAILABLE:
            raise ImportError("请安装 google-genai: pip install google-genai")

        self.api_key = api_key or os.environ.get('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("请设置 GEMINI_API_KEY 环境变量")

        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model
        self.max_concurrent = max_concurrent

    def _build_category_prompt(self, categories: List[str], keyword: str) -> str:
        """构建分类验证提示词"""
        categories_text = "\n".join([f"- {cat}" for cat in categories])
        return f"""你是电商产品分类专家。判断以下产品分类是否与搜索关键词"{keyword}"相关。

搜索关键词: {keyword}

产品分类列表:
{categories_text}

判断标准：
- 分类名称描述的产品类型是否与关键词"{keyword}"直接相关
- 例如：关键词"camping"与分类"Camping Tents"相关，与"Office Chairs"不相关
- 只要分类中的产品可能被搜索该关键词的用户购买，就认为相关

返回JSON格式（数组）：
[
  {{"category": "分类名称", "is_relevant": true/false, "reason": "简要理由(20字内)"}}
]

只返回JSON数组，不要其他内容。"""

    def _parse_categories_response(self, response_text: str, categories: List[str]) -> List[CategoryValidation]:
        """解析分类验证响应"""
        import re

        try:
            text = response_text.strip()

            # 提取 JSON
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
            if json_match:
                text = json_match.group(1).strip()

            data = json.loads(text)

            results = []
            for item in data:
                category = item.get('category', '')
                is_relevant = item.get('is_relevant')
                if isinstance(is_relevant, str):
                    is_relevant = is_relevant.lower() in ['true', 'yes', '1']
                reason = item.get('reason', '')

                results.append(CategoryValidation(
                    category=category,
                    is_relevant=bool(is_relevant),
                    reason=str(reason)[:50]
                ))

            return results

        except Exception as e:
            print(f"  [AI] 分类解析失败: {e}")
            return []

    def filter_categories(
        self,
        category_stats: List[Dict],
        keyword: str,
        max_categories: int = 10
    ) -> List[Dict]:
        """
        筛选与关键词相关的分类

        Args:
            category_stats: 分类统计列表，每项包含 'category' 字段
            keyword: 搜索关键词
            max_categories: 最大返回分类数量

        Returns:
            筛选后的相关分类列表
        """
        if not category_stats:
            return []

        # 过滤掉 Other 分类
        valid_stats = [s for s in category_stats if s.get('category') != 'Other']
        if not valid_stats:
            return []

        # 提取分类名称
        categories = [s['category'] for s in valid_stats[:30]]  # 最多分析30个分类

        print(f"\n  [AI] 开始分析 {len(categories)} 个分类与关键词 \"{keyword}\" 的相关性...")

        try:
            prompt = self._build_category_prompt(categories, keyword)
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )

            validations = self._parse_categories_response(response.text, categories)

            # 构建分类到验证结果的映射
            validation_map = {v.category: v for v in validations}

            # 筛选相关分类
            relevant_stats = []
            for stat in valid_stats:
                cat_name = stat['category']
                validation = validation_map.get(cat_name)
                if validation and validation.is_relevant:
                    relevant_stats.append(stat)
                    if len(relevant_stats) <= 10:
                        print(f"    ✓ {cat_name}: {validation.reason}")
                elif validation and not validation.is_relevant and len(relevant_stats) < 5:
                    print(f"    ✗ {cat_name}: {validation.reason}")

            print(f"  [AI] 分类筛选完成: {len(categories)} 个分类中 {len(relevant_stats)} 个相关")

            return relevant_stats[:max_categories]

        except Exception as e:
            print(f"  [AI] 分类筛选失败: {e}")
            # 失败时返回原始列表
            return valid_stats[:max_categories]


def filter_category_products(
    products: List[Dict],
    keyword: str,
    category: str,
    max_results: int = 100,
    api_key: str = None
) -> List[Dict]:
    """
    筛选某个分类下的相关产品

    Args:
        products: 产品列表
        keyword: 搜索关键词
        category: 分类名称
        max_results: 最大返回数量
        api_key: Gemini API 密钥

    Returns:
        筛选后的相关产品列表
    """
    if not GEMINI_AVAILABLE:
        print("  [AI] Gemini 不可用，跳过 AI 筛选")
        return products[:max_results]

    try:
        analyzer = GeminiProductAnalyzer(api_key=api_key)
        # 构建更精确的关键词
        search_keyword = f"{keyword} {category}"
        return analyzer.filter_products(products, search_keyword, max_results)
    except Exception as e:
        print(f"  [AI] 筛选失败: {e}")
        return products[:max_results]
