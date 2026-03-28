# 模块解析

逐文件详解每个模块的设计意图、核心逻辑和关键实现细节。

---

## config.py

**职责**：全局配置中心，统一管理所有环境变量。

```python
class Settings(BaseSettings):
    DB_HOST: str = "localhost"
    ANTHROPIC_API_KEY: str = ""
    PROXY_ENABLED: bool = False
    ...
```

**设计要点**：
- 继承 `pydantic_settings.BaseSettings`，自动从 `.env` 文件和系统环境变量读取，优先级：系统环境变量 > `.env` 文件 > 字段默认值。
- 提供 `db_url` 属性动态拼接 SQLAlchemy 连接串，避免字符串散落各处。
- 提供 `proxy_url` 属性，根据 `PROXY_ENABLED` 和认证信息自动构造完整代理 URL。
- 模块末尾单例化：`settings = Settings()`，全局 `from config import settings` 复用同一实例。

**类型转换**：`PROXY_ENABLED=false` 字符串被 Pydantic 自动转为 `bool(False)`，`DB_PORT=3306` 转为 `int`，无需手动转换。

---

## api/database.py

**职责**：数据库连接管理，提供异步引擎和会话工厂。

```python
engine = create_async_engine(settings.db_url, pool_size=10, max_overflow=20)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

**关键设计**：

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `expire_on_commit=False` | — | 提交后对象属性不失效，可继续访问而无需重新查询 |
| `pool_pre_ping=True` | — | 每次从连接池取连接前 ping 一次，自动处理断连 |
| `pool_recycle=3600` | — | 连接存活超过 1 小时自动重建，防止 MySQL 8h 超时断连 |

**`get_db` 依赖注入**：使用 `async with` 上下文管理器，异常时自动 rollback，确保每个请求结束后连接归还连接池。

**`init_db`**：在 `api/main.py` 的 lifespan 钩子中调用，服务启动时自动执行 `CREATE TABLE IF NOT EXISTS`。

---

## api/models.py

**职责**：定义 ORM 模型，映射数据库三张表。

### KeywordTask

```python
class KeywordTask(Base):
    __tablename__ = "keyword_tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(Enum("pending","running","done","failed"))
    products: Mapped[list["OzonProduct"]] = relationship(..., cascade="all, delete-orphan")
```

- `Mapped[T]` + `mapped_column()` 是 SQLAlchemy 2.0 的 typed mapping 语法，提供完整类型提示。
- `cascade="all, delete-orphan"`：删除任务时级联删除关联的商品和分析记录。
- `updated_at` 使用 `onupdate=func.now()` 在 Python 层设置，`server_onupdate=func.now()` 让数据库层也自动更新（两者配合确保两种更新路径都生效）。

### OzonProduct

```python
price: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=True)
rating: Mapped[float] = mapped_column(DECIMAL(3, 2), nullable=True)
```

`price` 和 `rating` 允许 `NULL`，因为爬虫解析时部分商品可能无法提取这两个字段。

### OzonAnalysis

```python
price_analysis: Mapped[dict] = mapped_column(JSON, nullable=True)
gap_opportunities: Mapped[list] = mapped_column(JSON, nullable=True)
keywords_recommend: Mapped[list] = mapped_column(JSON, nullable=True)
```

Claude 输出的结构化数据直接存为 JSON 列，保留完整嵌套结构，前端按需取用，避免过度范式化导致查询复杂。

---

## api/main.py

**职责**：FastAPI 应用入口，注册中间件、路由和生命周期钩子。

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()       # 建表
    start_scheduler()     # 启动 APScheduler
    yield
    stop_scheduler()      # 优雅停止调度器
```

**lifespan 替代旧版 `@app.on_event`**：FastAPI 0.93+ 推荐使用 `lifespan` 上下文管理器，`yield` 前为启动逻辑，`yield` 后为关闭逻辑，类型提示更清晰。

**CORS 配置**：`allow_origins=["*"]` 适合开发环境。生产环境应改为具体域名：

```python
allow_origins=["https://your-domain.com"]
```

---

## api/routes/tasks.py

**职责**：关键词任务的 CRUD 操作。

**路由设计**：
- `GET /tasks`：支持 `?status=pending` 查询参数筛选，`status=None` 时返回全部。
- `POST /tasks`：接受 Pydantic `TaskCreate` 模型校验请求体，字段缺失时自动返回 422。
- `DELETE /tasks/{id}`：先删除外键关联的 products 和 analysis 记录，再删除任务本身（MySQL 外键约束保护）。

**序列化处理**：SQLAlchemy ORM 对象不能直接返回（不可 JSON 序列化），路由层将 `datetime` 对象转为 `.isoformat()` 字符串，手动构造 dict 返回。

---

## api/routes/analysis.py

**职责**：分析结果的查询接口。

**`GET /analysis`**：支持按 `conclusion` 筛选（`?conclusion=入场`），返回所有分析结果，按时间倒序。

**`GET /analysis/{task_id}`**：同时返回 task 基本信息和其所有分析记录（一个任务可能多次分析，取全部历史）。

**`serialize_analysis` 辅助函数**：提取重复的序列化逻辑，两个路由复用，避免代码重复。

---

## api/routes/keywords.py

**职责**：爬虫触发和关键词建议两个功能接口。

### 触发爬取（`POST /scrape/trigger`）

```python
background_tasks.add_task(run_scrape_task, body.task_id)
return {"message": "Scrape triggered", "task_id": body.task_id}
```

使用 FastAPI 的 `BackgroundTasks` 异步后台执行，接口立即返回 200，不阻塞客户端。

**`run_scrape_task` 函数**是爬虫 + AI 分析的完整流水线：

```
更新 status=running
    → OzonScraper.scrape()    [Playwright 抓取，写 ozon_products]
    → analyze_products()      [Claude 分析，写 ozon_analysis]
    → 更新 status=done
异常 → 更新 status=failed
```

注意：此函数在 `AsyncSessionLocal` 上下文内执行，**不依赖** FastAPI 的 `get_db` 依赖注入（因为它是后台任务，不在请求上下文内）。

### 关键词建议（`GET /keywords/suggest`）

直接调用 `suggest_keywords()`，异常通过 `HTTPException(500)` 返回，错误信息透传给前端。

---

## scraper/proxy_manager.py

**职责**：管理代理 IP 配置，封装重试计数逻辑。

```python
def get_playwright_proxy(self) -> Optional[dict]:
    if not self.is_enabled():
        return None
    proxy = {"server": f"http://{settings.PROXY_HOST}:{settings.PROXY_PORT}"}
    if settings.PROXY_USER and settings.PROXY_PASS:
        proxy["username"] = settings.PROXY_USER
        proxy["password"] = settings.PROXY_PASS
    return proxy
```

返回 Playwright `BrowserType.launch()` 接受的代理字典格式，与爬虫层解耦。

**当前局限**：只支持单个固定代理，生产环境可扩展为代理池（维护 IP 列表，轮询或随机选取）：

```python
# 扩展示例
class ProxyManager:
    def __init__(self, proxy_list: list[str]):
        self._pool = proxy_list
        self._index = 0

    def next_proxy(self) -> str:
        proxy = self._pool[self._index % len(self._pool)]
        self._index += 1
        return proxy
```

---

## scraper/ozon_scraper.py

**职责**：异步 Playwright 爬虫，抓取 Ozon 搜索结果商品数据。

### 双模式抓取策略

**模式一：API 拦截（优先）**

```python
page.on("response", self._handle_response)
```

Ozon 是 SPA（单页应用），页面渲染依赖内部 API 调用。注册 response 事件监听器，过滤 `api/composer` 或 `search` 路径的 JSON 响应，从中提取结构化商品数据。

优点：数据干净（含全部字段），无需等待渲染，速度快。

**模式二：CSS 选择器（降级）**

当 API 拦截无数据时（页面结构变化、反爬拦截、非标准响应），等待 `[data-widget="searchResultsV2"]` 容器渲染，再通过 CSS 选择器逐元素提取。

优点：兼容性强；缺点：依赖 DOM 结构，Ozon 更新前端后需要维护选择器。

### 异常处理层级

```
OzonScraper.scrape()          ← 外部调用入口
    while can_retry():
        _do_scrape()
            ├── CaptchaError  → 向上抛出，不重试，由调用方标记 status=failed
            ├── BannedError   → 重试（切换代理），最多 3 次
            └── Exception     → 向上抛出
```

### 商品数据解析

`_extract_product_from_item` 对字段名做了多个候选路径的兼容：

```python
title = (
    item.get("name")         # 旧版 API
    or item.get("title")     # 通用字段
    or item.get("displayName")  # 新版 API
)
```

这是因为 Ozon 内部 API 不同接口（composer vs search）返回字段名不统一。

### URL 标准化

```python
if url and not url.startswith("http"):
    url = f"https://www.ozon.ru{url}"
```

API 响应中的 URL 常为相对路径（如 `/product/xxx`），需补全为完整 URL。

---

## analyzer/prompts.py

**职责**：集中管理所有 Prompt 模板，与业务逻辑解耦。

**设计原则**：

1. **System Prompt 定义角色和约束**，User Prompt 提供具体数据。这符合 Claude API 的最佳实践，角色设定在 system 层更稳定。

2. **强制 JSON 输出**：每个 system prompt 结尾均有"只返回 JSON"的指令，避免 Claude 输出解释文字导致 JSON 解析失败。

3. **内嵌 JSON Schema**：在 user prompt 中给出完整的输出 schema（含字段名和枚举值），大幅降低幻觉率和格式偏差。

4. **使用 Python 字符串模板而非 f-string**：使用 `.format()` 延迟填充，Prompt 常量在模块加载时不会因缺少变量而报错。

**`ANALYZE_PRODUCTS_USER` 中的双括号转义**：

```python
# Prompt 中的 JSON 示例用 {{ }} 转义，避免 .format() 误解析
"输出 JSON schema：{{ competition_level, ... }}"
```

---

## analyzer/claude_client.py

**职责**：封装 Anthropic SDK 调用，提供 4 个语义化分析函数。

### 同步 SDK + 异步函数的设计选择

`anthropic.Anthropic()` 是同步客户端，但 4 个函数声明为 `async`：

```python
async def analyze_products(...):
    ...
    data = _parse_with_retry(SYSTEM, user_prompt)  # 同步调用
    analysis = OzonAnalysis(...)
    db.add(analysis)
    await db.commit()  # 异步 DB 操作
```

这是合理的：函数本身需要 `await db.commit()`（异步操作），而 Claude API 调用是一次性同步 HTTP 请求，耗时约 2-10 秒但不阻塞事件循环（由于在 `BackgroundTasks` 线程中执行）。

如需完全非阻塞，可改用 `anthropic.AsyncAnthropic()` 并 `await client.messages.create(...)`。

### `_clean_json_response` 逻辑

```python
def _clean_json_response(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]                          # 去掉 ```json 行
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]                     # 去掉结尾 ``` 行
        text = "\n".join(lines).strip()
    return text
```

即使 prompt 明确要求"不含 markdown 代码块"，Claude 有时仍会输出 ` ```json`。此函数作为防御层处理这种情况。

### `_parse_with_retry` 重试逻辑

```python
for attempt in range(2):
    raw = _call_claude(system, user)
    cleaned = _clean_json_response(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        if attempt == 1:
            raise RuntimeError(...)
```

第一次失败后重试一次（重新调用 Claude），两次均失败则抛出 `RuntimeError` 由调用方处理（通常导致 `status=failed`）。

### `analyze_products` 的 DB 操作

此函数既调用 Claude API（IO 密集型）又写数据库，通过参数传入 `db: AsyncSession`，保持与调用方同一事务上下文，一次 `commit()` 完成。

---

## scheduler/tasks.py

**职责**：APScheduler 定时任务配置和执行。

### 同步调度器执行异步任务

APScheduler 3.x 的 `BackgroundScheduler` 在独立线程中执行 Job，无法直接 `await`。解决方案：

```python
def _run_async(coro):
    loop = asyncio.new_event_loop()   # 为当前线程创建新的事件循环
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
```

每次 Job 触发时创建独立事件循环执行协程，结束后关闭。这是 APScheduler 3.x + asyncio 的标准做法。

### 每小时任务：串行处理

```python
async def _process_pending_tasks():
    # 先查出所有 task_id
    async with AsyncSessionLocal() as db:
        tasks = await db.execute(select(KeywordTask).where(status == "pending"))
        task_ids = [t.id for t in tasks.scalars().all()]

    # 串行处理，避免多 Playwright 实例并发
    for task_id in task_ids:
        await run_scrape_task(task_id)
```

串行而非并发：Playwright 浏览器实例内存占用大（约 100-200MB/实例），串行处理可控制资源消耗。

### 每日 02:00 任务：batch_rank

```python
async def _daily_batch_rank():
    today = date.today()
    # 查询今天 done 的任务
    tasks = await db.execute(
        select(KeywordTask).where(
            and_(status == "done", func.date(updated_at) == today)
        )
    )
    # 构建 summaries，调用 Claude batch_rank
    ranked = await batch_rank(summaries)
    logger.info(f"Top pick: {ranked.get('top_pick')}")
```

batch_rank 结果目前仅写入日志。可扩展为写入新表或发送 Webhook 通知。

---

## frontend/src/api/index.js

**职责**：统一封装 Axios，提供语义化 API 调用函数。

### 拦截器设计

```javascript
http.interceptors.response.use(
    (response) => response.data,          // 自动解包 .data，调用方直接拿到业务数据
    (error) => {
        const msg = error.response?.data?.detail || error.message || '请求失败'
        ElMessage.error(msg)              // 全局错误提示
        return Promise.reject(error)      // 继续向上传播，调用方可 catch
    }
)
```

成功时解包 `response.data`，调用方无需每次写 `.data`：

```javascript
// 调用方
const tasks = await getTasks()   // 直接是数组，不是 { data: [...] }
```

### baseURL 来源

```javascript
const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
```

Vite 在构建时将 `import.meta.env.VITE_*` 变量内联到 bundle 中，开发和生产环境通过不同的 `.env` 文件控制。

---

## frontend/src/components/

### CompetitionBadge.vue

```vue
const tagType = computed(() => {
    switch (props.level) {
        case '低': return 'success'   // 绿色
        case '中': return 'warning'   // 黄色
        case '高': return 'danger'    // 红色
    }
})
```

纯展示组件，只接受 `level` prop，使用 Element Plus `el-tag` 的 `type` 属性控制颜色。`computed` 而非 `methods` 确保值有缓存，重复渲染不重复计算。

### OpportunityScoreCard.vue

```vue
const percentage = computed(() => (props.score || 0) * 10)  // 1-10 → 10-100%
```

将 1-10 分映射到 `el-progress` 的 0-100% 范围。颜色根据分值动态变化：≥8 绿、≥5 黄、否则红，与竞争强度的语义一致。

### KeywordTable.vue

```vue
<el-table-column label="难度" v-if="showDifficulty" />
<el-table-column label="复制" v-if="showCopy" />
```

通过 `showDifficulty` 和 `showCopy` prop 控制可选列的显示，同一组件在 `AnalysisDetail`（不显示复制）和 `KwTool`（显示复制）中复用。

---

## frontend/src/views/

### Dashboard.vue

**统计卡片**使用 `computed` 从 `analysisList` 和 `allTasks` 实时计算，无需额外 API 请求：

```javascript
const statCards = computed(() => {
    const total = allTasks.value.length
    const avg = scores.reduce((a,b) => a+b, 0) / scores.length
    ...
})
```

**行点击跳转**：`@row-click="onRowClick"` + `router.push()`，配合 CSS `cursor: pointer` 给用户可点击的视觉反馈。

### Keywords.vue

**防重复触发**：`scrapingIds`（`ref(new Set())`）记录正在触发的 task_id，触发期间禁用按钮，请求完成后移除。

```javascript
scrapingIds.value.add(row.id)
try {
    await triggerScrape(row.id)
} finally {
    scrapingIds.value.delete(row.id)  // 成功或失败都要移除
}
```

### AnalysisDetail.vue

**缺口时间轴**用 `el-timeline` 组件展示，`entry_difficulty` 映射到 `type` 属性（`success/warning/danger`），颜色与 badge 语义统一。

**价格带四象限**：`min/max` 数值格式化为本地化货币，`sweet_spot/weak_zone` 直接展示 Claude 输出的描述性文字。

### KwTool.vue

**复制全部**使用 `navigator.clipboard.writeText()`（现代浏览器标准 API），降级用 `ElMessage.error` 提示手动复制，不使用 `document.execCommand`（已废弃）。

---

## 跨模块交互总结

```
config.py
  └─ 被所有模块导入（settings 单例）

api/database.py
  ├─ Base ← api/models.py
  ├─ get_db ← api/routes/*.py (依赖注入)
  ├─ AsyncSessionLocal ← api/routes/keywords.py (后台任务)
  └─ AsyncSessionLocal ← scheduler/tasks.py

api/models.py
  ├─ KeywordTask ← api/routes/tasks.py
  ├─ OzonProduct ← scraper/ozon_scraper.py
  └─ OzonAnalysis ← analyzer/claude_client.py

scraper/ozon_scraper.py
  └─ ProxyManager ← scraper/proxy_manager.py

analyzer/claude_client.py
  └─ prompts.py (常量导入)

api/routes/keywords.py
  ├─ OzonScraper ← scraper/ozon_scraper.py
  └─ analyze_products ← analyzer/claude_client.py

scheduler/tasks.py
  ├─ run_scrape_task ← api/routes/keywords.py
  └─ batch_rank ← analyzer/claude_client.py

api/main.py
  ├─ tasks_router, analysis_router, keywords_router
  ├─ init_db ← api/database.py
  └─ start_scheduler / stop_scheduler ← scheduler/tasks.py
```
