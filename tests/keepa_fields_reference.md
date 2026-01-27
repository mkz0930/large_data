# Keepa API 字段参考文档

基于 ASIN `B0BK9HFZ77` 的实际返回数据整理。

## 基本信息

| 字段 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `asin` | string | ASIN 码 | B0BK9HFZ77 |
| `title` | string | 产品标题 | Amico 24 Pack 6 Inch... |
| `brand` | string | 品牌 | Amico |
| `manufacturer` | string | 制造商 | Amico |
| `model` | string | 型号 | HS-STC512WH |
| `partNumber` | string | 零件号 | HS-STC512WH |
| `color` | string | 颜色 | White |
| `size` | string | 尺寸 | 6 Inch |
| `style` | string | 款式 | - |
| `binding` | string | 装订/类型 | Tools & Home Improvement |

## 分类信息

| 字段 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `productGroup` | string | 产品组 | Home Improvement |
| `rootCategory` | int | 根分类 ID | 228013 |
| `categories` | list[int] | 分类 ID 列表 | [6291360011] |
| `categoryTree` | list[dict] | 分类树 | Tools & Home Improvement > Electrical > ... |
| `salesRankDisplayGroup` | string | 销量排名分类 | home_improvement_display_on_website |

## 销售数据

| 字段 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `monthlySold` | int | 月销量 | 3000 |
| `availabilityAmazon` | int | 亚马逊库存状态 | -1 (0=无, -1=缺货, >0=有货) |
| `isSNS` | bool | 是否支持订阅省 | False |
| `isB2B` | bool | 是否 B2B 商品 | False |
| `newPriceIsMAP` | bool | 新品价格是否为 MAP | False |
| `isEligibleForSuperSaverShipping` | bool | 是否支持超级省运费 | True |
| `isEligibleForTradeIn` | bool | 是否支持以旧换新 | False |

## 时间信息

| 字段 | 类型 | 说明 | 转换方式 |
|------|------|------|----------|
| `listedSince` | int | 上架时间 (Keepa 时间戳) | `(keepa_time + 21564000) * 60` = Unix 时间戳 |
| `trackingSince` | int | 开始追踪时间 | 同上 |
| `lastUpdate` | int | 最后更新时间 | 同上 |
| `lastPriceChange` | int | 最后价格变动时间 | 同上 |
| `releaseDate` | int | 发布日期 | 同上 |

## 尺寸重量

| 字段 | 类型 | 说明 | 单位 |
|------|------|------|------|
| `itemHeight` | int | 商品高度 | 0.01 英寸 |
| `itemLength` | int | 商品长度 | 0.01 英寸 |
| `itemWidth` | int | 商品宽度 | 0.01 英寸 |
| `itemWeight` | int | 商品重量 | 0.01 磅 |
| `packageHeight` | int | 包装高度 | 0.01 英寸 |
| `packageLength` | int | 包装长度 | 0.01 英寸 |
| `packageWidth` | int | 包装宽度 | 0.01 英寸 |
| `packageWeight` | int | 包装重量 | 0.01 磅 |
| `packageQuantity` | int | 包装数量 | - |

## FBA 费用

| 字段 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `fbaFees.pickAndPackFee` | int | 拣货包装费 (分) | 1220 ($12.20) |
| `referralFeePercent` | int | 推荐费百分比 | 11 |

## 变体信息

| 字段 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `parentAsin` | string | 父 ASIN | B0F6V6LLG9 |
| `parentTitle` | string | 父产品标题 | - |
| `variations` | list | 变体列表 | 6 个变体 |
| `variationCSV` | string | 变体属性 CSV | - |

---

## csv 数组 - 历史价格数据

**格式**: `[timestamp1, value1, timestamp2, value2, ...]`

**价格单位**: 分 (除以 100 得美元)

**时间戳转换**: `unix_timestamp = (keepa_time + 21564000) * 60`

| 索引 | 名称 | 说明 | 数据点数 |
|------|------|------|----------|
| 0 | AMAZON | 亚马逊自营价格 | 1 |
| 1 | NEW | 第三方新品最低价 | 377 |
| 2 | USED | 二手最低价 | 518 |
| 3 | SALES | 销量排名 (**不除以 100**) | 6798 |
| 4 | LISTPRICE | 标价/建议零售价 | 18 |
| 5 | COLLECTIBLE | 收藏品价格 | - |
| 6 | REFURBISHED | 翻新品价格 | - |
| 7 | NEW_FBM_SHIPPING | FBM 新品运费 | - |
| 8 | LIGHTNING_DEAL | 闪购价格 | 2 |
| 9 | WAREHOUSE | 亚马逊仓库价格 | - |
| 10 | NEW_FBA | FBA 新品价格 | - |
| 11 | COUNT_NEW | 新品卖家数量 | 244 |
| 12 | COUNT_USED | 二手卖家数量 | 1191 |
| 13 | COUNT_REFURBISHED | 翻新品卖家数量 | - |
| 14 | COUNT_COLLECTIBLE | 收藏品卖家数量 | - |
| 15 | EXTRA_INFO_UPDATES | 额外信息更新 | - |
| 16 | RATING | 评分 (x10, 如 45=4.5 星) | - |
| 17 | COUNT_REVIEWS | 评论数量 | - |
| 18 | BUY_BOX_SHIPPING | Buy Box 运费 | - |

### 解析示例 (Python)

```python
from datetime import datetime

def keepa_to_datetime(keepa_time):
    """Keepa 时间戳转 datetime"""
    unix_ts = (keepa_time + 21564000) * 60
    return datetime.fromtimestamp(unix_ts)

def parse_price_history(csv_data, index=1):
    """解析价格历史 (默认 NEW 价格)"""
    data = csv_data[index]
    history = []
    for i in range(0, len(data), 2):
        if i + 1 < len(data):
            ts, price = data[i], data[i + 1]
            if ts and price and price > 0:
                history.append({
                    'date': keepa_to_datetime(ts),
                    'price': price / 100.0  # 转美元
                })
    return history
```

---

## stats 对象 - 统计汇总

### current[] - 当前价格

索引对应 csv 类型，单位为分。

| 索引 | 类型 | 示例值 | 说明 |
|------|------|--------|------|
| 0 | Amazon | -1 | 无货 |
| 1 | New | 17999 | $179.99 |
| 2 | Used | 8699 | $86.99 |
| 3 | SalesRank | 1361 | #1,361 |
| 4 | ListPrice | 17999 | $179.99 |

### avg[] - 平均价格

统计周期内的平均价格 (分)。

| 索引 | 类型 | 示例值 |
|------|------|--------|
| 1 | New | 13439 ($134.39) |
| 2 | Used | 8977 ($89.77) |

### min[]/max[] - 历史最低/最高

格式: `[keepa_timestamp, price_in_cents]`

| 字段 | 类型 | 值 |
|------|------|-----|
| min[1] | New 最低 | $103.98 |
| max[1] | New 最高 | $249.99 |
| min[2] | Used 最低 | $79.99 |
| max[2] | Used 最高 | $170.99 |

### 销量排名下降次数

反映销售活跃度，数值越高说明销售越频繁。

| 字段 | 说明 | 示例值 |
|------|------|--------|
| `salesRankDrops30` | 30 天内 | 74 |
| `salesRankDrops90` | 90 天内 | 233 |
| `salesRankDrops180` | 180 天内 | 393 |

### Buy Box 信息

| 字段 | 说明 | 示例值 |
|------|------|--------|
| `buyBoxPrice` | Buy Box 价格 (分) | -2 (无数据) |
| `buyBoxShipping` | Buy Box 运费 (分) | -2 |
| `buyBoxIsFBA` | 是否 FBA | None |
| `buyBoxIsAmazon` | 是否亚马逊自营 | None |
| `buyBoxSellerId` | 卖家 ID | None |

### 缺货百分比

数组索引对应 csv 类型，值为百分比 (0-100)，-1 表示无数据。

| 字段 | 说明 |
|------|------|
| `outOfStockPercentage30` | 30 天缺货率 |
| `outOfStockPercentage90` | 90 天缺货率 |

---

## 其他重要字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `monthlySoldHistory` | list | 月销量历史 (格式同 csv) |
| `couponHistory` | list | 优惠券历史 |
| `salesRanks` | dict | 多分类销量排名 |
| `features` | list[str] | 产品特性列表 |
| `images` | list[str] | 图片 ID 列表 |
| `hasReviews` | bool | 是否有评论 |
| `isAdultProduct` | bool | 是否成人商品 |

---

## 特殊值说明

| 值 | 含义 |
|----|------|
| -1 | 无货/缺货 |
| -2 | 无数据 |
| 0 | 免费/无 |
| None | 未追踪 |

---

*生成时间: 2026-01-27*
*测试 ASIN: B0BK9HFZ77*
