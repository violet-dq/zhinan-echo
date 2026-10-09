# 🌸 知南 · Echo —— 学习 DDL 与资料管理智能体

> **知南而行，必有回响。**

一个以**对话为核心入口**的学习管理智能体 Web 应用：学生通过自然语言完成资料整理、DDL 录入、语义检索、复习规划等全部操作；智能体听得懂、办得到、会主动提醒。

<p align="center">
  <img src="frontend/public/logo.png" width="120" height="120" alt="知南·Echo Logo" style="border-radius: 50%;"/>
</p>

---

## ✨ 核心能力

| 模块 | 能力 | 说明 |
|------|------|------|
| 🤖 智能体对话 | LangGraph 工具调用 | LLM 原生 function calling 自动决策调用哪个工具；无 API Key 时降级为规则模式 |
| 📚 资料索引 | 多格式解析 + 在线预览 | PDF (pdf.js) / Word (mammoth.js) / PPT / 图片；支持上传、预览、下载、删除 |
| 🔍 语义检索 (RAG) | 双路召回 + 引用溯源 | 向量检索 (BGE-M3) + BM25 关键词检索，RRF 融合重排，带 `[编号]` 引用 |
| ⏰ DDL 规划 | 四种录入 + 看板 | 对话 / 截图 OCR / 粘贴文本 / 手动；列表视图 + 优先级矩阵；.ics 日历导出 |
| 📈 复习规划 | 知识树 + 智能排期 | 自动提取知识树，按遗忘曲线排期，任务完成后自动重排；Markdown 导出 |
| 🎨 主题系统 | 5 套主题切换 | 二月兰（默认）/ 纯白 / 深黑 / 夏季暖阳 / 冬季雪花 |
| ⚙️ 系统设置 | per-user 配置 | 皮肤切换、下载路径、通知偏好、LLM API Key（每用户独立 LLM 配置） |
| 👤 用户中心 | 资料管理 | 头像、昵称、密码修改、退出登录 |

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────┐
│  前端 Vue 3 + TypeScript + Vite + Element Plus   │
│  二月兰主题 · 5 套皮肤 · 对话气泡 + 结构化卡片    │
│  mammoth.js (Word预览) · pdf.js (PDF预览)        │
└──────────────────────┬──────────────────────────┘
                       │ HTTP/JSON (JWT Auth)
┌──────────────────────▼──────────────────────────┐
│  后端 FastAPI (Python 3.12+)                     │
│  ┌─────────────────────────────────────────────┐│
│  │ 智能体层 LangGraph                           ││
│  │ load_context → llm_decision ↔ tool_node → END││
│  │ bind_tools() 原生 function calling           ││
│  └─────────────────────────────────────────────┘│
│  检索：向量(余弦) + BM25 双路召回 + RRF 重排      │
│  解析：PyMuPDF / python-docx / python-pptx       │
│  提醒：asyncio 后台扫描（7天/3天/1天/1小时分档）  │
└──────┬───────────────────────┬──────────────────┘
       │                       │
  SQLite/PostgreSQL        本地向量库 (按用户隔离)
  (零配置 / 一键切PG)     (可无缝切换 Milvus/Qdrant)
```

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **前端框架** | Vue 3 + TypeScript | Composition API，响应式组件 |
| **UI 库** | Element Plus | 大圆角 + 玻璃态设计 |
| **构建工具** | Vite | 快速 HMR 开发体验 |
| **后端框架** | FastAPI | 异步 Python Web 框架 |
| **智能体** | LangGraph + LangChain | StateGraph 编排，bind_tools 原生 tool calling |
| **LLM** | DeepSeek (OpenAI 兼容协议) | 支持 per-user API Key 覆盖 |
| **Embedding** | BGE-M3 (SiliconFlow) | 1024 维，中英双语 |
| **数据库** | SQLite / PostgreSQL | 零配置 SQLite，可一键切 PG |
| **向量库** | 本地轻量向量库 | 按用户隔离，JSON + 余弦检索 |
| **文件预览** | pdf.js + mammoth.js | 浏览器端渲染，不依赖浏览器插件 |
| **认证** | JWT | 无状态认证，Token Bearer |

## 🚀 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+
- npm 9+

### 1. 后端

```bash
cd backend
pip install -r requirements.txt

# 配置 LLM / Embedding（可选，不配也能跑，自动降级规则模式）
cp .env.example .env
# 编辑 .env 填入：
#   LLM_API_KEY=sk-xxx        (DeepSeek API Key)
#   EMBEDDING_API_KEY=sk-xxx  (SiliconFlow API Key)

python run.py    # 启动于 http://127.0.0.1:8000
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev      # 开发模式 http://localhost:5173（/api 代理到 8000）
```

### 3. 一体化部署（后端托管前端）

```bash
cd frontend && npm run build        # 构建前端到 dist/
cd ../backend && python run.py      # 后端直接托管前端
# 访问 http://127.0.0.1:8000
```

### 4. 公网暴露（可选）

```bash
# Cloudflare Tunnel（免费，无需注册）
cloudflared tunnel --url http://localhost:8000
# 得到 https://xxx.trycloudflare.com 公网地址
```

## 🐳 Docker 部署

```bash
cp backend/.env.example backend/.env   # 按需填写
docker compose up -d --build
# 访问 http://服务器IP/
```

推荐配置：2 核 4G 起步（启用 OCR 建议 4 核 8G）。

## 🔑 配置说明

### `.env` 配置项

| 变量 | 说明 | 默认值 | 必填 |
|------|------|--------|------|
| `LLM_API_KEY` | DeepSeek API Key | 空（降级规则模式） | 否 |
| `LLM_API_BASE` | LLM API 地址 | `https://api.deepseek.com/v1` | 否 |
| `LLM_MODEL` | 模型名 | `deepseek-chat` | 否 |
| `EMBEDDING_API_KEY` | Embedding API Key | 空（降级 n-gram） | 否 |
| `EMBEDDING_API_BASE` | Embedding API 地址 | `https://api.siliconflow.cn/v1` | 否 |
| `EMBEDDING_MODEL` | Embedding 模型 | `BAAI/bge-m3` | 否 |
| `DATABASE_URL` | 数据库连接 | `sqlite:///./data/zhinan.db` | 否 |
| `JWT_SECRET` | JWT 密钥 | 开发默认值 | 生产必改 |
| `SMTP_HOST` | 邮件服务器 | 空（不发邮件） | 否 |

### Per-User LLM 配置

每个用户可在「系统设置 → 智能化」中填写自己的 LLM API Key / Base / Model，覆盖系统默认配置。

## 🎭 主题系统

| 主题 | 代号 | 风格 |
|------|------|------|
| 二月兰 | `echo` | 深紫渐变侧边栏 + 紫色花瓣背景 |
| 纯白 | `light` | 纯白简洁 + 浅灰侧边栏 |
| 深黑 | `dark` | 深紫黑 + 暗色组件适配 |
| 夏季暖阳 | `summer` | 暖橙渐变 + 太阳背景图 |
| 冬季雪花 | `winter` | 冰蓝渐变 + 雪花背景图 |

## 📁 项目结构

```
zhinan-echo/
├── backend/
│   ├── app/
│   │   ├── agent/          # LangGraph 智能体
│   │   │   ├── graph.py    # 主图：llm_decision ↔ tool_node 循环
│   │   │   ├── tool_defs.py # 工具定义 + system prompt
│   │   │   ├── tools.py    # 工具实现（DDL/RAG/文件/复习）
│   │   │   └── state.py    # AgentState 状态定义
│   │   ├── routers/        # API 路由
│   │   │   ├── auth.py     # 登录/注册/JWT
│   │   │   ├── chat.py     # 对话入口 + 会话历史
│   │   │   ├── files.py    # 文件上传/预览/下载/删除
│   │   │   ├── ddl.py      # DDL CRUD + OCR
│   │   │   ├── review.py   # 复习计划 CRUD
│   │   │   ├── export.py   # 导出 (.ics / CSV / Markdown)
│   │   │   ├── user.py     # 用户资料/密码/设置
│   │   │   └── misc.py     # 仪表盘/通知/课程
│   │   ├── services/       # 业务服务
│   │   │   ├── llm.py      # LLM 调用 (per-user 覆盖)
│   │   │   ├── embedder.py # Embedding 服务
│   │   │   ├── retrieval.py # RAG 双路召回
│   │   │   ├── parser.py   # 文件解析
│   │   │   ├── review.py   # 复习排期算法
│   │   │   ├── reminders.py # 提醒服务
│   │   │   └── exporter.py # 导出服务
│   │   ├── config.py       # 全局配置
│   │   ├── models.py       # 数据模型
│   │   ├── schemas.py      # Pydantic 模型
│   │   ├── security.py     # JWT 认证
│   │   └── main.py         # FastAPI 入口
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/     # Vue 组件
│   │   │   ├── ChatPanel.vue      # 对话面板
│   │   │   ├── LibraryView.vue    # 资料索引
│   │   │   ├── DdlBoard.vue       # DDL 看板
│   │   │   ├── ReviewView.vue     # 复习计划
│   │   │   ├── DashboardView.vue  # 首页仪表盘
│   │   │   ├── SettingsView.vue   # 系统设置
│   │   │   ├── UserProfile.vue    # 用户信息
│   │   │   ├── EchoLogo.vue       # Logo 组件
│   │   │   └── MessageCards.vue   # 消息卡片
│   │   ├── views/
│   │   │   ├── MainView.vue       # 主布局 + 侧边栏
│   │   │   └── LoginView.vue      # 登录 + 介绍页
│   │   ├── api.ts         # API 封装
│   │   └── style.css      # 主题系统 CSS 变量
│   ├── public/            # 静态资源（Logo/背景图）
│   └── index.html
├── deploy/                # 部署配置
├── docker-compose.yml
└── README.md
```

## 🧪 测试账号

| 账号 | 密码 | 场景 |
|------|------|------|
| `demo1` | `echo123456` | 完整演示库 |
| `demo2` | `echo123456` | 部分课程 |
| `demo3` | `echo123456` | 空白新用户 |

首次启动自动初始化种子数据。

## 💬 对话示例

```
用户：下周有哪些DDL？
Echo：共 2 项待办，按时间排序：· 操作系统 实验3 …（附清单卡片）

用户：帮我记一下，算法作业 8月20号晚上10点截止
Echo：已记录 ✅「算法作业」截止：08月20日 22:00（6天后）

用户：二叉树有哪些遍历方式？
Echo：（检索资料，给出带 [1][2] 来源引用的回答）

用户：我8月30号考数据结构，帮我生成复习计划
Echo：「数据结构」复习计划已生成 ✅ 17 个知识点 / 9 天排期

用户：我想上传课件
Echo：（弹出文件选择器，上传后自动解析入库）
```

## ❓ FAQ

**Q：没有 LLM API Key 能用吗？**
可以。系统自动降级为规则模式：意图识别走关键词，RAG 直接返回最相关片段，复习计划用章节结构建知识树。

**Q：OCR 识别截图 DDL 失败？**
安装 OCR 引擎：`pip install paddleocr paddlepaddle`（约 1GB）。不安装不影响其他功能。

**Q：如何切换 PostgreSQL？**
`.env` 中设置 `DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/echo`，`pip install psycopg2-binary`。

**Q：其他电脑无法访问？**
1. 服务器绑定 `0.0.0.0`（非 `127.0.0.1`）
2. 放行防火墙 8000 端口
3. 公共 WiFi（如 CMCC）有客户端隔离，用 Cloudflare Tunnel 穿透

## 📄 开源协议

[MIT License](LICENSE) - 自由使用、修改、分发。

## 📜 合规说明

- 演示资料为模拟课程内容，不涉及真实课程版权
- 用户数据按账号隔离，仅本人可见
- LLM 调用仅发送文档片段，不含账号信息

---

<p align="center">
  知南而行 · 必有回响 🌸
</p>
