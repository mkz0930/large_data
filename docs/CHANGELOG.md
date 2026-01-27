# 变更日志

所有重要变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

---

## [1.4.2] - 2026-01-27

### 新增

- 卖家精灵历史数据缓存功能
  - 步骤7.5 数据补充时，已获取的卖家精灵数据会缓存到数据库
  - 缓存有效期 20 天，20 天内不重复抓取相同 ASIN
  - 大幅减少 API 调用次数，提升抓取效率

### 变更

- `src/database.py` - 新增缓存相关方法
  - 新增 `sellerspirit_history_cache` 表存储缓存数据
  - `get_cached_sellerspirit_history()` - 获取缓存的历史数据
  - `save_sellerspirit_history_cache()` - 保存历史数据到缓存
  - `get_asins_needing_history_fetch()` - 获取需要从 API 获取的 ASIN 列表

- `src/scraper.py` - `enrich_with_sellerspirit_history` 方法
  - 新增 `cache_days` 参数，可自定义缓存有效期（默认 20 天）
  - 优先从缓存获取数据，仅对缺失的 ASIN 调用 API
  - 新获取的数据自动保存到缓存

### 数据库表结构

新增 `sellerspirit_history_cache` 表：

| 字段 | 类型 | 说明 |
|------|------|------|
| `asin` | TEXT | ASIN 码（唯一） |
| `sales_3m` | INTEGER | 最近3个月销量 |
| `ss_monthly_sales` | INTEGER | 卖家精灵月销量 |
| `listing_date` | TEXT | 上架日期 |
| `avg_monthly_sales` | INTEGER | 平均月销量 |
| `sales_months_count` | INTEGER | 有销量数据的月份数 |
| `ss_rating` | REAL | 卖家精灵评分 |
| `ss_reviews` | INTEGER | 卖家精灵评论数 |
| `raw_trends` | TEXT | 原始 trends 数据（JSON） |
| `updated_at` | TEXT | 缓存更新时间 |

---

## [1.4.1] - 2026-01-27

### 修复

- `src/apify_price.py` - 修复 Apify API 调用失败问题
  - 弃用 `apify_client` 库，改用 `data_summary` 中的 `ApifyAmazonScraper`
  - 使用 REST API 直接调用，支持异步并发和智能重试
  - 保持原有缓存功能不变

---

## [1.4.0] - 2026-01-27

### 新增

- `src/apify_db.py` - Apify 数据缓存数据库
  - 缓存已抓取的 Apify 价格历史数据
  - 最近 20 天内抓取过的数据不再重复抓取，节省 API 调用费用
  - 支持批量查询缓存状态
  - 支持清理过期缓存

- `tests/test_apify_db.py` - ApifyDB 测试用例（11 个测试）

### 变更

- `src/apify_price.py` - ApifyPriceFetcher 集成缓存功能
  - `get_price_history()` 优先使用缓存数据
  - `get_multiple_price_history()` 批量获取时自动区分缓存和需要抓取的 ASIN
  - 新增 `cache_days` 参数，可自定义缓存有效期（默认 20 天）

- `src/__init__.py` - 导出新模块
  - 新增导出：`ApifyDB`, `ApifyPriceFetcher`, `is_apify_available`, `get_apify_cache_stats`, `clean_apify_cache`

### 新增辅助函数

| 函数 | 说明 |
|------|------|
| `get_apify_cache_stats()` | 获取缓存统计信息（总数、有效数、过期数） |
| `clean_apify_cache(days)` | 清理指定天数前的过期缓存 |

### 数据库表结构

新增 `data/apify_cache.db` 数据库：

| 字段 | 类型 | 说明 |
|------|------|------|
| `asin` | TEXT | ASIN 码（唯一） |
| `price` | REAL | 当前价格 |
| `price_min` | REAL | 历史最低价 |
| `price_max` | REAL | 历史最高价 |
| `price_min_date` | TEXT | 最低价日期 |
| `price_max_date` | TEXT | 最高价日期 |
| `listed_at` | TEXT | 上架日期 |
| `raw_data` | TEXT | 原始 JSON 数据 |
| `created_at` | TEXT | 缓存创建时间 |

---

## [1.3.1] - 2026-01-27

### 新增

- 评论数据填充功能
  - 当 ScraperAPI 的 `rating`（评分）为空时，自动使用卖家精灵数据填充
  - 当 ScraperAPI 的 `reviews_count`（评论数）为空时，自动使用卖家精灵数据填充

### 变更

- `src/scraper.py` - `enrich_with_sellerspirit_history` 方法
  - 新增提取卖家精灵的 `rating` 和 `reviews` 字段
  - `history_map` 新增 `ss_rating` 和 `ss_reviews` 字段

- `src/database.py` - `batch_update_sellerspirit_history` 方法
  - 新增条件更新逻辑：当原有 rating/reviews_count 为空或为 0 时，用卖家精灵数据填充

### CSV 导出字段

导出的 CSV 文件包含以下评论相关字段：
| 字段 | 说明 |
|------|------|
| `rating` | 产品评分（优先 ScraperAPI，为空时用卖家精灵数据） |
| `reviews_count` | 评论数量（优先 ScraperAPI，为空时用卖家精灵数据） |

---

## [1.3.0] - 2026-01-26

### 新增

- `src/logger.py` - 统一日志模块
  - 支持同时输出到控制台和文件
  - 日志文件按日期轮转，保存在 `logs/` 目录
  - 支持日志级别：DEBUG, INFO, WARNING, ERROR
  - 格式：`[时间] [级别] [模块] 消息`
- `tests/test_logger.py` - 日志模块测试用例（15 个测试）

### 变更

- `main.py` - 替换 print 为 logger
- `src/scraper.py` - 替换 print 为 logger
- `src/database.py` - 替换 print 为 logger
- 所有日志自动保存到 `logs/batch_scraper_YYYY-MM-DD.log`

### 日志级别使用规范

| 级别 | 用途 | 示例 |
|------|------|------|
| DEBUG | 调试信息 | 数据库迁移详情 |
| INFO | 正常流程 | 步骤开始/完成、统计汇总 |
| WARNING | 警告 | 缓存命中、跳过操作 |
| ERROR | 错误 | 异常捕获、失败操作 |

### 日志文件位置

```
logs/
└── batch_scraper_2026-01-26.log
```

---

## [1.2.0] - 2026-01-26

### 新增

- `src/ai_analyzer.py` - Gemini AI 产品筛选器
  - 使用 Gemini API 快速并行验证产品相关性
  - 动态并发控制（自动调整并发数）
  - 每个分类只保留前 N 个相关产品
- 命令行参数：
  - `--ai-filter` 启用 AI 筛选
  - `--ai-limit` 设置每个分类保留的最大数量（默认 100）

### 使用方式

```bash
# 启用 AI 筛选
python main.py "camping" --ai-filter

# 自定义筛选数量
python main.py "camping" --ai-filter --ai-limit 50
```

### 环境变量

需要设置 `GEMINI_API_KEY` 环境变量才能使用 AI 筛选功能。

---

## [1.1.0] - 2026-01-26

### 新增

- `main.py` 统一入口，整合单关键词和批量抓取模式
- `src/` 源代码目录，模块化拆分：
  - `src/scraper.py` - 主抓取器 (BatchScraper)
  - `src/database.py` - 数据库管理器 (BatchScraperDB)
  - `src/category.py` - 分类分析
  - `src/utils.py` - 工具函数
- `tests/test_main.py` 测试用例（15 个测试）
- `docs/` 文档目录
  - `REQUIREMENTS.md` 需求文档
  - `ARCHITECTURE.md` 架构文档
  - `CHANGELOG.md` 变更日志

### 变更

- 代码从单文件拆分为模块化结构
- 命令行使用方式统一为 `python main.py`
- 批量模式通过 `--batch` 参数指定

### 使用方式

```bash
# 单关键词模式
python main.py "camping"
python main.py "hiking" --max-pages 50 --top-categories 5

# 批量模式
python main.py --batch keywords.txt
```

---

## [1.0.0] - 初始版本

### 功能

- `batch_scraper.py` - 大批量 ASIN 抓取器
- `batch_keywords.py` - 批量关键词抓取
- ScraperAPI 集成
- 卖家精灵分类数据集成（可选）
- SQLite 数据存储
