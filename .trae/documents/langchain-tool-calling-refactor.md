# 对话助教 LangChain Tool Calling 重构方案

## Context（背景与目标）

**问题根因**：
- 当前 `.env` 中 `LLM_API_KEY` 为空 → `llm_enabled=False` → 所有 LLM 调用返回 None → 完全依赖 `RULE_KEYWORDS` 正则规则匹配意图
- 正则规则太死板，必须匹配特定句式（如"帮我记一下"才能触发 ddl_add），用户用任意自然语言表达时要么不命中要么被误判
- 现有架构已是 LangGraph（LangChain 生态的图框架），但意图识别层用正则优先 + LLM 兜底（兜底失效）

**目标**：
用 LangChain 原生 Tool Calling（function calling）替代正则规则，让 LLM 自动识别任意自然语言并调用对应工具完成 DDL 添加、文件上传、复习规划等任务。

**用户确认的关键决策**：
1. 改用 DeepSeek 作为 LLM 提供方（用户自行填 API Key 到 .env）
2. 文件上传两种方式都支持：① 对话返回上传引导卡片（用户拖拽）② 用户在对话里贴本地文件绝对路径，后端读取入库

---

## 架构选择

**保留 LangGraph 作为编排框架** + **用 LangChain Tool Calling 替代正则意图识别**。

理由：
- LangGraph 是 LangChain 生态的图编排框架，比传统 `AgentExecutor` 更现代、可控
- 现有图结构（load_context → intent → route → 各 handler 节点）已成熟，改动量最小
- `ChatOpenAI.bind_tools()` + `ToolNode` 能让 LLM 原生 function calling 决定调哪个工具，彻底摆脱正则

**新流程**：
```
load_context → llm_decision → [has_tool_calls] → tool_node → llm_decision (循环)
                            → [no_tool_calls]  → END (直接回复)
```
无 API Key 时降级走旧正则分支（保留 `classify_intent` + 旧节点作为 fallback）。

---

## 实施步骤

### 1. 依赖与配置

**修改 `requirements.txt`**：新增
```
langchain-core>=0.2
langchain-openai>=0.1
```

**修改 `app/config.py`** L10-L14：改回 DeepSeek 默认
```python
llm_api_base: str = "https://api.deepseek.com/v1"
llm_model: str = "deepseek-chat"
llm_fast_model: str = "deepseek-chat"  # DeepSeek 无轻量模型，主模型即可
```

**`.env`**：用户自行填 `LLM_API_KEY=sk-xxx`（实施后提示）

### 2. LLM 服务：新增 LangChain ChatOpenAI 工厂

**修改 `app/services/llm.py`**：新增 `get_chat_model()` 函数
```python
def get_chat_model(temperature=0.3, model=None) -> "ChatOpenAI":
    """返回 LangChain ChatOpenAI 实例（指向 DeepSeek，兼容 OpenAI function calling 协议）。"""
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=model or settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_api_base,
        temperature=temperature,
        max_tokens=settings.llm_max_tokens,
    )
```
保留现有 `LLMService` 类（旧 handler 仍用 `llm.chat` / `llm.chat_json`）。

### 3. 工具定义层（新增文件）

**新建 `app/agent/tool_defs.py`**：用 `@tool` 装饰器把现有 handler 包装成 LangChain 工具。

工具清单（复用 `agent/tools.py` 现有函数，不重写业务逻辑）：

| 工具名 | 入参 | 复用的现有函数 | 说明 |
|---|---|---|---|
| `add_ddl` | title, due_at, course?, priority? | `tools.handle_ddl_add` | 添加 DDL 截止任务 |
| `query_ddls` | time_range?, course? | `tools.handle_ddl_query` | 查询今日/本周/下周待办 |
| `complete_ddl` | task_keyword | `tools.handle_ddl_done` | 标记任务完成 |
| `search_materials` | query, course? | `tools.handle_rag` | RAG 检索资料问答 |
| `list_files` | course? | `tools.handle_file_query` / `handle_file_organize` | 查询资料库 |
| `create_review_plan` | course, exam_date | `tools.handle_review_plan` | 生成复习计划 |
| `query_review_progress` | (无) | `tools.handle_review_query` | 查询复习进度 |
| `export_data` | format? | `tools.handle_export` | 导出引导 |
| `upload_file_guide` | course? | 新增，返回上传引导卡片 | 用户拖拽上传 |
| `ingest_file_by_path` | file_path, course? | 调用 `ingest_file` 服务 | 读取本地路径入库 |

每个工具的 docstring 写清楚"何时调用此工具"，让 LLM 准确识别。例：
```python
@tool
def add_ddl(title: str, due_at: str, course: str = "", priority: str = "medium") -> dict:
    """当用户想记录、添加、登记截止任务/作业/考试/DDL时调用。
    title: 简洁任务名；due_at: YYYY-MM-DD HH:MM；course: 课程名（可选）；priority: high/medium/low。
    例：用户说"算法第3章作业 8月20号晚上10点 截止"→ 调用此工具。"""
    # 委托给 tools.handle_ddl_add，需要 db/user 上下文 → 通过闭包注入
```

**db/user 注入策略**：工具需要 `db: Session` 和 `user: User`，但 `@tool` 装饰器要求函数签名纯净。用**工厂函数**在每次请求时动态构建工具列表，闭包捕获 db/user：
```python
def build_tools(db: Session, user: User) -> list:
    @tool
    def add_ddl(title: str, due_at: str, ...):
        return tools.handle_ddl_add(db, user, f"{title} {due_at}", {"title": title, "due_at": due_at, ...})
    # ... 其他工具
    return [add_ddl, query_ddls, complete_ddl, ...]
```

### 4. Agent 图重构

**修改 `app/agent/graph.py`**：
- 保留 `load_context` 节点
- **新增 `llm_decision` 节点**：用 `get_chat_model().bind_tools(tools)` + 系统提示词，让 LLM 决定调用工具或直接回复
- **新增 `tool_node`**：用 `langgraph.prebuilt.ToolNode` 执行工具调用
- **条件路由**：LLM 输出含 `tool_calls` → 走 `tool_node` → 回到 `llm_decision` 生成最终回复；无 `tool_calls` → END
- **降级分支**：`llm_enabled=False` 时，走旧 `intent_node` + 正则路由 + 旧 handler 节点（保留现有逻辑作 fallback）
- **工具结果回传**：ToolNode 执行后，工具返回的 `{"reply": ..., "cards": [...]}` 注入回 LLM 上下文，让 LLM 生成自然语言总结回复给用户

新图结构：
```python
builder.add_node("load_context", load_context)
builder.add_node("llm_decision", llm_decision_node)   # 新
builder.add_node("tool_node", ToolNode(tools))         # 新
# 旧节点保留作 fallback：intent, ddl, rag, file, review, export, smalltalk
builder.add_edge(START, "load_context")
# load_context 后根据 llm_enabled 分流
builder.add_conditional_edges("load_context",
    lambda s: "llm_decision" if llm.enabled else "intent")
# LLM 模式：llm_decision ↔ tool_node 循环
builder.add_conditional_edges("llm_decision",
    lambda s: "tool_node" if s["messages"][-1].tool_calls else END)
builder.add_edge("tool_node", "llm_decision")
# 规则模式：保留旧 intent → route → 各节点
```

### 5. State 扩展

**修改 `app/agent/state.py`**：新增 `messages: list` 字段承载 LangChain 消息流（工具调用/结果的标准载体）。
```python
class AgentState(TypedDict, total=False):
    # 既有字段...
    messages: list[dict]   # 新增：LangChain 消息流
```

### 6. 文件路径入库工具

**在 `tool_defs.py` 的 `ingest_file_by_path` 工具里**：调用现有 `services/ingest.py` 的 `ingest_file(db, user.id, stored_path, filename)`。工具内做：
- 校验路径存在、扩展名在 `SUPPORTED_EXT` 内
- 复制文件到 `data/uploads/` 下
- 调用 `ingest_file` 入库（自动解析、分块、向量化、打标签）
- 返回入库结果卡片

### 7. chat 路由兼容

**`app/routers/chat.py` 无需大改**：`run_agent` 返回签名不变（`{"reply", "cards", "intent"}`）。新增的 LLM 模式下 `intent` 字段填 `"tool_call"` 或工具名，前端不依赖此字段。

---

## 关键文件清单

| 文件 | 操作 | 改动 |
|---|---|---|
| `backend/requirements.txt` | 修改 | +langchain-core, +langchain-openai |
| `backend/.env` | 修改 | 改回 DeepSeek base，用户填 Key |
| `backend/app/config.py` | 修改 | L10-L14 改回 DeepSeek 默认 |
| `backend/app/services/llm.py` | 修改 | 新增 `get_chat_model()` 工厂 |
| `backend/app/agent/state.py` | 修改 | 新增 `messages` 字段 |
| `backend/app/agent/tool_defs.py` | **新建** | 10 个 `@tool` 工具定义 + `build_tools()` 工厂 |
| `backend/app/agent/graph.py` | 修改 | 新增 llm_decision/tool_node 节点 + 降级分支 |
| `backend/app/agent/tools.py` | 不动 | 现有 handler 原样复用 |

---

## 验证方案

1. **安装依赖**：`pip install langchain-core langchain-openai`
2. **填 Key**：用户在 `.env` 填 `LLM_API_KEY=sk-xxx`（DeepSeek）
3. **重启后端**：`python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`
4. **对话测试用例**（任意自然语言，非特定句式）：
   - "下周三要交算法第三章作业，帮我记一下" → 应识别 add_ddl 工具
   - "我 10 月 15 号考数据结构，安排一下复习" → create_review_plan
   - "D:\学习资料\数据结构\test.pdf 帮我导入" → ingest_file_by_path
   - "今天有什么要交的" → query_ddls
   - "讲一下二叉树遍历" → search_materials (RAG)
   - "那个离散数学的小测验我做完了" → complete_ddl
5. **降级验证**：把 Key 删空重启，确认仍能走旧正则规则兜底
6. **前端**：打开 http://127.0.0.1:8000 登录 demo1，在"对话助教"用上述自然语言测试，确认返回正确卡片（ddl_added/review_plan/sources 等）

---

## 风险与回退

- **DeepSeek 不支持 function calling？** → DeepSeek 已支持 OpenAI 兼容的 tool_calls 协议，可直接用
- **ToolNode 执行失败** → graph.py 的 `_handler` 已有 try/except 兜底，工具异常返回友好提示
- **无 Key 时降级** → 保留旧正则分支，用户不填 Key 也能用（只是回到"特定句式"模式）
- **工具循环调用死锁** → LangGraph ToolNode 默认单轮执行，不进入无限循环
