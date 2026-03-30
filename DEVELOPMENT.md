# 开发文档

本文档面向参与系统开发的工程师，涵盖架构设计、数据流、扩展指南和调试方法。

---

## 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                         前端 (Vue3)                              │
│  Dashboard  │  Keywords  │  AnalysisDetail  │  KwTool           │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP (Axios)
┌──────────────────────────▼──────────────────────────────────────┐
│                      FastAPI (api/)                              │
│  /tasks  │  /analysis  │  /scrape/trigger  │  /keywords/suggest │
│                    CORS Middleware                               │
└────────┬────────────────────────────────────┬────────────────────┘
         │ SQLAlchemy 2.0 async               │ asyncio background task
┌────────▼──────────┐              ┌──────────▼──────────────────┐
│   MySQL (3 表)    │              │   OzonScraper (Playwright)   │
│  keyword_tasks    │◄─────────────│   + ProxyManager             │
│  ozon_products    │              └──────────┬──────────────────-┘
│  ozon_analysis    │                         │ products list
└────────▲──────────┘              ┌──────────▼──────────────────┐
         │ write analysis          │   Claude API Client          │
         └─────────────────────────│   analyze_products()         │
                                   └─────────────────────────────-┘

APScheduler (scheduler/)
  ├── IntervalTrigger(hours=1) → 处理 pending 任务
  └── CronTrigger(02:00)      → batch_rank 写日志
```

---

## 目录结构详解

```
ozon-crawler/
├── config.py               # 全局配置（pydantic-settings 读取 .env）
├── requirements.txt        # Python 依赖锁定
├── .env.example            # 环境变量模板
│
├── api/                    # FastAPI 应用层
│   ├── main.py             # 应用入口、中间件、lifespan
│   ├── database.py         # 异步引擎、会话工厂、Base 类
│   ├── models.py           # SQLAlchemy ORM 模型（3 张表）
│   └── routes/
│       ├── tasks.py        # /tasks CRUD
│       ├── analysis.py     # /analysis 查询
│       └── keywords.py     # /scrape/trigger + /keywords/suggest
│
├── scraper/                # 爬虫层
│   ├── ozon_scraper.py     # Playwright 异步爬虫（双模式）
│   └── proxy_manager.py    # 代理配置与重试管理
│
├── analyzer/               # AI 分析层
│   ├── claude_client.py    # Anthropic SDK 调用封装
│   └── prompts.py          # 所有 Prompt 模板（常量）
│
├── scheduler/              # 定时任务层
│   └── tasks.py            # APScheduler 配置与任务函数
│
└── frontend/               # Vue3 前端
    ├── vite.config.js      # Vite 配置（含代理）
    ├── src/
    │   ├── main.js         # 应用入口（Element Plus 注册）
    │   ├── App.vue         # 根组件（侧边栏布局）
    │   ├── router/index.js # 路由配置
    │   ├── api/index.js    # Axios 封装（统一 baseURL + 拦截器）
    │   ├── views/          # 页面组件
    │   └── components/     # 可复用组件
    └── package.json
```

---

## 核心数据流

## 代理配置说明

- `PROXY_ENABLED=true` 开启代理。
- `PROXY_TYPE` 支持：`http` / `https` / `socks5`。
- `PROXY_HOST`、`PROXY_PORT` 为必填（开启代理时）。
- `PROXY_USER`、`PROXY_PASS` 按需填写（鉴权代理时）。

### 完整任务生命周期

```
用户操作                 API 层                  数据层              外部服务
─────────              ─────────              ─────────           ─────────
POST /tasks       →    create KeywordTask     → MySQL(pending)
                        status=pending

POST /scrape/trigger →  后台任务启动           → MySQL(running)

                        OzonScraper.scrape()   → Playwright
                                               ← Ozon HTML/JSON
                        写入 ozon_products     → MySQL

                        analyze_products()                         → Claude API
                                                                   ← JSON 分析
                        写入 ozon_analysis     → MySQL(done)

GET /analysis/:id →    查询 ozon_analysis     ← MySQL
                  ←    返回完整报告
```

### 爬虫双模式降级流程

```
启动 Playwright Browser
        │
        ▼
注册 page.on("response") 拦截器
        │
        ▼
page.goto(ozon search URL)
        │
        ├─── 响应拦截成功？
        │    URL 含 api/composer 或 search
        │    Content-Type: application/json
        │         │
        │         ▼ YES
        │    _parse_api_response()
        │    解析 widgetStates / items
        │         │
        │         └──────────────────────────┐
        │                                    │
        ▼ NO（拦截为空或失败）                │
_scrape_with_css()                          │
  等待 [data-widget="searchResultsV2"]      │
  遍历子元素，提取各字段                      │
        │                                    │
        └────────────────────────────────────┘
                         │
                         ▼
                  写入 ozon_products
                         │
                    下一页 / 结束
```

### AI 分析数据流

```python
# 调用链路（同步 SDK，由 asyncio 后台任务调用）
products_list (list[dict])
    │
    ▼
json.dumps(products[:50])          # 最多 50 条，控制 Token 消耗
    │
    ▼
ANALYZE_PRODUCTS_USER.format(...)  # 填充 Prompt 模板
    │
    ▼
anthropic.Anthropic().messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=2000,
    system=ANALYZE_PRODUCTS_SYSTEM,
    messages=[{"role": "user", "content": user_prompt}]
)
    │
    ▼
_clean_json_response(raw_text)     # 去除 ```json ``` 标记
    │
    ▼
json.loads(cleaned)                # 解析 JSON，失败重试 1 次
    │
    ▼
OzonAnalysis 对象写入数据库
```

---

## 数据库设计

### 表关系

```
keyword_tasks (1)
    ├──< ozon_products (N)    task_id FK
    └──< ozon_analysis (N)    task_id FK
```

### 字段类型选择说明

| 字段 | 类型 | 原因 |
|------|------|------|
| `price` | DECIMAL(10,2) | 货币精度，避免浮点误差 |
| `rating` | DECIMAL(3,2) | 最大 9.99，精确表示 |
| `opportunity_score` | TINYINT | 1-10 范围，节省空间 |
| `price_analysis` | JSON | 结构灵活，避免过度范式化 |
| `gap_opportunities` | JSON | 数组结构，Claude 输出直存 |
| `keywords_recommend` | JSON | 同上 |
| `status` | ENUM | 限制合法值，索引效率高 |

### 迁移说明

当前使用 `Base.metadata.create_all` 自动建表（开发模式）。生产环境建议引入 Alembic：

```bash
pip install alembic
alembic init alembic
# 修改 alembic/env.py 引入 Base 和 db_url
alembic revision --autogenerate -m "init"
alembic upgrade head
```

---

## API 接口规范

### 统一响应格式

成功响应直接返回业务数据（无 `code/message` 包装）：

```json
// GET /tasks
[
  {
    "id": 1,
    "keyword_cn": "运动水壶",
    "keyword_ru": "спортивная бутылка",
    "status": "done",
    "created_at": "2026-03-28T10:00:00",
    "updated_at": "2026-03-28T10:05:30"
  }
]
```

错误响应遵循 FastAPI 默认格式：

```json
// 404
{"detail": "Task not found"}

// 422
{"detail": [{"loc": ["body", "keyword_cn"], "msg": "field required"}]}
```

### 新增路由方法

在 `api/routes/` 下创建新文件，在 `api/main.py` 注册：

```python
# api/routes/reports.py
from fastapi import APIRouter
router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("")
async def list_reports(): ...

# api/main.py
from api.routes.reports import router as reports_router
app.include_router(reports_router)
```

---

## 扩展指南

### 添加新的 AI 分析函数

**Step 1**：在 `analyzer/prompts.py` 添加 Prompt 常量

```python
MY_ANALYSIS_SYSTEM = "你是..."
MY_ANALYSIS_USER = "分析 {data}，输出 JSON：{schema}"
```

**Step 2**：在 `analyzer/claude_client.py` 添加函数

```python
async def my_analysis(data: dict) -> dict:
    user_prompt = MY_ANALYSIS_USER.format(data=json.dumps(data))
    return _parse_with_retry(MY_ANALYSIS_SYSTEM, user_prompt)
```

**Step 3**：在路由或调度器中调用即可。

### 替换爬虫目标站点

修改 `scraper/ozon_scraper.py` 中的：
- `OZON_SEARCH_URL`：目标搜索 URL
- `_handle_response`：拦截判断逻辑（`api/composer` 条件）
- `_parse_api_response`：JSON 解析逻辑（字段路径）
- `_scrape_with_css`：CSS 选择器（各字段的选择器）

### 添加新的定时任务

```python
# scheduler/tasks.py

def _my_weekly_job():
    logger.info("Weekly job triggered")
    _run_async(_my_async_function())

# 在 start_scheduler() 中注册：
_scheduler.add_job(
    _my_weekly_job,
    trigger=CronTrigger(day_of_week="mon", hour=9, minute=0),
    id="weekly_report",
    name="Weekly report every Monday 09:00",
    replace_existing=True,
)
```

### 接入更多 AI 模型

`analyzer/claude_client.py` 中的 `MODEL` 常量可直接替换为其他 Claude 模型：

```python
MODEL = "claude-opus-4-6"    # 更强能力
MODEL = "claude-haiku-4-5-20251001"  # 更快更便宜
```

若需接入 OpenAI / 其他 LLM，在 `_get_client()` 替换 SDK 客户端并适配消息格式即可。

---

## 前端开发规范

### API 调用规范

所有 HTTP 请求必须通过 `src/api/index.js` 的封装函数，禁止在组件内直接使用 `axios`：

```javascript
// 正确
import { getTasks, createTask } from '@/api/index.js'
const tasks = await getTasks()

// 禁止
import axios from 'axios'
const tasks = await axios.get('/tasks')  // ❌
```

### 组件开发规范

- 可复用的展示型组件放 `src/components/`
- 页面级组件（与路由对应）放 `src/views/`
- 组件使用 `<script setup>` + Composition API
- Props 必须定义类型和默认值

### 新增页面步骤

```javascript
// 1. 创建 src/views/MyPage.vue

// 2. 在 src/router/index.js 注册路由
{
  path: '/my-page',
  name: 'MyPage',
  component: () => import('@/views/MyPage.vue'),  // 懒加载
  meta: { title: '我的页面' }
}

// 3. 在 App.vue 侧边栏添加菜单项
<el-menu-item index="/my-page">
  <el-icon><MyIcon /></el-icon>
  <span>我的页面</span>
</el-menu-item>
```

---

## 调试指南

### 后端调试

**查看详细日志**

```bash
# 开启 debug 级别日志
uvicorn api.main:app --reload --log-level debug
```

**单独测试爬虫**（不依赖 HTTP 接口）

```python
# 在项目根目录执行
import asyncio
from api.database import AsyncSessionLocal, init_db
from scraper.ozon_scraper import OzonScraper

async def test():
    await init_db()
    async with AsyncSessionLocal() as db:
        scraper = OzonScraper()
        products = await scraper.scrape(
            task_id=999,
            keyword_ru="спортивная бутылка",
            db=db
        )
        print(f"抓取到 {len(products)} 个商品")
        for p in products[:3]:
            print(p.title, p.price)

asyncio.run(test())
```

**单独测试 Claude 分析**

```python
import asyncio
from analyzer.claude_client import suggest_keywords

async def test():
    result = await suggest_keywords(
        product_name_cn="运动水壶",
        attributes="500ml，不锈钢",
        target_user="健身爱好者",
        price_range="500-2000卢布"
    )
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))

asyncio.run(test())
```

**测试调度器（立即触发）**

```python
from scheduler.tasks import _hourly_job, _daily_job
_hourly_job()   # 立即执行一次 pending 任务处理
_daily_job()    # 立即执行一次 batch_rank
```

### 前端调试

```bash
# 开发模式（热更新）
cd frontend
npm run dev

# 查看 Vite 代理日志
# 在 vite.config.js 的 proxy 中添加：
# configure: (proxy) => { proxy.on('error', (err) => console.log(err)) }

# 构建并预览
npm run build
npm run preview
```

### 数据库调试

```sql
-- 查看所有任务
SELECT id, keyword_cn, keyword_ru, status, created_at FROM keyword_tasks ORDER BY id DESC;

-- 查看某任务的抓取商品
SELECT title, price, review_count, rating FROM ozon_products WHERE task_id = 1 LIMIT 10;

-- 查看分析结果
SELECT keyword_ru, competition_level, opportunity_score, action_conclusion
FROM ozon_analysis ORDER BY analyzed_at DESC;

-- 重置失败任务（允许重新抓取）
UPDATE keyword_tasks SET status = 'pending' WHERE id = 1;
```

---

## 性能注意事项

| 场景 | 建议 |
|------|------|
| 大批量任务并发 | 调度器串行处理，避免 Playwright 实例过多占用内存 |
| Claude API 费用 | 单次调用最多传入 50 条商品，`max_tokens=2000` |
| 数据库连接池 | `pool_size=10, max_overflow=20`，高并发场景可调大 |
| Playwright 内存 | 每次爬取后 `browser.close()`，避免泄漏 |
| 爬虫频率 | `SCRAPE_DELAY_MIN/MAX` 建议不低于 2s，过低易被封 |

---

## 依赖版本说明

| 包 | 版本 | 说明 |
|----|------|------|
| `fastapi` | 0.111.0 | 稳定版，支持 lifespan 上下文 |
| `sqlalchemy` | 2.0.30 | 2.x async API，与 1.x 不兼容 |
| `aiomysql` | 0.2.0 | SQLAlchemy async MySQL 驱动 |
| `playwright` | 1.44.0 | 固定版本，浏览器内核需对应安装 |
| `anthropic` | 0.28.0 | Claude API 官方 SDK |
| `apscheduler` | 3.10.4 | 3.x 版本，4.x API 有较大变化 |
| `pydantic-settings` | 2.3.1 | 配合 Pydantic v2 使用 |
