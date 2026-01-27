"""
工具函数模块
提供价格解析、销量解析等通用功能
"""

import re
from typing import Optional


def parse_price(price) -> Optional[float]:
    """
    解析价格字符串为浮点数

    Args:
        price: 价格值（字符串、数字或 None）

    Returns:
        解析后的浮点数，无法解析时返回 None

    Examples:
        >>> parse_price("$29.99")
        29.99
        >>> parse_price(19.99)
        19.99
        >>> parse_price("1,299.00")
        1299.0
    """
    if price is None:
        return None
    if isinstance(price, (int, float)):
        return float(price)
    if isinstance(price, str):
        match = re.search(r'[\d.]+', price.replace(',', ''))
        if match:
            return float(match.group())
    return None


def parse_sales(message: str) -> int:
    """
    解析销量信息

    Args:
        message: 销量描述字符串（如 "2K+ bought", "10K+ bought"）

    Returns:
        解析后的销量整数，无数据时返回 0

    Examples:
        >>> parse_sales("2K+ bought in past month")
        2000
        >>> parse_sales("500+ bought")
        500
        >>> parse_sales("1.5M+ bought")
        1500000
    """
    if not message:
        return 0
    match = re.search(r'(\d+(?:\.\d+)?)\s*([KkMm])?\s*\+', message)
    if not match:
        return 0
    number = float(match.group(1))
    unit = match.group(2)
    if unit:
        unit = unit.upper()
        if unit == 'K':
            number *= 1000
        elif unit == 'M':
            number *= 1000000
    return int(number)


def chunk_list(lst: list, chunk_size: int) -> list:
    """
    将列表分割为指定大小的块

    Args:
        lst: 原始列表
        chunk_size: 每块大小

    Returns:
        分块后的列表

    Examples:
        >>> chunk_list([1,2,3,4,5], 2)
        [[1,2], [3,4], [5]]
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def is_same_type(product: dict, keyword: str, target_category: str = None) -> bool:
    """
    判断产品是否与关键词同类

    Args:
        product: 产品字典，需包含 'name' 字段
        keyword: 搜索关键词
        target_category: 可选，限制产品分类

    Returns:
        True 表示同类产品，False 表示不同类

    Examples:
        >>> is_same_type({'name': 'Portable Power Station 1000W'}, 'power station')
        True
        >>> is_same_type({'name': 'Solar Panel 100W'}, 'power station')
        False
    """
    name = product.get('name', '').lower()

    # 关键词必须在标题中
    if keyword.lower() not in name:
        return False

    # 可选：限制分类
    if target_category:
        category = product.get('category', '')
        if target_category.lower() not in category.lower():
            return False

    return True


def filter_same_type(products: list, keyword: str, target_category: str = None) -> list:
    """
    筛选同类产品

    Args:
        products: 产品列表
        keyword: 搜索关键词
        target_category: 可选，限制产品分类

    Returns:
        筛选后的同类产品列表

    Examples:
        >>> products = [{'name': 'Power Station 500W'}, {'name': 'Solar Panel'}]
        >>> filter_same_type(products, 'power station')
        [{'name': 'Power Station 500W'}]
    """
    return [p for p in products if is_same_type(p, keyword, target_category)]
