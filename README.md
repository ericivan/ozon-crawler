# Ozon 电商选品分析系统

基于 Playwright 爬虫 + Claude AI 的 Ozon 俄罗斯电商选品分析工具，帮助卖家快速评估市场竞争态势、发现价格缺口、生成俄语关键词并给出入场建议。

---

## 功能概览

| 功能 | 说明 |
|------|------|
| 关键词任务管理 | 创建、删除、触发抓取任务 |
| Ozon 商品抓取 | Playwright 异步爬虫，支持 API 拦截 + CSS 降级 + 代理切换 |
| AI 竞争分析 | Claude 分析竞争强度、价格带、缺口机会、入场建议 |
| 俄语关键词生成 | AI 生成符合俄罗斯用户搜索习惯的关键词 |
| 横向批量排名 | 多关键词综合评分对比，输出周度选品洞察 |
| 定时自动化 | 每小时自动处理待抓取任务，每天 02:00 执行批量排名 |
| 可视化看板 | Vue3 前端展示统计卡片、分析报告、关键词对照表 |

---

## 系统要求

| 依赖 | 版本要求 |
|------|---------|
| Python | 3.11+ |
| Node.js | 18+ |
| MySQL | 8.0+ |
| Anthropic API Key | 有效的 claude-sonnet-4-20250514 访问权限 |

---

## 快速开始

### 1. 克隆项目

```bash
git clone <repo-url>
cd ozon-crawler
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，填写必填项：

```ini
# 数据库（必填）
DB_HOST=localhost
DB_PORT=3306
DB_NAME=ozon_analyzer
DB_USER=root
DB_PASS=your_password

# Anthropic API（必填）
ANTHROPIC_API_KEY=sk-ant-api03-...

# 代理（可选，默认关闭）
PROXY_ENABLED=false

# 爬虫参数（可选，有默认值）
SCRAPE_DELAY_MIN=2
SCRAPE_DELAY_MAX=5
SCRAPE_MAX_PAGES=3
```

### 3. 创建数据库

```sql
CREATE DATABASE ozon_analyzer CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

> 表结构由 SQLAlchemy 在首次启动时自动创建，无需手动执行 DDL。

### 4. 安装后端依赖

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium         # 安装 Chromium 浏览器内核
```

### 5. 启动后端服务

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

服务启动后访问 API 文档：
- Swagger UI：http://localhost:8000/docs
- ReDoc：http://localhost:8000/redoc

### 6. 安装前端依赖并启动

```bash
cd frontend
cp .env.example .env          # 默认指向 http://localhost:8000
npm install
npm run dev
```

前端默认运行在 http://localhost:5173

---

## 使用流程

### 方式一：手动操作（推荐新手）

```
1. 打开 http://localhost:5173/keywords
2. 在表单中输入关键词（中文 + 俄语），点击「添加任务」
3. 在任务列表中点击「触发抓取」
4. 等待状态变为「已完成」（约 1-3 分钟）
5. 跳转至 /dashboard 查看分析结果
6. 点击表格行查看完整分析报告
```

### 方式二：定时自动化

任务创建后状态为 `pending`，后台调度器每小时自动触发抓取和分析，无需手动干预。

### 方式三：API 直接调用

```bash
# 创建任务
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"keyword_cn": "运动水壶", "keyword_ru": "спортивная бутылка для воды"}'

# 手动触发抓取
curl -X POST http://localhost:8000/scrape/trigger \
  -H "Content-Type: application/json" \
  -d '{"task_id": 1}'

# 查看分析结果
curl http://localhost:8000/analysis/1

# 生成俄语关键词
curl "http://localhost:8000/keywords/suggest?product_name_cn=运动水壶&attributes=500ml,不锈钢&target_user=健身人群&price_range=500-1500卢布"
```

---

## 前端页面说明

### /dashboard — 选品总览

顶部 4 个统计卡片（总任务数 / 已分析数 / 入场建议数 / 平均机会分），下方为所有分析结果列表。可按入场建议（入场/观望/放弃）筛选，点击任意行跳转详情。

### /keywords — 关键词管理

添加新任务、查看所有任务的状态（待处理/进行中/已完成/失败），支持手动触发抓取和删除任务。

### /analysis/:id — 分析详情

单个关键词的完整分析报告：
- 综合摘要
- 竞争强度 + 机会评分仪表盘
- 价格带四象限（最低价/最高价/主流区间/薄弱区间）
- 缺口机会时间轴（按入场难度标色）
- 推荐关键词对照表（俄中对照）
- 入场建议（入场/观望/放弃 + 原因 + 下一步）

### /kw-tool — 关键词工具

输入产品信息，AI 生成 10 个俄语关键词（3 核心词 + 4 长尾词 + 3 场景词），支持单条复制和一键复制全部。

---

## 代理配置

当目标网站限制国内 IP 访问时，启用代理：

```ini
PROXY_ENABLED=true
PROXY_HOST=192.168.1.100
PROXY_PORT=7890
PROXY_USER=username      # 可留空（无需认证时）
PROXY_PASS=password      # 可留空
```

系统在 IP 被封禁时自动切换代理，最多重试 3 次。

---

## 任务状态说明

| 状态 | 含义 |
|------|------|
| `pending` | 已创建，等待调度器或手动触发 |
| `running` | 爬虫正在运行 |
| `done` | 爬取完成，AI 分析已写入数据库 |
| `failed` | 爬取失败（验证码/IP 封禁/网络异常） |

失败的任务可以重新点击「触发抓取」重试。

---

## 生产部署

### 后端（使用 Gunicorn）

```bash
pip install gunicorn
gunicorn api.main:app -w 4 -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 --timeout 120
```

### 前端（构建静态文件）

```bash
cd frontend
npm run build
# dist/ 目录即为静态文件，部署至 Nginx 或 CDN
```

### Nginx 反向代理示例

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        root /var/www/ozon-analyzer/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 常见问题

**Q: 爬虫报 "Captcha detected"，任务变成 failed？**

Ozon 检测到自动化访问，触发验证码。建议：
1. 启用真实代理
2. 增大延迟：`SCRAPE_DELAY_MIN=5 SCRAPE_DELAY_MAX=10`
3. 减少翻页：`SCRAPE_MAX_PAGES=1`

**Q: Claude API 调用超时？**

检查 `ANTHROPIC_API_KEY` 是否有效，并确认账户有 `claude-sonnet-4-20250514` 访问权限。

**Q: 数据库连接失败？**

确认 MySQL 已启动，`.env` 中的 `DB_HOST/DB_USER/DB_PASS` 正确，并已创建 `ozon_analyzer` 数据库。

**Q: 前端显示"请求失败"？**

检查 `frontend/.env` 中 `VITE_API_BASE_URL` 是否指向正确的后端地址，并确认 CORS 允许前端域名。
