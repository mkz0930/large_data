"""
分类分析模块
提供产品分类提取、统计分析功能
"""

import re
from typing import List, Dict
from collections import Counter


# 停用词列表（常见无意义词）
STOPWORDS = {
    # 冠词、连词、介词
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
    'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
    # 代词
    'it', 'its', 'this', 'that', 'these', 'those', 'i', 'you', 'he',
    'she', 'we', 'they', 'what', 'which', 'who', 'whom', 'where', 'when',
    'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more', 'most',
    'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same',
    'so', 'than', 'too', 'very', 'just', 'also', 'now', 'new', 'used',
    # 数量词
    'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
    'pack', 'pcs', 'piece', 'pieces', 'set', 'sets', 'pair', 'pairs',
    'person', 'people', 'man', 'seat', 'seats', 'count', 'qty',
    # 尺寸单位
    'size', 'large', 'small', 'medium', 'xl', 'xxl', 'xs', 'l', 'm', 's',
    'inch', 'inches', 'ft', 'feet', 'cm', 'mm', 'lb', 'lbs', 'oz', 'kg', 'g',
    'gallon', 'quart', 'liter', 'litre', 'ml',
    # 颜色
    'black', 'white', 'red', 'blue', 'green', 'yellow', 'pink', 'purple',
    'gray', 'grey', 'brown', 'orange', 'silver', 'gold', 'beige', 'navy',
    'color', 'colors', 'multi', 'multicolor',
    # 营销词
    'amazon', 'brand', 'best', 'top', 'premium', 'quality', 'pro',
    'deluxe', 'ultra', 'super', 'extra', 'plus', 'max', 'mini', 'lite',
    'official', 'original', 'genuine', 'authentic', 'upgraded', 'improved',
    # 人群
    'men', 'women', 'kids', 'adult', 'adults', 'boy', 'girl', 'baby',
    'boys', 'girls', 'babies', 'children', 'child', 'toddler', 'teen',
    'mens', 'womens', 'unisex', 'family',
    # 常见形容词
    'portable', 'foldable', 'folding', 'adjustable', 'waterproof',
    'lightweight', 'heavy', 'duty', 'durable', 'sturdy', 'strong',
    'soft', 'hard', 'thick', 'thin', 'wide', 'narrow', 'long', 'short',
    'indoor', 'outdoor', 'home', 'office', 'travel', 'car', 'garden'
}


def extract_ngrams(text: str, n: int) -> List[str]:
    """
    从文本中提取 n-gram

    Args:
        text: 输入文本
        n: n-gram 的 n 值

    Returns:
        n-gram 列表
    """
    # 清理文本，只保留字母和空格
    text = re.sub(r'[^a-zA-Z\s]', ' ', text.lower())
    words = text.split()

    if len(words) < n:
        return []

    ngrams = []
    for i in range(len(words) - n + 1):
        ngram = ' '.join(words[i:i+n])
        ngrams.append(ngram)
    return ngrams


def extract_product_types(
    search_results: List[Dict],
    search_keyword: str,
    min_count: int = 3,
    top_n: int = 20
) -> List[str]:
    """
    动态提取产品类型关键词
    从产品名称中提取高频 N-gram 词组

    Args:
        search_results: 搜索结果列表
        search_keyword: 搜索关键词（会被加入停用词）
        min_count: 最小出现次数
        top_n: 返回前 N 个

    Returns:
        产品类型关键词列表
    """
    # 将搜索关键词也加入停用词
    stopwords = STOPWORDS.copy()
    search_words = set(re.sub(r'[^a-zA-Z\s]', ' ', search_keyword.lower()).split())
    stopwords.update(search_words)

    # 统计所有 N-gram
    ngram_counter = Counter()

    for item in search_results:
        name = item.get('name') or ''
        if not name:
            continue

        # 提取 1-gram, 2-gram, 3-gram
        for n in [1, 2, 3]:
            ngrams = extract_ngrams(name, n)
            for ngram in ngrams:
                words = ngram.split()
                # 单词本身是停用词则跳过
                if n == 1 and ngram in stopwords:
                    continue
                # 多词组合：如果所有词都是停用词则跳过
                if n > 1 and all(w in stopwords for w in words):
                    continue
                # 过滤太短的词
                if n == 1 and len(ngram) < 3:
                    continue
                ngram_counter[ngram] += 1

    # 过滤低频词，按频率排序
    valid_ngrams = [
        (ngram, count) for ngram, count in ngram_counter.items()
        if count >= min_count
    ]
    # 优先长词组，同长度按频率排序
    valid_ngrams.sort(key=lambda x: (-len(x[0].split()), -x[1]))

    # 去重：如果短词组是长词组的子串，则移除短词组
    result = []
    for ngram, count in valid_ngrams:
        is_subset = False
        for existing in result:
            if ngram in existing and ngram != existing:
                is_subset = True
                break
        if not is_subset:
            result.append(ngram)
        if len(result) >= top_n:
            break

    return result


def analyze_category_distribution(
    search_results: List[Dict],
    keyword: str,
    use_sellerspirit: bool = False
) -> List[Dict]:
    """
    分析产品分类分布

    Args:
        search_results: 搜索结果列表
        keyword: 搜索关键词
        use_sellerspirit: 是否使用卖家精灵分类数据

    Returns:
        分类统计列表，按数量降序排列
    """
    # 检查是否已有卖家精灵分类数据
    has_ss_data = any(item.get('category_sub') for item in search_results)

    if use_sellerspirit is None:
        use_sellerspirit = has_ss_data

    # 如果没有卖家精灵数据，使用动态提取
    product_type_keywords = []
    if not use_sellerspirit or not has_ss_data:
        use_sellerspirit = False
        product_type_keywords = extract_product_types(
            search_results, keyword, min_count=3, top_n=30
        )

    # 统计产品类型
    category_counter = Counter()
    category_data = {}

    for item in search_results:
        asin = item.get('asin')
        if not asin:
            continue

        # 获取分类信息
        if use_sellerspirit and item.get('category_sub'):
            found_type = item.get('category_sub') or 'Other'
        else:
            # Fallback: 从产品名称中提取类型
            name = (item.get('name') or '').lower()
            found_type = None
            if not use_sellerspirit:
                for ptype in product_type_keywords:
                    if ptype in name:
                        found_type = ptype.title()
                        break
            if not found_type:
                found_type = 'Other'

        category_counter[found_type] += 1

        if found_type not in category_data:
            category_data[found_type] = {
                'prices': [],
                'ratings': [],
                'reviews': []
            }

        # 收集数据用于计算平均值
        price = item.get('price')
        if price:
            if isinstance(price, str):
                match = re.search(r'[\d.]+', price.replace(',', ''))
                if match:
                    category_data[found_type]['prices'].append(float(match.group()))
            else:
                category_data[found_type]['prices'].append(float(price))

        rating = item.get('stars') or item.get('rating')
        if rating:
            category_data[found_type]['ratings'].append(float(rating))

        reviews = item.get('total_reviews') or item.get('ratings_total')
        if reviews:
            category_data[found_type]['reviews'].append(int(reviews))

    # 构建统计结果（剔除 Other 分类）
    stats = []
    for product_type, count in category_counter.most_common():
        # 跳过 Other 分类
        if product_type == 'Other':
            continue
        data = category_data.get(product_type, {})
        stat = {
            'category': product_type,
            'count': count,
            'avg_price': sum(data['prices']) / len(data['prices']) if data['prices'] else None,
            'avg_rating': sum(data['ratings']) / len(data['ratings']) if data['ratings'] else None,
            'total_reviews': sum(data['reviews']) if data['reviews'] else None
        }
        stats.append(stat)

    return stats


def print_category_stats(stats: List[Dict], use_sellerspirit: bool = False):
    """
    打印分类统计结果

    Args:
        stats: 分类统计列表
        use_sellerspirit: 是否使用卖家精灵数据
    """
    source_label = "卖家精灵" if use_sellerspirit else "动态提取"
    print(f"\n类目分布 - {source_label} (共 {len(stats)} 个类目):")
    print("-" * 95)
    print(f"{'排名':<4} {'类目':<36} {'数量':<6} {'平均价格':<10} {'平均评分':<8} {'总评论数':<12}")
    print("-" * 95)

    for i, stat in enumerate(stats[:10], 1):
        avg_price = f"${stat['avg_price']:.2f}" if stat['avg_price'] else "N/A"
        avg_rating = f"{stat['avg_rating']:.1f}" if stat['avg_rating'] else "N/A"
        total_reviews = f"{stat['total_reviews']:,}" if stat['total_reviews'] else "N/A"
        category_display = stat['category'][:34] + '..' if len(stat['category']) > 36 else stat['category']
        print(f"{i:<4} {category_display:<36} {stat['count']:<6} {avg_price:<10} {avg_rating:<8} {total_reviews:<12}")

    if len(stats) > 10:
        print(f"... 还有 {len(stats) - 10} 个类目")
