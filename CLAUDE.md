# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 编码规范（必须遵守）

**重要**：所有编码任务必须遵循 `.claude/skills/prules/SKILL.md` 中定义的个人编码标准和工作流程。

核心要求：
- **TDD**：测试先行，红灯→绿灯→重构
- **文档同步**：每次提交必须更新 `docs/CHANGELOG.md`
- **中文注释**：所有注释使用中文
- **Bug 修复**：必须先读取报错 → 分析原因 → 修复 → 添加测试用例
- **工作流程**：方案设计 ✋ → 编写测试 ✋ → 实现代码 ✋ → 验证提交 ✋

详细规范请查阅 `.claude/skills/prules/SKILL.md`。

## 项目概述

大批量 Amazon ASIN 抓取器，使用 ScraperAPI 进行数据采集，支持关键词搜索、分类扩展和多级筛选。

## 常用命令

```bash
# 单关键词抓取（默认启用 AI 筛选）
python main.py "camping"

# 带参数抓取
python main.py "hiking" --max-pages 50 --top-categories 5

# 自定义 AI 筛选数量（每个分类保留 50 个）
python main.py "camping" --ai-limit 50

# 自定义销量筛选阈值（保留销量 <= 200 的产品）
python main.py "camping" --filter-max-sales 200

# 禁用 AI 筛选
python main.py "camping" --no-ai-filter

# 启用第3轮深度分类抓取
python main.py "camping" --round3

# 批量关键词抓取（从文件读取）
python main.py --batch keywords.txt

# 运行测试
python -m pytest tests/ -v
```

## 环境配置

API 密钥从 `D:\Product\data_summary\.env` 加载：
```
SCRAPERAPI_KEY=your_key_here
GEMINI_API_KEY=your_gemini_key_here  # AI 筛选功能需要
```

## 架构

### 文件结构

```
large_data/
├── main.py              # 统一入口
├── src/                 # 源代码目录
│   ├── __init__.py      # 模块导出
│   ├── scraper.py       # 主抓取器 (BatchScraper)
│   ├── database.py      # 数据库管理器 (BatchScraperDB)
│   ├── category.py      # 分类分析
│   ├── ai_analyzer.py   # AI 产品筛选器 (Gemini)
│   ├── utils.py         # 工具函数
│   └── logger.py        # 日志模块
├── tests/               # 测试目录
├── docs/                # 文档目录
└── data/                # 数据库目录
```

### 依赖关系

本项目依赖 `D:\Product\data_summary` 中的 `AmazonScraper` 类：
- `external_apis/amazon_scraper.py` - ScraperAPI 封装，提供智能搜索和批量抓取功能

### 核心类

- **BatchScraper** (`src/scraper.py`) - 主抓取器，执行流程：
  1. `scrape_keyword()` - 关键词搜索，智能停止（销量低于阈值时停止）
  2. `fetch_sellerspirit_categories()` - 获取卖家精灵分类数据
  3. `analyze_categories()` - 分析产品分类分布（支持 AI 筛选）
  4. `scrape_top_categories()` - 扩展抓取热门分类
  5. `filter_by_sponsored()` - 剔除广告 ASIN
  6. `filter_by_category()` - 分类筛选，只保留数量最多的分类，并计算平均价格和中位数
  7. `filter_by_sales()` - 销量筛选，剔除高销量产品
  8. `filter_by_price()` - 价格筛选，剔除价格高于平均价/中位数的产品
  8.5. `enrich_with_sellerspirit_history()` - 数据补充，获取卖家精灵历史销量数据

- **BatchScraperDB** (`src/database.py`) - SQLite 数据库管理器

- **GeminiProductAnalyzer** (`src/ai_analyzer.py`) - AI 产品筛选器
  - 使用 Gemini API 验证产品与关键词的相关性
  - 支持高并发（动态调整并发数）
  - 每个分类只保留前 N 个相关产品

### 数据库

位置：`data/batch_scraper.db`

| 表 | 用途 |
|---|---|
| `asins` | ASIN 数据（主键：asin + keyword） |
| `category_stats` | 产品分类统计 |
| `scrape_tasks` | 抓取任务记录 |
| `sellerspirit_data` | 卖家精灵分类数据缓存 |

### ScraperAPI 字段映射

ScraperAPI 返回的字段名与通用名称不同：
- `stars` → rating
- `total_reviews` → reviews_count
- `purchase_history_message` → 需解析为 sales_volume（如 "2K+ bought" → 2000）
- `url` → 产品URL（用于识别广告）
- `is_sponsored` → 是否为广告（通过 URL 特征识别）

## 工作流程

```
输入关键词
    ↓
步骤1: ScraperAPI 搜索
    ↓
步骤1.5: 获取卖家精灵分类数据
    ↓
步骤2: 分析分类分布（AI 筛选相关分类）
    ↓
步骤3: 扩展抓取热门分类
    ↓
步骤4: 深度分类扩展（可选，--round3）
    ↓
步骤5: 广告筛选（剔除 is_sponsored=1）
    ↓
步骤6: 分类筛选（只保留数量最多的1个分类，计算平均价格和中位数）
    ↓
步骤7: 销量筛选（剔除销量 > 100）
    ↓
步骤8: 价格筛选（剔除价格 > min(平均价, 中位数)）
    ↓
步骤8.5: 数据补充（卖家精灵历史销量、月销量）
    ↓
步骤9: 导出 CSV
```

## 筛选规则

| 步骤 | 规则 | 说明 |
|------|------|------|
| 步骤5 | 广告筛选 | 剔除 URL 中包含广告特征（sspa, sponsored 等）的 ASIN |
| 步骤6 | 分类筛选 | 按 category_sub 聚类，只保留数量最多的1个分类，并计算该分类的平均价格和中位数 |
| 步骤7 | 销量筛选 | 剔除销量 > 100 的 ASIN（可通过 --filter-max-sales 调整） |
| 步骤8 | 价格筛选 | 剔除价格 > min(平均价格, 中位数) 的 ASIN |
| 步骤8.5 | 数据补充 | 使用卖家精灵 Hook 补充：最近3个月销量(sales_3m)、卖家精灵月销量(ss_monthly_sales) |
