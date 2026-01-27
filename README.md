# 大批量 ASIN 抓取器

使用 ScraperAPI 快速抓取 Amazon 产品数据，支持关键词搜索和分类扩展。

## 功能

1. **关键词搜索**: 输入关键词，自动抓取所有相关 ASIN（智能停止：当销量低于阈值时停止）
2. **分类数据获取**: 通过卖家精灵获取 ASIN 分类信息
3. **分类扩展**: 自动抓取前 N 个热门分类的更多 ASIN
4. **数据库存储**: 所有数据保存到 SQLite 数据库

## 环境配置

确保 `D:\Product\data_summary\.env` 文件中配置了 ScraperAPI 密钥：

```
SCRAPERAPI_KEY=your_api_key_here
```

## 使用方法

### 单关键词抓取

```bash
# 基本用法
python main.py "camping"

# 完整参数
python main.py "camping" \
    --country us \
    --max-pages 100 \
    --sales-threshold 10 \
    --top-categories 3 \
    --category-pages 50 \
    --db-path data/batch_scraper.db
```

### 批量关键词抓取

```bash
# 从文件读取关键词
python main.py --batch keywords.txt

# 完整参数
python main.py -b keywords.txt \
    --country us \
    --max-pages 100 \
    --top-categories 3
```

关键词文件格式（每行一个关键词）：
```
camping gear
hiking backpack
outdoor tent
```

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--country, -c` | 国家代码 | us |
| `--max-pages, -p` | 关键词搜索最大页数 | 100 |
| `--sales-threshold, -s` | 销量阈值（低于此值停止） | 10 |
| `--top-categories, -t` | 抓取前N个热门类目 | 3 |
| `--category-pages` | 每个类目最大页数 | 50 |
| `--db-path` | 数据库路径 | data/batch_scraper.db |

## 数据库结构

### asins 表
存储所有抓取的 ASIN 数据

| 字段 | 说明 |
|------|------|
| asin | Amazon 标准识别号 |
| keyword | 搜索关键词 |
| source_type | 来源类型 (keyword_search/category_search) |
| source_value | 来源值（关键词或类目名） |
| name | 产品名称 |
| brand | 品牌 |
| category | 类目 |
| price | 价格 |
| rating | 评分 |
| reviews_count | 评论数 |
| sales_volume | 销量 |
| page_rank | 页面排名 |

### category_stats 表
类目统计数据

| 字段 | 说明 |
|------|------|
| keyword | 关键词 |
| category | 类目名称 |
| asin_count | ASIN 数量 |
| avg_price | 平均价格 |
| avg_rating | 平均评分 |
| total_reviews | 总评论数 |

### scrape_tasks 表
抓取任务记录

## 查询示例

```sql
-- 查看关键词的 ASIN 数量
SELECT keyword, COUNT(DISTINCT asin) as count
FROM asins
GROUP BY keyword;

-- 查看类目分布
SELECT category, asin_count
FROM category_stats
WHERE keyword = 'camping gear'
ORDER BY asin_count DESC;

-- 导出所有 ASIN
SELECT DISTINCT asin FROM asins WHERE keyword = 'camping gear';
```

## 工作流程

```
输入关键词
    ↓
[步骤1] ScraperAPI 搜索关键词
    ↓ (智能停止：销量 < 阈值)
[步骤2] 分析类目分布
    ↓
[步骤3] 抓取前3个热门类目
    ↓
保存到数据库
```
