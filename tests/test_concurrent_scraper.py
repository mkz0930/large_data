"""
测试 ScraperAPI 并发抓取优化
"""
import sys
import os
from pathlib import Path

# 添加路径
DATA_SUMMARY_PATH = Path(__file__).parent.parent.parent / "data_summary"
sys.path.insert(0, str(DATA_SUMMARY_PATH))
sys.path.insert(0, str(DATA_SUMMARY_PATH / "external_apis"))

from dotenv import load_dotenv

# 加载环境变量
env_path = DATA_SUMMARY_PATH / ".env"
load_dotenv(env_path)

from amazon_scraper import AmazonScraper

def test_concurrent_scraper():
    """测试并发抓取功能"""
    api_key = os.environ.get('SCRAPERAPI_KEY')
    if not api_key:
        print("错误: 未找到 SCRAPERAPI_KEY 环境变量")
        return

    print("=" * 60)
    print("测试 ScraperAPI 并发抓取优化")
    print("=" * 60)

    # 初始化抓取器
    scraper = AmazonScraper(
        api_key=api_key,
        max_concurrent=5,  # 并发数
        max_retries=3,
        request_timeout=60
    )

    # 测试关键词
    keyword = "camping lantern"
    max_pages = 5  # 测试抓取 5 页

    print(f"\n关键词: {keyword}")
    print(f"最大页数: {max_pages}")
    print(f"并发数: {scraper.max_concurrent}")
    print("-" * 60)

    # 执行抓取
    import time
    start_time = time.time()

    result = scraper.search_keyword_with_smart_stop(
        keyword=keyword,
        max_pages=max_pages,
        sales_threshold=10,
        use_concurrent=True,  # 启用并发
        show_progress=True
    )

    duration = time.time() - start_time

    # 输出结果
    print("\n" + "=" * 60)
    print("抓取结果")
    print("=" * 60)
    print(f"总耗时: {duration:.2f} 秒")
    print(f"抓取页数: {result.get('pages_scraped', 0)}")
    print(f"检测总页数: {result.get('detected_total_pages', 'N/A')}")
    print(f"ASIN 数量: {result.get('total_asins', 0)}")
    print(f"停止原因: {result.get('stopped_reason', 'N/A')}")

    # 显示部分结果
    search_results = result.get('search_results', [])
    if search_results:
        print(f"\n前 5 个产品:")
        for i, item in enumerate(search_results[:5], 1):
            print(f"  {i}. [{item.get('page', '?')}页] {item.get('asin')} - {item.get('name', '')[:50]}...")

    return result


if __name__ == "__main__":
    test_concurrent_scraper()
