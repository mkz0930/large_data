# 架构文档

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        main.py                               │
│                      (统一入口)                               │
├─────────────────────────────────────────────────────────────┤
│  parse_args()      - 命令行参数解析                          │
│  validate_args()   - 参数验证和模式选择                       │
│  run_single_keyword() - 单关键词抓取                         │
│  run_batch_keywords() - 批量抓取                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    batch_scraper.py                          │
├─────────────────────────────────────────────────────────────┤
│  BatchScraper                                                │
│  ├── scrape_keyword()           - 步骤1: 关键词搜索          │
│  ├── fetch_sellerspirit_categories() - 步骤1.5: 获取分类     │
│  ├── analyze_categories()       - 步骤2: 分析分类分布        │
│  └── scrape_top_categories()    - 步骤3: 扩展抓取热门分类    │
│                                                              │
│  BatchScraperDB                                              │
│  ├── save_asins()               - 保存 ASIN 数据             │
│  ├── save_category_stats()      - 保存分类统计               │
│  └── get_existing_asins()       - 获取已存在 ASIN            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              D:\Product\data_summary\                        │
│              external_apis\amazon_scraper.py                 │
├─────────────────────────────────────────────────────────────┤
│  AmazonScraper                                               │
│  └── search_keyword_with_smart_stop() - ScraperAPI 封装      │
└─────────────────────────────────────────────────────────────┘
```

## 文件结构

```
large_data/
├── main.py              # 统一入口
├── src/                 # 源代码目录
│   ├── __init__.py      # 模块导出
│   ├── scraper.py       # 主抓取器 (BatchScraper)
│   ├── database.py      # 数据库管理器 (BatchScraperDB)
│   ├── category.py      # 分类分析
│   ├── logger.py        # 统一日志模块
│   └── utils.py         # 工具函数
├── tests/
│   ├── test_main.py     # 入口测试用例
│   └── test_logger.py   # 日志模块测试用例
├── docs/
│   ├── REQUIREMENTS.md  # 需求文档
│   ├── ARCHITECTURE.md  # 架构文档
│   └── CHANGELOG.md     # 变更日志
├── data/
│   └── batch_scraper.db # SQLite 数据库
├── logs/                # 日志目录（自动创建）
│   └── batch_scraper_YYYY-MM-DD.log
├── README.md            # 项目说明
└── CLAUDE.md            # Claude Code 指引
```

## 数据流

```
输入关键词
    │
    ▼
[步骤1] ScraperAPI 搜索
    │
    ▼
[步骤1.5] 卖家精灵获取分类数据
    │
    ▼
[步骤2] 分析产品分类分布
    │
    ▼
[步骤3] 扩展抓取热门分类
    │
    ▼
保存到 SQLite 数据库
```

## 数据库表结构

| 表 | 用途 |
|---|---|
| `asins` | ASIN 数据（主键：asin + keyword） |
| `category_stats` | 产品分类统计 |
| `scrape_tasks` | 抓取任务记录 |

## 外部依赖

| 依赖 | 路径 | 说明 |
|------|------|------|
| AmazonScraper | `D:\Product\data_summary\external_apis\amazon_scraper.py` | ScraperAPI 封装 |
| SellerSpiritCollector | `D:\Product\data_summary\src\collectors\` | 卖家精灵采集器（可选） |
