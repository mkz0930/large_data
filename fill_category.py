"""
补充缺失的分类数据
使用卖家精灵 Hook 获取 ASIN 的分类信息
"""

import sys
import time
import sqlite3
import importlib.util
from pathlib import Path

# 添加 data_summary 路径
DATA_SUMMARY_PATH = Path(__file__).parent.parent / "data_summary"
sys.path.insert(0, str(DATA_SUMMARY_PATH))

# 动态导入卖家精灵 Hook
spec = importlib.util.spec_from_file_location(
    "sellerspirit_hook",
    DATA_SUMMARY_PATH / "src" / "collectors" / "sellerspirit_hook.py"
)
sellerspirit_hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sellerspirit_hook)


def chunk_list(lst, chunk_size):
    """将列表分割成指定大小的块"""
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]


def get_missing_asins(db_path: str, keyword: str) -> list:
    """获取缺少分类数据的 ASIN"""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("""
            SELECT asin FROM asins
            WHERE keyword = ? AND (category_sub IS NULL OR category_sub = '')
        """, (keyword,))
        return [row[0] for row in cursor.fetchall()]


def update_category_data(db_path: str, keyword: str, category_map: dict) -> int:
    """更新 ASIN 的分类数据"""
    updated = 0
    with sqlite3.connect(db_path) as conn:
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
            except Exception as e:
                print(f"更新 {asin} 失败: {e}")
        conn.commit()
    return updated


def fetch_category_via_hook(asins: list) -> dict:
    """使用 Hook 获取分类数据"""
    token = sellerspirit_hook.login()
    if not token:
        print("Hook 登录失败")
        return {}

    sellerspirit_hook.token = token
    category_map = {}
    chunks = list(chunk_list(asins, 40))

    for i, chunk in enumerate(chunks):
        print(f"  处理批次 {i+1}/{len(chunks)} ({len(chunk)} 个 ASIN)...")

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

        if i < len(chunks) - 1:
            time.sleep(2)

    return category_map


def main():
    db_path = "data/batch_scraper.db"
    keyword = "camping"

    print(f"=" * 60)
    print(f"补充分类数据 - 关键词: {keyword}")
    print(f"=" * 60)

    # 1. 获取缺少分类的 ASIN
    missing_asins = get_missing_asins(db_path, keyword)
    print(f"\n缺少分类数据的 ASIN: {len(missing_asins)} 个")

    if not missing_asins:
        print("所有 ASIN 都有分类数据，无需补充")
        return

    # 2. 使用 Hook 获取分类数据
    print(f"\n正在使用 Hook 获取分类数据...")
    category_map = fetch_category_via_hook(missing_asins)
    print(f"成功获取 {len(category_map)} 个 ASIN 的分类数据")

    # 3. 更新数据库
    if category_map:
        print(f"\n正在更新数据库...")
        updated = update_category_data(db_path, keyword, category_map)
        print(f"成功更新 {updated} 条记录")

    # 4. 统计结果
    print(f"\n" + "=" * 60)
    print("补充后的分类统计")
    print("=" * 60)

    with sqlite3.connect(db_path) as conn:
        # 总数统计
        cursor = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN category_sub IS NOT NULL AND category_sub != '' THEN 1 ELSE 0 END) as has_category
            FROM asins WHERE keyword = ?
        """, (keyword,))
        row = cursor.fetchone()
        total, has_category = row[0], row[1]
        print(f"\n总 ASIN: {total}")
        print(f"有分类数据: {has_category} ({has_category*100/total:.1f}%)")
        print(f"无分类数据: {total - has_category} ({(total-has_category)*100/total:.1f}%)")

        # 分类分布
        cursor = conn.execute("""
            SELECT category_sub, COUNT(*) as count
            FROM asins
            WHERE keyword = ? AND category_sub IS NOT NULL AND category_sub != ''
            GROUP BY category_sub
            ORDER BY count DESC
            LIMIT 30
        """, (keyword,))
        rows = cursor.fetchall()

        print(f"\n分类分布（前30）:")
        for i, (cat, count) in enumerate(rows, 1):
            print(f"  {i:2}. {cat}: {count}")


if __name__ == "__main__":
    main()
