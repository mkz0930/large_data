"""
获取卖家精灵 Hook 返回的示例数据
"""
import sys
import json
from pathlib import Path

# 添加路径
DATA_SUMMARY_PATH = Path(__file__).parent.parent.parent / "data_summary"
sys.path.insert(0, str(DATA_SUMMARY_PATH / "src" / "collectors"))

import sellerspirit_hook

if __name__ == '__main__':
    print("登录卖家精灵...")
    token = sellerspirit_hook.login()
    if not token:
        print("登录失败")
        sys.exit(1)

    print(f"登录成功")
    sellerspirit_hook.token = token

    # 测试 ASIN
    test_asin = "B0CRDQ6458"
    print(f"获取 ASIN: {test_asin}")

    data = sellerspirit_hook.getData(test_asin)

    if data and len(data) > 0:
        sample = data[0]
        output_path = Path(__file__).parent / "hook_sample_data.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(sample, f, ensure_ascii=False, indent=2)
        print(f"已保存到: {output_path}")
        print(f"\n关键字段:")
        print(f"  asin: {sample.get('asin')}")
        print(f"  node_label_path: {sample.get('node_label_path')}")
        print(f"  bsrList: {sample.get('bsrList')}")
    else:
        print("获取数据失败")
