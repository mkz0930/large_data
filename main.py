"""
Amazon ASIN 批量抓取器 - 统一入口

使用方式:
    # 单关键词模式
    python main.py "camping"
    python main.py "hiking" --max-pages 50 --top-categories 5

    # 启用第3轮抓取（深度分类扩展）
    python main.py "camping" --round3
    python main.py "camping" --round3 --round3-asins 300 --round3-categories 3

    # 批量模式（从文件读取）
    python main.py --batch keywords.txt
    python main.py -b keywords.txt --max-pages 100

功能:
    1. 抓取关键词搜索结果
    2. 获取 ASIN 分类数据（卖家精灵）
    3. 扩展抓取热门分类的更多 ASIN
    4. 第3轮抓取：对前N个ASIN进行深度分类分析并扩展抓取（可选）
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple

# 添加 data_summary 路径（用于加载 .env）
DATA_SUMMARY_PATH = Path(__file__).parent.parent / "data_summary"

from dotenv import load_dotenv
load_dotenv(DATA_SUMMARY_PATH / ".env")

# 从 src 模块导入
from src import BatchScraper
from src.logger import setup_logger

# 初始化日志
logger = setup_logger("main")


def parse_args(args: List[str] = None) -> argparse.Namespace:
    """
    解析命令行参数

    Args:
        args: 命令行参数列表，None 时使用 sys.argv

    Returns:
        解析后的参数命名空间
    """
    parser = argparse.ArgumentParser(
        description='Amazon ASIN 批量抓取器 - 使用 ScraperAPI 抓取产品数据',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py "camping"                    # 抓取 camping 关键词
  python main.py "hiking" -p 50 -t 5          # 抓取 50 页，扩展 5 个分类
  python main.py "camping" --round3           # 启用第3轮深度分类抓取
  python main.py -b keywords.txt              # 批量抓取文件中的关键词
        """
    )

    # 位置参数：单个关键词（可选）
    parser.add_argument(
        'keyword',
        type=str,
        nargs='?',
        default=None,
        help='搜索关键词（单关键词模式）'
    )

    # 批量模式
    parser.add_argument(
        '--batch', '-b',
        type=str,
        default=None,
        metavar='FILE',
        help='批量模式：指定关键词文件路径（每行一个关键词）'
    )

    # 通用参数
    parser.add_argument(
        '--country', '-c',
        type=str,
        default='us',
        help='国家代码 (默认: us)'
    )
    parser.add_argument(
        '--max-pages', '-p',
        type=int,
        default=100,
        help='关键词搜索最大页数 (默认: 100)'
    )
    parser.add_argument(
        '--sales-threshold', '-s',
        type=int,
        default=10,
        help='销量阈值，低于此值停止抓取 (默认: 10)'
    )
    parser.add_argument(
        '--top-categories', '-t',
        type=int,
        default=100,
        help='扩展抓取前 N 个热门分类 (默认: 3)'
    )
    parser.add_argument(
        '--category-pages',
        type=int,
        default=100,
        help='每个分类最大页数 (默认: 50)'
    )
    parser.add_argument(
        '--db-path',
        type=str,
        default='data/batch_scraper.db',
        help='数据库路径 (默认: data/batch_scraper.db)'
    )
    parser.add_argument(
        '--no-sellerspirit',
        action='store_true',
        help='禁用卖家精灵分类数据，使用动态关键词提取'
    )

    # AI 筛选参数
    parser.add_argument(
        '--no-ai-filter',
        action='store_true',
        help='禁用 AI 分类筛选（默认启用）'
    )
    parser.add_argument(
        '--ai-limit',
        type=int,
        default=100,
        help='AI 筛选后保留的最大分类数量 (默认: 100)'
    )

    # 第3轮抓取参数
    parser.add_argument(
        '--round3',
        action='store_true',
        help='启用第3轮抓取：对前N个ASIN进行深度分类分析并扩展抓取'
    )
    parser.add_argument(
        '--round3-asins',
        type=int,
        default=300,
        help='第3轮抓取分析的ASIN数量 (默认: 300)'
    )
    parser.add_argument(
        '--round3-categories',
        type=int,
        default=100,
        help='第3轮抓取的分类数量 (默认: 100)'
    )

    # 销量筛选参数
    parser.add_argument(
        '--filter-max-sales',
        type=int,
        default=100,
        help='销量筛选阈值，保留销量小于此值的 ASIN (默认: 100)'
    )

    return parser.parse_args(args)


def validate_args(args: argparse.Namespace) -> Tuple[Optional[str], Optional[str]]:
    """
    验证参数并确定运行模式

    Args:
        args: 解析后的参数

    Returns:
        (mode, error): mode 为 'single'/'batch'/None，error 为错误信息
    """
    if args.batch:
        # 批量模式
        if not Path(args.batch).exists():
            return None, f"关键词文件不存在: {args.batch}"
        return 'batch', None
    elif args.keyword:
        # 单关键词模式
        return 'single', None
    else:
        # 无输入
        return None, "请指定关键词或使用 --batch 指定关键词文件"


def load_keywords_from_file(file_path: str) -> List[str]:
    """
    从文件加载关键词列表

    Args:
        file_path: 关键词文件路径

    Returns:
        关键词列表（过滤空行和注释）

    Raises:
        FileNotFoundError: 文件不存在
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    keywords = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            keyword = line.strip()
            # 跳过空行和注释
            if keyword and not keyword.startswith('#'):
                keywords.append(keyword)
    return keywords


def run_single_keyword(scraper: BatchScraper, keyword: str, args: argparse.Namespace) -> dict:
    """
    执行单关键词抓取

    Args:
        scraper: BatchScraper 实例
        keyword: 搜索关键词
        args: 命令行参数

    Returns:
        抓取结果字典
    """
    ai_filter_limit = getattr(args, 'ai_limit', 100)
    enable_round3 = getattr(args, 'round3', False)
    round3_top_asins = getattr(args, 'round3_asins', 300)
    round3_top_categories = getattr(args, 'round3_categories', 3)
    filter_max_sales = getattr(args, 'filter_max_sales', 100)

    return scraper.run(
        keyword=keyword,
        country_code=args.country,
        max_pages=args.max_pages,
        sales_threshold=args.sales_threshold,
        top_categories=args.top_categories,
        max_pages_per_category=args.category_pages,
        ai_filter_limit=ai_filter_limit,
        enable_round3=enable_round3,
        round3_top_asins=round3_top_asins,
        round3_top_categories=round3_top_categories,
        filter_max_sales=filter_max_sales
    )


def run_batch_keywords(scraper: BatchScraper, keywords: List[str], args: argparse.Namespace) -> List[dict]:
    """
    执行批量关键词抓取

    Args:
        scraper: BatchScraper 实例
        keywords: 关键词列表
        args: 命令行参数

    Returns:
        所有抓取结果列表
    """
    results = []

    for i, keyword in enumerate(keywords, 1):
        logger.info(f"{'#'*60}")
        logger.info(f"# 进度: {i}/{len(keywords)} - {keyword}")
        logger.info(f"{'#'*60}")

        result = run_single_keyword(scraper, keyword, args)
        results.append(result)

    return results


def print_batch_summary(results: List[dict], db_path: str):
    """打印批量抓取汇总"""
    logger.info(f"{'='*60}")
    logger.info("批量抓取完成汇总")
    logger.info(f"{'='*60}")

    total_asins = sum(r.get('total_asins', 0) for r in results if r.get('success'))
    success_count = sum(1 for r in results if r.get('success'))

    logger.info(f"  成功: {success_count}/{len(results)}")
    logger.info(f"  总 ASIN: {total_asins}")
    logger.info(f"  数据库: {db_path}")


def main(args: List[str] = None) -> int:
    """
    主入口函数

    Args:
        args: 命令行参数列表，None 时使用 sys.argv

    Returns:
        退出码：0 成功，1 失败
    """
    # 解析参数
    parsed_args = parse_args(args)

    # 验证参数
    mode, error = validate_args(parsed_args)
    if error:
        logger.error(f"错误: {error}")
        logger.info("使用 --help 查看帮助信息")
        return 1

    # 获取 API Key
    api_key = os.environ.get('SCRAPERAPI_KEY')
    if not api_key:
        logger.error("错误: 请设置环境变量 SCRAPERAPI_KEY")
        logger.info("或在 data_summary/.env 文件中配置")
        return 1

    # 创建抓取器
    use_sellerspirit = not parsed_args.no_sellerspirit
    use_ai_filter = not getattr(parsed_args, 'no_ai_filter', False)
    scraper = BatchScraper(
        api_key=api_key,
        db_path=parsed_args.db_path,
        use_sellerspirit=use_sellerspirit,
        use_ai_filter=use_ai_filter
    )

    # 执行抓取
    if mode == 'single':
        # 单关键词模式
        result = run_single_keyword(scraper, parsed_args.keyword, parsed_args)

        # 输出 JSON 结果
        logger.info(f"{'='*60}")
        json_output = json.dumps(result, indent=2, ensure_ascii=False)
        logger.info(f"JSON 结果:\n{json_output}")
        print(json_output)

        return 0 if result.get('success') else 1

    elif mode == 'batch':
        # 批量模式
        keywords = load_keywords_from_file(parsed_args.batch)
        if not keywords:
            logger.error("错误: 关键词文件为空")
            return 1

        logger.info(f"加载了 {len(keywords)} 个关键词:")
        for i, kw in enumerate(keywords, 1):
            logger.info(f"  {i}. {kw}")

        results = run_batch_keywords(scraper, keywords, parsed_args)

        # 打印汇总
        print_batch_summary(results, parsed_args.db_path)

        # 保存结果到文件
        output_file = f"batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logger.info(f"  结果文件: {output_file}")

        success_count = sum(1 for r in results if r.get('success'))
        return 0 if success_count == len(results) else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
