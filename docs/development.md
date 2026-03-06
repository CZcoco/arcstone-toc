# Arcstone 矿业投资智能体 — 开发文档

> 最后更新：2026-02-19（新增：百炼知识库本地上传管理、多知识库 RAG、会话按时间排序）

---

## 一、项目概述

Arcstone 是一个面向矿业投资人的 AI 智能体，目标是从阿里云百炼平台的简单 RAG Chatbot 迁移到一个具备专业判断力、长期记忆和多工具协作能力的 Agent 系统。

**核心价值：** 矿业投资评估需要跨地质、采矿、选矿、经济、合规多学科的综合分析，AI 需要记住每个项目的讨论历史和用户偏好，而不是每次重新开始。

**技术栈：**

| 层 | 方案 |
|---|---|
| 框架 | LangChain Deep Agents 0.4.1 + LangGraph |
| 大模型 | DeepSeek V3.2 / Kimi K2.5 / Qwen 3.5 Plus / Claude Sonnet 4（多模型支持） |
| 工具 | 百炼 RAG、Tavily 搜索、IRR/NPV 计算、Python 代码执行、PDF 读取、记忆语义搜索 |
| 记忆 | CompositeBackend → SqliteStore（`data/memories.db`） + SqliteSaver（`data/checkpoints.db`） + 语义检索（DashScope Embedding + FTS5 + jieba） |
| 前端 | Electron + React + Vite + Tailwind CSS 桌面应用 |
| 后端 API | FastAPI + Uvicorn，SSE 流式输出 |

---

## 二、项目结构

```
D:/miner-agent/
├── .claude/
│   └── CLAUDE.md                  # Claude Code 开发规则
├── .env                           # API Keys（不提交 git）
├── .env.example                   # 环境变量模板
├── requirements.txt               # Python 依赖
├── run.py                         # 终端 CLI 入口
├── run_api.py                     # FastAPI 后端启动脚本（uvicorn, port 8000）
│
├── src/
│   ├── agent/
│   │   ├── config.py              # 多模型配置：DeepSeek / Kimi / Qwen / Claude
│   │   ├── main.py                # create_mining_agent() 工厂函数
│   │   └── prompts.py             # System Prompt：角色 + 7大评估框架 + 记忆指令
│   ├── api/
│   │   ├── app.py                 # FastAPI 应用 + AgentManager（多模型缓存）
│   │   ├── routes.py              # 所有 API 路由
│   │   └── stream.py              # SSE 流式输出封装（agent 线程解耦）
│   ├── store.py                   # SqliteStore：BaseStore 的 SQLite 实现
│   ├── memory_search.py           # MemorySearchEngine：语义检索引擎（Embedding + FTS5 + jieba）
│   └── tools/
│       ├── rag.py                 # 百炼多知识库 RAG 检索（支持 set_rag_kb_configs 动态配置）
│       ├── kb_uploader.py         # BailianKBManager：知识库文件上传/检索/删除
│       ├── search.py              # Tavily 联网搜索（线程安全单例）
│       ├── calculate.py           # IRR / NPV / 回收期计算
│       ├── code_runner.py         # Python 代码执行（subprocess，无状态）
│       ├── pdf_reader.py          # PDF 读取工具（pdfplumber，CLI 用）
│       ├── pdf_parser.py          # PDF 解析模块（MinerU API + pdfplumber 降级）
│       └── memory_search.py       # 记忆语义搜索工具（Agent 调用入口）
│
├── frontend/                      # Electron + React 桌面前端
│   ├── package.json               # 依赖：react 18, react-markdown, lucide-react 等
│   ├── vite.config.ts             # Vite 配置，/api 代理到 localhost:8000
│   ├── tailwind.config.ts         # sand 色系 + accent 色 + 自定义动画
│   ├── src/
│   │   ├── App.tsx                # 主应用：会话管理、消息滚动、模型选择、KB 配置启动同步
│   │   ├── types.ts               # 类型定义：Message、Segment、ToolCall、Session、KBDocument、KBConfig
│   │   ├── hooks/
│   │   │   └── useChat.ts         # SSE 流式 hook：sendMessage / resendMessage
│   │   ├── lib/
│   │   │   └── api.ts             # 后端 API 封装
│   │   └── components/
│   │       ├── ChatMessage.tsx     # 消息渲染（segment-based）+ 编辑重发
│   │       ├── ChatInput.tsx       # 输入框 + 模型选择器
│   │       ├── ModelSelector.tsx   # 模型下拉选择器
│   │       ├── ToolCallCard.tsx    # 工具调用卡片（可展开）
│   │       ├── ThinkingIndicator.tsx  # 思考中动画
│   │       ├── Sidebar.tsx         # 侧边栏：会话列表 + 右键菜单 + 知识库/记忆按钮
│   │       ├── MemoryPanel.tsx     # 记忆面板（右侧抽屉）
│   │       └── KnowledgeBasePanel.tsx  # 知识库管理面板（右侧抽屉，多知识库切换/上传/删除）
│   └── electron/
│       └── main.ts                # Electron 主进程
│
├── data/
│   ├── memories.db                # SQLite 持久化记忆（运行时生成）
│   ├── checkpoints.db             # SQLite 会话检查点（运行时生成）
│   └── thread_id.txt              # CLI 当前会话 ID（运行时生成）
│
├── docs/
│   ├── 01-需求分析.md ~ 09-代码示例.md   # 9 篇架构设计文档
│   ├── development.md             # 本文档
│   └── plans/
│       └── 2026-02-17-memory-layer-design.md
│
└── skills/                        # Agent 技能定义（PDF 处理等）
```

---

## 三、架构详解

### 3.1 Agent 创建流程

```python
# src/agent/main.py
def create_mining_agent(model_name="deepseek", db_path=..., checkpoint_path=...,
                        store=None, checkpointer=None):
    llm = get_llm(model_name)
    if store is None:
        store = SqliteStore(db_path)
    if checkpointer is None:
        checkpointer = SqliteSaver(sqlite3.connect(checkpoint_path, check_same_thread=False))

    agent = create_deep_agent(
        model=llm,
        tools=[bailian_rag, web_search, calculate_irr, run_python, read_pdf, memory_search],
        system_prompt=MINING_SYSTEM_PROMPT,
        store=store,
        backend=lambda rt: CompositeBackend(
            default=StateBackend(rt),
            routes={"/memories/": StoreBackend(
                rt, namespace=lambda ctx: ("filesystem",)
            )},
        ),
        checkpointer=checkpointer,
    )
    return agent, store, checkpointer
```

支持传入已有的 `store` 和 `checkpointer` 以实现多模型共享（见 3.8 节）。

`create_deep_agent` 是 deepagents 的核心函数，返回 LangGraph 的 `CompiledStateGraph`。它自动注入以下内置工具和中间件：

**内置工具（由 deepagents 提供）：**
- `write_file` / `read_file` / `edit_file` — 文件系统操作
- `ls` / `glob` / `grep` — 文件浏览搜索
- `write_todos` — 任务规划
- `task` — 子代理委派（Agent 会自主创建 subagent 处理复杂子任务）
- `execute` — Shell 命令执行

**内置中间件：**
- `TodoListMiddleware` — 任务管理
- `FilesystemMiddleware` — 文件系统初始化
- `SubAgentMiddleware` — 子代理调度
- `SummarizationMiddleware` — 长对话自动摘要
- `PatchToolCallsMiddleware` — 工具调用修正

### 3.2 文件系统后端（CompositeBackend）

Agent 的文件操作通过 `CompositeBackend` 路由到不同后端：

```
Agent 调用 write_file("/notes.txt", ...)
    → CompositeBackend → 不匹配 /memories/ 前缀
    → StateBackend（临时，会话结束即消失）

Agent 调用 write_file("/memories/projects/铜矿.md", ...)
    → CompositeBackend → 匹配 /memories/ 前缀
    → StoreBackend → SqliteStore.put()（永久保存到 SQLite）
```

**路径剥离行为：** CompositeBackend 路由后会剥掉匹配的前缀。Agent 写入 `/memories/user_profile.md`，StoreBackend 实际存储的 key 是 `/user_profile.md`。读取时同理。这是 deepagents 的设计行为，对 Agent 透明。

**namespace 显式化：** StoreBackend 构造时传入 `namespace=lambda ctx: ("filesystem",)`，显式指定存储命名空间。这避免了 deepagents 0.4.1 的隐式 namespace 推断（依赖 `assistant_id`），并为 0.5.0 升级做准备（届时 namespace 将成为必传参数）。

### 3.3 SqliteStore 实现

`src/store.py` 继承 `langgraph.store.base.BaseStore`，用 Python 内置 `sqlite3` 实现。

**数据库 Schema：**

```sql
CREATE TABLE items (
    namespace TEXT NOT NULL,    -- '["filesystem"]'（JSON 数组）
    key       TEXT NOT NULL,    -- '/user_profile.md'
    value     TEXT NOT NULL,    -- JSON: {"content": [...], "created_at": ..., "modified_at": ...}
    created_at TEXT NOT NULL,   -- ISO 时间戳
    updated_at TEXT NOT NULL,
    PRIMARY KEY (namespace, key)
);
```

**核心设计决策：**
- namespace 是 `tuple[str, ...]`，序列化为 JSON 数组字符串存储
- value 是 `dict`，序列化为 JSON 字符串
- 每次 `put` 立即 `commit`，不怕崩溃丢数据
- WAL 模式（Write-Ahead Logging）提升并发读写性能
- `check_same_thread=False` 支持多线程访问
- 更新时保留原始 `created_at`，只更新 `updated_at`
- 搜索用 JSON 前缀匹配：`'["filesystem"'` LIKE 匹配 `'["filesystem"]'` 和 `'["filesystem", "sub"]'`

**为什么不用官方 Store：** LangGraph 官方只有 `InMemoryStore`（重启丢失）和 `PostgresStore`（需要数据库服务）。没有 `SqliteStore`。自己实现约 230 行代码，零额外依赖，后续 Electron 桌面应用直接打包带走。

### 3.4 记忆系统

**记忆目录结构：**

```
/memories/
├── user_profile.md      # 用户偏好（IRR 门槛、矿种关注、沟通习惯）
├── instructions.md      # 自我改进指令（术语纠正、回答方式偏好）
├── projects/            # 项目档案（每个项目一个文件）
│   ├── 贵州磷矿.md
│   └── 云南铜矿.md
├── decisions/           # 投资决策记录
│   └── 2026-02-17_贵州磷矿_推进尽调.md
└── documents/           # PDF 上传转换后的文档
    └── 可研报告_xxx.md
```

**两种写入方式：**

1. **实时写入：** Agent 在对话中检测到用户偏好/决策时，立即调用 `write_file` 写入（由 System Prompt 指令驱动）
2. **归档写入：** 用户输入 `/archive` 或退出时选择归档，Agent 回顾完整对话历史，提取关键信息完整写入

**读取时机：** Agent 收到每轮第一条用户消息后，System Prompt 指示它依次读取：
1. `/memories/index.md` — 记忆索引（所有文件的路径、摘要、更新时间）
2. `/memories/user_profile.md` — 用户投资偏好
3. `/memories/instructions.md` — 工作改进指令

根据索引内容和用户消息，按需读取具体文件（如用户提到"铜矿A"则读 `/memories/projects/铜矿A.md`）。

**语义检索引擎（MemorySearchEngine）：**

`src/memory_search.py` 实现了记忆文件的混合语义检索，与 SqliteStore 共享同一个 `sqlite3.Connection`，在 `memories.db` 中额外管理两张表：

```sql
-- 向量索引
CREATE TABLE embeddings (
    namespace TEXT NOT NULL,
    key       TEXT NOT NULL,
    embedding BLOB NOT NULL,       -- numpy float32, 1024维, tobytes()
    text_hash TEXT NOT NULL,       -- SHA256[:16], 变更检测
    updated_at TEXT NOT NULL,
    PRIMARY KEY (namespace, key)
);

-- 全文索引（jieba 分词后存入）
CREATE VIRTUAL TABLE fts_memory USING fts5(
    namespace, key, content,
    tokenize='unicode61'
);
```

**写入流程：** SqliteStore `_handle_put()` 写入 `("filesystem",)` 命名空间时自动触发 hook：
1. `text_hash`（SHA256[:16]）变更检测，内容没变不调 API
2. 调 DashScope `text-embedding-v3`（1024 维）生成向量 → 写入 embeddings 表
3. jieba `cut_for_search` 分词 → 写入 fts_memory 表
4. embedding 失败只 log 不阻塞写入

**检索流程：** Agent 调用 `memory_search` 工具 → `MemorySearchEngine.search()`：
1. 向量余弦相似度（权重 70%）：query embedding vs 全量 embeddings，numpy 批量计算
2. BM25 关键词匹配（权重 30%）：jieba 分词后 FTS5 MATCH 查询，分数归一化到 [0,1]
3. 加权合并排序，返回 top-K 文件路径 + 评分 + 摘要片段

**Backfill 机制：** 应用启动时（`app.py` lifespan），`backfill()` 遍历所有已有记忆，embedding hash 没变只刷新 FTS（`force_fts=True`），两次 API 调用间 sleep 0.2s 防限频。

**全局访问器：** `set_global_search_engine()` / `get_global_search_engine()` 模块变量，在 `app.py` lifespan 中注册，供 `@tool` 装饰的 `memory_search` 工具获取引擎实例。

**Agent 工具（`src/tools/memory_search.py`）：**

```python
@tool
def memory_search(query: str, top_k: int = 5) -> str:
    """搜索记忆文件，找到与查询最相关的内容。"""
```

返回格式化的文件路径 + 相关度评分 + 摘要，Agent 看到后用 `read_file` 精读具体内容。

**记忆索引（index.md）：**

`/memories/index.md` 是所有记忆文件的目录，Agent 首轮只需读这一个文件即可知道自己记了什么。格式为 Markdown 表格，按类型分区：

```markdown
# 记忆索引

## 用户画像
| 文件 | 摘要 | 更新时间 |
| /user_profile.md | 资深矿业投资人，偏好IRR>15%，关注铜矿锂矿... | 2026-02-15 |

## 项目
| 文件 | 摘要 | 更新时间 |
| /projects/铜矿A.md | 贵州铜矿，IRR约12%，建议观望... | 2026-02-15 |

## 决策
| 文件 | 摘要 | 更新时间 |

## 文档
| 文件 | 摘要 | 更新时间 |
| /documents/PRD.md | 产品需求文档，11页，MinerU解析 | 2026-02-18 |
```

**索引维护规则：**
- **Agent 实时维护：** 每次 `write_file` 写入/更新记忆文件后，必须同步更新 `index.md` 对应行
- **后端自动维护：** `POST /api/upload/pdf` 端点在存完 PDF 后自动写入索引条目（`_update_memory_index` 函数）
- **摘要长度：** 项目/决策类 80-150 字（含关键数据），文档类 20-50 字
- **去重：** 同一文件路径重复写入时更新现有行，不重复添加

**多轮对话 vs 跨会话记忆的区别：**

| 维度 | 多轮对话（同一会话） | 跨会话记忆 |
|---|---|---|
| 实现方式 | LangGraph checkpointer（SqliteSaver → `data/checkpoints.db`） | `/memories/` + SqliteStore → `data/memories.db` |
| 数据范围 | 完整消息历史（你说的+AI回的+工具调用） | Agent 主动提取写入的结构化信息 |
| 生命周期 | 同一 thread_id 内有效，**跨进程重启保留** | 永久保存，所有会话可读 |
| 上限 | 受 128K 上下文限制，超长对话会被摘要 | 无限制，每个文件独立 |
| 精度 | 完美（原始消息） | 取决于 Agent 写入的详细程度 |

### 3.5 多模型配置

```python
# src/agent/config.py
MODEL_CONFIG = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",          # DeepSeek V3.2, 128K
        "env_key": "DEEPSEEK_API_KEY",
        "extra_kwargs": {"frequency_penalty": 0.3},  # 抑制重复
    },
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "kimi-k2.5",
        "env_key": "MOONSHOT_API_KEY",
        "extra_body": {"thinking": {"type": "disabled"}},  # 关闭 thinking
        "extra_kwargs": {"temperature": 0.6},
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen3.5-plus",
        "env_key": "DASHSCOPE_API_KEY",
        "extra_body": {"enable_thinking": False},  # 关闭 thinking
    },
    "claude": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "env_key": "ANTHROPIC_API_KEY",
    },
    "claude-honsoft": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "base_url": "https://cc.honsoft.cn",   # 自有服务器代理
        "env_key": "ANTHROPIC_AUTH_TOKEN",
    },
}
```

- OpenAI 兼容模型（DeepSeek / Kimi / Qwen）统一用 `langchain_openai.ChatOpenAI`
- Anthropic 模型用 `langchain_anthropic.ChatAnthropic`，支持自定义 `base_url`
- `extra_kwargs` 允许每个模型设置独有参数（如 DeepSeek 的 `frequency_penalty`）
- 未知模型名会抛出 `ValueError` 并提示可用选项
- 前端模型选择持久化到 `localStorage`

**模型测试情况（2026-02-18）：**

| 模型 | 流畅度 | 工具调用 | 备注 |
|---|---|---|---|
| DeepSeek V3.2 | 最流畅 | 稳定（3轮10次工具调用通过） | 默认开发模型 |
| Qwen 3.5 Plus | 不错 | 稳定（2轮2次工具调用通过） | 阿里云 DashScope 接口 |
| Kimi K2.5 | 正常 | 稳定（关闭 thinking 后2轮10次通过） | Moonshot API，需关闭 thinking |
| Claude Sonnet 4 | 优秀 | 稳定（3轮7次工具调用通过） | 需通过自有服务器代理访问 |

> **Kimi/Qwen thinking 模式修复：** `ChatOpenAI` 会丢弃 `reasoning_content` 字段，导致多轮工具调用时 API 报 400 错误。通过 `extra_body` 关闭 thinking 模式解决（Kimi: `{"thinking": {"type": "disabled"}}`，Qwen: `{"enable_thinking": False}`）。

> **Claude content 格式兼容：** Anthropic 模型的 `AIMessage.content` 返回 `list[{"type":"text","text":"..."}]` 而非 `str`。通过 `_extract_text()` 统一提取函数兼容两种格式，用于 stream.py、routes.py、run.py 三处。

### 3.6 System Prompt 设计

`src/agent/prompts.py` 中的 `MINING_SYSTEM_PROMPT` 包含：

1. **角色定义：** 20 年矿业投资实战经验的高级顾问，"老朋友"身份
2. **核心原则：** 知识库优先、拒绝幻觉、专业严谨、决策导向
3. **7 大评估框架：** A.地质资源 → B.水文工程 → C.开发条件 → D.采矿 → E.选矿 → F.经济性 → G.合规风险
4. **工具使用指南：** 何时用 RAG、搜索、计算
5. **工作方法（规划层）：** 任务类型路由（简单问答/单项分析/多步评估/对比决策）、多步任务先列 3-5 步计划再逐步执行、计划调整策略、完成后自检清单
6. **记忆管理指令：** 何时读取/写入 `/memories/`，使用 `read_file`/`write_file`
7. **对话风格：** 平和、主动、不显示引用来源

**规划层设计要点：**
- 不使用独立的 planning 模块，通过 System Prompt 引导模型自主规划（参考 Anthropic "从最简单方案开始"原则）
- 任务类型路由：模型根据任务复杂度选择策略——简单问题直接答，复杂任务先列计划
- Todo-list 注意力锚定：Deep Agents 内置 `TodoListMiddleware`，自动提供 `write_todos` 工具。模型在复杂任务中使用它跟踪进度，已完成步骤附带简短结论，防止长对话中目标偏移
- 完成后自检：多步分析完成后检查覆盖完整性、数据来源、结论一致性、遗漏风险
- 调研基础：`docs/research/agent-planning-research.md`（Lilian Weng、Anthropic、Manus、学术前沿）

---

## 四、FastAPI 后端 API

### 4.1 架构设计

```
FastAPI (app.py)
  ├── lifespan: 创建共享 SqliteStore + SqliteSaver + AgentManager
  ├── AgentManager: 按 model_name 懒加载并缓存 agent 实例
  │   └── 多模型共享同一 store 和 checkpointer
  └── routes.py: 所有 API 端点
```

**关键设计决策：**
- 所有涉及阻塞 IO 的端点用 `def`（非 `async def`），FastAPI 自动放入线程池执行，不阻塞事件循环
- Agent 单例通过 `AgentManager.get(model_name)` 获取，线程安全的 double-checked locking
- SSE 流式输出通过 `stream.py` 将 `agent.stream()` 解耦到独立线程

### 4.2 SSE 流式输出（stream.py）

**核心机制：agent 线程与 SSE 推送解耦**

```
┌─────────────┐     queue.Queue      ┌──────────────┐
│  Agent 线程  │ ──── put(event) ───→ │  SSE 生成器   │ → yield → 客户端
│ agent.stream │                      │  stream_to_  │
│  (独立线程)  │ ← detached.set() ── │  sse()       │
└─────────────┘                      └──────────────┘
```

- `_run_agent()` 在 `threading.Thread(daemon=True)` 中运行 `agent.stream()`
- 事件通过 `queue.Queue` 传递给 SSE 生成器
- `_SENTINEL` 对象标记线程结束
- **客户端断开时**（`GeneratorExit`）：设置 `detached` Event，agent 线程停止入队但继续运行直到完成，确保 LangGraph checkpoint 被保存。用户切回该会话时从 history 加载完整回复
- `detached` flag 防止断连后 queue 内存无限增长

**SSE 事件类型：**

| 事件 | 数据 | 说明 |
|---|---|---|
| `text_chunk` | `{content: "..."}` | AI 文本 token |
| `tool_call` | `{id, name, args}` | Agent 发起工具调用 |
| `tool_result` | `{id, name, content}` | 工具返回结果 |
| `thinking` | `{}` | 检测到工具调用 chunk（思考中） |
| `done` | `{}` | 流式输出结束 |
| `error` | `{message: "..."}` | 出错 |

### 4.3 API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/health` | 健康检查 |
| `GET` | `/api/models` | 返回可用模型列表（检测 API Key 是否配置） |
| `POST` | `/api/chat/stream` | 发送消息并流式返回，支持 `model` 参数 |
| `POST` | `/api/chat/resend` | 编辑重发：Time Travel 到指定用户消息之前的 checkpoint |
| `POST` | `/api/archive` | 归档当前对话的记忆 |
| `POST` | `/api/session/new` | 创建新会话（返回 UUID） |
| `GET` | `/api/session/list` | 列出所有会话 |
| `POST` | `/api/session/rename` | 重命名会话 |
| `DELETE` | `/api/session/{thread_id}` | 删除会话 |
| `GET` | `/api/session/{thread_id}` | 获取会话历史消息 |
| `GET` | `/api/memory/list` | 列出所有记忆文件 |
| `GET` | `/api/memory/{key}` | 获取记忆文件内容 |
| `PUT` | `/api/memory/{key}` | 更新记忆文件内容 |
| `DELETE` | `/api/memory/{key}` | 删除记忆文件 |
| `POST` | `/api/memory/rename` | 重命名记忆文件（保留目录，只改文件名） |
| `POST` | `/api/upload/pdf` | 上传单个 PDF/Word 文件，解析后存入 memories |
| `POST` | `/api/upload/pdfs` | 批量上传（最多 5 个），MinerU 并行解析，逐个存入 memories |
| `GET` | `/api/kb/list` | 列出知识库文档（分页，可指定 `index_id`） |
| `POST` | `/api/kb/upload` | 上传文件到百炼知识库（异步，返回 job_id） |
| `GET` | `/api/kb/upload/status` | 查询上传任务状态（轮询） |
| `DELETE` | `/api/kb/delete` | 删除知识库文档 |
| `GET` | `/api/kb/rag/config` | 获取当前 RAG 知识库配置列表 |
| `POST` | `/api/kb/rag/config` | 更新 RAG 知识库配置列表 |

### 4.4 编辑重发（Time Travel）

用户可以编辑之前任意一条用户消息并重新发送。后端利用 LangGraph 的 `get_state_history()` 实现：

1. 前端传 `message_index`（第几条用户消息，0-based）和编辑后的 `message`
2. 后端遍历 `agent.get_state_history(config)`（按时间倒序），找到 human message 数量 ≤ `message_index` 的 snapshot
3. 用该 snapshot 的 config（包含 `checkpoint_id`）调 `agent.stream()`，从那个时间点 fork 新对话分支
4. 原始对话历史保留在 checkpointer 中不被破坏

设有 safety bound（最多扫描 500 个 checkpoint），防止超长对话下的性能问题。

### 4.5 Tavily 搜索线程安全

`src/tools/search.py` 中 `TavilyClient` 改为线程安全单例（double-checked locking）：

```python
_client: TavilyClient | None = None
_client_lock = threading.Lock()

def _get_client() -> TavilyClient:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))
    return _client
```

**原因：** 之前每次 `web_search()` 调用都创建新的 `TavilyClient`（内含 `requests.Session`）。FastAPI 多线程环境下频繁创建/销毁 Session 导致 urllib3 连接池竞争，远程服务器检测到异常连接强制关闭（ConnectionResetError 10054）。

**注意：** Tavily API（`api.tavily.com`）在中国大陆被 GFW 封锁，需要 VPN 才能访问。

---

## 五、Electron + React 前端

### 5.1 技术栈

| 技术 | 版本 | 用途 |
|---|---|---|
| React | 18 | UI 框架 |
| Vite | 6 | 构建工具 |
| Tailwind CSS | 3 | 样式 |
| TypeScript | 5 | 类型安全 |
| Electron | 33 | 桌面壳 |
| react-markdown + remark-gfm | — | Markdown 渲染 |
| lucide-react | — | 图标 |
| @microsoft/fetch-event-source | — | SSE 客户端 |

### 5.2 设计风格

Claude-like 简洁暖色调：
- 背景色：warm ivory `#f5f3ef`
- 主色调：sand 色系（自定义 Tailwind palette）
- 强调色：`#c8956c`（accent）
- 字体：DM Sans + Noto Sans SC + JetBrains Mono
- 动画：fadeIn、slideUp、slideRight、pulseSoft
- 超细滚动条，琥珀色文字选区

### 5.3 消息模型（Segment-Based）

核心设计：消息内容由有序的 `Segment[]` 数组组成，保证文本和工具调用的交替顺序在流式输出和历史加载时一致。

```typescript
type Segment = TextSegment | ToolCallSegment;

interface TextSegment {
  type: "text";
  content: string;
}

interface ToolCallSegment {
  type: "tool_call";
  toolCall: ToolCall;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;           // 全文（用于预览/fallback）
  segments?: Segment[];      // 有序内容段
  isStreaming?: boolean;
}
```

**为什么不用 `content + toolCalls[]`：** 之前用扁平结构（`content: string` + `toolCalls: ToolCall[]`），渲染时所有工具调用堆在顶部、文字在底部，与实际生成顺序不符。Segment-based 模型按到达顺序排列，`ChatMessage` 组件直接 `.map()` 渲染。

### 5.4 useChat Hook

核心 SSE 流式处理 hook，提供：

- `sendMessage(content, model?)` — 发送新消息
- `resendMessage(messageId, newContent, model?)` — 编辑并重发
- `stopStreaming()` — 停止流式输出
- `loadHistory(history)` — 从 checkpoint 加载历史消息
- `clearMessages()` — 清空（切换会话时用）

**内部架构：**

```
sendMessage / resendMessage
    └→ streamResponse(url, body, priorMessages)
        ├── 创建 AbortController
        ├── 添加空 AI 消息到 messages
        ├── fetchEventSource (SSE)
        │   ├── text_chunk → 累积到最后一个 TextSegment
        │   ├── tool_call → 新建 ToolCallSegment，断开文字累积
        │   ├── tool_result → 更新对应 ToolCall 的 result + status
        │   ├── thinking → 断开文字累积
        │   ├── done → flushUI，标记完成
        │   └── error → 显示错误
        └── requestAnimationFrame 节流 UI 更新
```

**关键技术点：**
- `currentAiIdRef` 精确追踪当前 AI 消息 ID，避免用 `prev[length-1]` 导致的消息错乱
- `textAccumulating` flag：连续 `text_chunk` 追加到同一 TextSegment；`tool_call`/`thinking` 事件断开累积
- `requestAnimationFrame` 节流：`syncToUI()` 每帧最多更新一次，`flushUI()` 在终止事件时立即刷新
- 重发消息时通过 `streamResponse` 共享完整 SSE 处理逻辑，避免代码重复

### 5.5 组件说明

**ChatMessage.tsx** — 消息渲染 + 编辑重发
- `React.memo()` 包裹防止不必要渲染
- 用户消息 hover 显示铅笔图标，点击进入编辑模式
- 编辑模式：textarea 预填内容，自适应高度，Enter 提交，Escape 取消
- 流式输出时隐藏编辑按钮
- AI 消息按 `segments` 顺序渲染 TextSegment（Markdown）和 ToolCallCard

**ModelSelector.tsx** — 模型下拉选择器
- 从 `GET /api/models` 获取可用模型列表（只显示有 API Key 的）
- 向上弹出菜单，显示模型名和 model ID
- 只有多于 1 个可用模型时才显示
- 选择持久化到 `localStorage`

**Sidebar.tsx** — 侧边栏会话管理
- 会话列表从 `GET /api/session/list` 加载
- 右键上下文菜单：重命名、删除
- 重命名：内联 input，Enter/blur 提交，Escape 取消
- `stripMarkdown()` 清理预览文本中的 Markdown 语法

**ChatInput.tsx** — 输入框 + 附件暂存 + 多文件上传
- 自适应高度 textarea（最大 180px）
- Enter 发送，Shift+Enter 换行
- 流式输出时显示停止按钮（Square 图标）
- 底部左侧放 ModelSelector + 文件上传按钮（回形针），右侧放发送按钮
- 文件上传：支持 `.pdf/.doc/.docx`，`multiple` 多选，每次最多选 5 个，总附件上限 30 个
- 上传中显示"解析中 N 个文件..."指示条（附件区内）
- 附件标签区：文件名 + 页数 + X 关闭按钮，多文件累积，发送后清空

### 5.6 智能滚动

- `scrollRef` 监听 scroll 事件，距底部 >80px 认为用户在看历史
- `userScrolledUpRef` 为 true 时不自动滚动
- 流式输出时用 `"auto"` behavior（无动画堆叠），完成后用 `"smooth"`
- 用户发新消息时强制重置 `userScrolledUpRef = false`

---

## 六、工具详解

### 6.1 百炼 RAG（`bailian_rag`）

调用阿里云百炼 Retrieve API 检索内部知识库，支持多知识库同时检索。

- **API：** `alibabacloud_bailian20231229.client.Client.retrieve_with_options()`
- **Workspace ID：** 通过环境变量 `BAILIAN_WORKSPACE_ID` 获取
- **Index ID：** 通过 `set_rag_kb_configs()` 动态配置，支持多个知识库
- **AccessKey：** 通过系统环境变量 `ALIBABA_CLOUD_ACCESS_KEY_ID` / `SECRET` 获取
- **多知识库：** 全局 `_rag_kb_configs: list[dict]` 线程安全存储，`bailian_rag` 工具遍历所有配置，结果带 `--- 来自知识库「name」---` 前缀汇总返回
- **配置同步：** 前端 KnowledgeBasePanel 更新知识库列表时调 `POST /api/kb/rag/config`；App 启动时从 localStorage 同步到后端（防重启丢失）
- **返回格式：** 所有知识库结果合并，每个知识库单独标注来源；未检索到时返回提示

**设计选择：** 用 Retrieve API 而非 Application API，这样 Agent 自己做 prompt 组装，不依赖百炼应用层的模型和模板，灵活度更高。工具描述保持通用（不写死域名/内容），RAG 检索的知识库内容由用户在 KnowledgeBasePanel 自行上传和管理。

### 6.2 联网搜索（`web_search`）

通过 Tavily API 搜索实时信息。

- **用途：** 矿价走势、政策变化、行业新闻
- **深度：** `basic`（快速）或 `advanced`（深入，多花 1 credit）
- **返回：** AI 摘要 + 前 5 条结果标题和内容
- **线程安全：** TavilyClient 单例 + threading.Lock
- **限制：** 中国大陆需 VPN 访问 `api.tavily.com`

### 6.3 财务计算（`calculate_irr`）

计算 IRR、NPV、投资回收期。

- **IRR：** 二分法求解（1000 次迭代，精度 ±0.0001%）
- **NPV：** 以指定折现率计算
- **回收期：** 累计现金流法，支持小数年份
- **输入：** 初始投资（万元）、各年净现金流列表、折现率
- **输出：** 格式化的字典

### 6.4 Python 代码执行（`run_python`）

让 Agent 编写并运行 Python 代码进行数据分析、计算、画图。

- **执行方式：** 写入临时 `.py` 文件 → `subprocess.run()` 执行 → 返回 stdout
- **Python 路径：** 通过环境变量 `PYTHON_EXECUTABLE` 指定，fallback 到 `sys.executable`
- **超时：** 30 秒自动终止
- **输出限制：** 最大 10,000 字符，超出截断
- **无状态：** 每次执行独立进程，变量不跨次保留
- **可用库：** numpy, scipy, pandas, matplotlib 等已安装的库
- **安全考虑：** 只能跑 Python，不开放 shell 权限
- **画图：** Agent 用 `plt.savefig()` 保存到临时目录

**典型场景：** IRR/NPV/DCF 计算、敏感性分析、蒙特卡洛模拟、pandas 数据处理、matplotlib 图表

### 6.5 PDF 读取（`read_pdf`）

使用 pdfplumber 读取 PDF 全文，主要供 CLI 场景使用。

- **执行方式：** 与 `run_python` 类似，subprocess 调用 pdfplumber
- **超时：** 60 秒
- **输出限制：** 最大 50,000 字符
- **用途：** Agent 在命令行中直接读取用户指定路径的 PDF 文件

### 6.6 文件解析模块（`pdf_parser.py`，非 Agent 工具）

PDF/Word 上传功能的后端解析模块，由 API 端点调用。支持 `.pdf`、`.doc`、`.docx` 格式。

**双引擎策略（自动降级 + 重试）：**

```
有 MINERU_API_KEY 且有效？
  → 是：MinerU API 解析（vlm 模式，表格/公式质量更好）
       → 第 1 次失败？sleep 2s 重试 1 次（单文件）/ 整体降级（批量）
       → 两次都失败：降级本地解析（pdfplumber 或 python-docx）
  → 否：本地解析直接处理
       → pdf → pdfplumber
       → docx → python-docx（提取段落文本）
       → doc → 无本地方案，仅靠 MinerU
       → 提取为空（扫描件）？返回 warning 提示用户
```

**MinerU 批量解析流程（多文件并行）：**

1. `POST /api/v4/file-urls/batch` — 所有文件一次请求，申请 `batch_id` + 各文件上传 URL
2. 逐个 `PUT {upload_url}` — 上传文件字节到 OSS
3. 轮询 `GET /api/v4/extract-results/batch/{batch_id}`（5秒间隔，最多5分钟）
   - 用**数组索引**而非 `file_name` 匹配结果（MinerU 返回的 `file_name` 可能来自 PDF 元数据，与上传时的文件名不同）
   - `total_pages` 只在 `state=running` 时有值，通过 `pages_cache` 在轮询中缓存
4. 下载各文件的 `full_zip_url` → 解压 → 提取 `full.md`
5. 单个文件 MinerU 失败 → 独立降级本地解析，不影响其他文件

**存储格式：** 转换后的文本以 StoreBackend 兼容格式存入 `/memories/documents/{文件名}.md`：

```python
store.put(("filesystem",), "/documents/报告名.md", {
    "content": full_content.split("\n"),  # list of lines
    "created_at": iso_timestamp,
    "modified_at": iso_timestamp,
})
```

Agent 通过 `ls("/memories/documents/")` 发现文件，`read_file` 读取内容（默认前100行，支持翻页）。

**文件头部元信息：**

```markdown
# 报告名
- 来源：PDF 上传
- 页数：11
- 解析方式：mineru

---

(正文内容)
```

---

## 七、终端 CLI（run.py）

### 7.1 流式输出

使用 `agent.stream()` + `stream_mode=["messages", "updates"]` 实现实时显示：

- **Token 流：** AI 回复逐字输出
- **工具调用：** 显示 `⚡ 调用工具: web_search(query='...')`
- **工具结果：** 显示 `✓ web_search 返回: ...`（截断 200 字）
- **思考状态：** 检测到工具调用 chunk 时显示"思考中..."

### 7.2 交互命令

| 命令 | 功能 |
|---|---|
| `/new` | 新建会话（生成新 thread_id，提示是否先归档） |
| `/archive` | 归档当前对话（Agent 回顾对话并写入 /memories/） |
| `/memory` | 列出所有记忆文件 |
| `exit` / `quit` / `退出` | 退出（提示是否归档） |

### 7.3 会话持久化

`thread_id` 保存在 `data/thread_id.txt`。重启 `run.py` 时复用上次的 thread_id，配合 `SqliteSaver` checkpointer 实现**跨进程重启的对话连续性**。

---

## 八、环境与依赖

### 8.1 Python 环境

- **Conda 环境：** `miner-agent`
- **Python 路径：** `D:/miniconda/envs/miner-agent/python.exe`
- **禁止** 使用裸 `python` / `pip` / `conda run`

### 8.2 依赖列表

| 包 | 版本 | 用途 |
|---|---|---|
| deepagents | 0.4.1 | Agent 框架 |
| langchain-openai | 1.1.9 | DeepSeek / Kimi / Qwen API 调用 |
| langchain-anthropic | 1.3.3 | Claude API 调用 |
| tavily-python | 0.7.21 | 联网搜索 |
| python-dotenv | 1.2.1 | .env 加载 |
| alibabacloud_bailian | — | 百炼 RAG SDK |
| langgraph | 1.0.8 | Agent 运行时 |
| langgraph-checkpoint | 4.0.0 | 检查点基础抽象 |
| langgraph-checkpoint-sqlite | 3.0.3 | SQLite 持久化检查点 |
| fastapi | 0.115+ | Web API 框架 |
| uvicorn | 0.34+ | ASGI 服务器 |
| numpy / scipy / pandas / matplotlib | — | 数据分析（run_python 工具依赖） |
| pdfplumber | 0.11+ | PDF 本地解析（降级方案） |

### 8.3 API Keys

| Key | 来源 | 存储位置 |
|---|---|---|
| DEEPSEEK_API_KEY | DeepSeek 官网 | `.env` |
| MOONSHOT_API_KEY | Moonshot 开放平台 | `.env` |
| DASHSCOPE_API_KEY | 阿里云 DashScope | `.env` |
| ANTHROPIC_API_KEY | Anthropic | `.env` |
| ANTHROPIC_AUTH_TOKEN | 自有服务器代理 | `.env` |
| ALIBABA_CLOUD_ACCESS_KEY_ID/SECRET | 阿里云 RAM | 系统环境变量 |
| BAILIAN_WORKSPACE_ID / INDEX_ID | 百炼控制台 | `.env` |
| BAILIAN_CATEGORY_ID | 百炼文件分类 ID（默认 `default`） | `.env`（可选） |
| TAVILY_API_KEY | Tavily 官网 | `.env` |
| PYTHON_EXECUTABLE | conda 环境 Python 路径 | `.env` |
| MINERU_API_KEY | MinerU 官网（90天有效） | `.env`（可选） |

---

## 九、开发过程 & Bug 修复记录

### 9.1 前端开发阶段（2026-02-18）

从零搭建完整的 Electron + React + FastAPI 前端，经历多轮迭代测试和 bug 修复。

#### Bug 1: Markdown 列表不显示
- **现象：** 有序/无序列表的项目符号不显示
- **原因：** 全局 CSS reset `* { margin: 0; padding: 0 }` 覆盖了 `list-style`
- **修复：** 在 `index.css` 的 `.prose` 选择器中显式设置 `list-style-type: disc/decimal`，`.prose li { display: list-item }`，嵌套列表用 circle/square

#### Bug 2: 输出卡住 + 回复顺序错乱
- **现象：** 流式输出中途卡住，再发消息后回复顺序混乱
- **原因：** useChat 用 `prev[prev.length - 1]` 定位当前 AI 消息；没有 `done` 事件时 `isStreaming` 永远为 true；新消息更新到错误的 AI 消息上
- **修复：** 引入 `currentAiIdRef` 精确追踪 AI 消息 ID；`updateAiMessage(aiId, patch)` 用 `.map()` 精准更新；添加 `onclose` 处理连接断开；新消息强制 abort 前一个流

#### Bug 3: 侧边栏显示原始 Markdown
- **现象：** 会话预览文本显示 `**需求端强劲**` 等 Markdown 语法
- **原因：** 预览文本直接从 checkpoint 取出，未经处理
- **修复：** 添加 `stripMarkdown()` 函数，剥离 bold、italic、heading、link、list marker、blockquote 等语法

#### Bug 4: 工具调用和文字顺序错误（流式输出）
- **现象：** 流式输出时所有工具调用堆在顶部，文字在底部
- **原因：** 原始消息模型是扁平的 `content + toolCalls[]`，ChatMessage 先渲染所有 toolCalls 再渲染 content
- **修复：** 彻底重构为 **segment-based 消息模型**（见 5.3 节），按到达顺序排列，`.map()` 渲染

#### Bug 5: 工具调用和文字顺序错误（历史加载）
- **现象：** 退出再进入后，同一回复中工具调用堆在最上面
- **原因：** `loadHistory` 中处理 assistant 消息时先推 tool_calls 再推 text
- **修复：** 调整为先推 text segment 再推 tool_call segments（与流式顺序一致）

#### Bug 6: 流式输出时强制拖拽滚动
- **现象：** 用户向上滚动查看历史时被拖回底部
- **原因：** `useEffect` 在 `messages` 变化时无条件调用 `scrollIntoView`
- **修复：** 添加 `userScrolledUpRef` 跟踪用户滚动意图（距底部 >80px），只在用户靠近底部时自动滚动；流式输出用 `"auto"` behavior 避免动画堆叠

#### Bug 7: 重命名/删除会话无效
- **现象：** 右键菜单操作无反应
- **原因：** 后端未重启（旧版本没有对应路由）；前端 catch 块为空 `// ignore` 无报错
- **修复：** 重启后端；catch 块改为 `console.error`；`store.put(ns, key, None)` 改为 `store.delete(ns, key)`

#### Bug 8: 阻塞事件循环（Code Review 发现）
- **原因：** 所有端点用 `async def`，但调用同步的 `agent.stream()` 和 SQLite 操作
- **修复：** 改为 `def`（FastAPI 自动放入线程池），只有 health 端点保留 `async def`

#### Bug 9: 每个 token 触发 React 重渲染（Code Review 发现）
- **原因：** `syncToUI()` 每收到一个 token 就调 `setMessages`
- **修复：** `requestAnimationFrame` 节流，每帧最多更新一次

#### Bug 10: CORS 配置冲突（Code Review 发现）
- **原因：** `allow_origins=["*"]` + `allow_credentials=True` 冲突
- **修复：** `allow_credentials=False`

#### Bug 11: Agent 在模块 import 时创建（Code Review 发现）
- **修复：** 移到 FastAPI `lifespan` context manager 中创建，关闭时清理 SQLite 连接

### 9.2 SSE 断连丢失输出（2026-02-18）

- **现象：** 对话未结束时切换到其他会话，回来后 AI 回复不完整
- **原因：** `handleSelectSession` → `clearMessages()` → `abort()` SSE → 后端 `agent.stream()` 被中断 → checkpoint 不完整
- **修复：** 将 `agent.stream()` 解耦到独立线程（queue-based），客户端断开时设 `detached` flag 停止入队但 agent 继续跑完保存 checkpoint

### 9.3 Tavily 搜索失败（2026-02-18）

- **现象：** `ConnectionResetError(10054, '远程主机强迫关闭了一个现有的连接')`
- **原因双重：**
  1. 每次调用创建新 `TavilyClient`，多线程下 `requests.Session` 连接池竞争
  2. `api.tavily.com` 在中国大陆被 GFW 封锁
- **修复：** TavilyClient 改为线程安全单例；用户需开 VPN

### 9.4 多模型支持（2026-02-18）

- 新增 `AgentManager` 类：按 `model_name` 懒加载并缓存 agent 实例，多模型共享 store/checkpointer
- 所有 chat 端点新增 `model` 参数
- `GET /api/models` 返回可用模型列表（检测 API Key 是否配置）
- 前端 `ModelSelector` 组件放在输入框左下角，选择持久化到 localStorage

### 9.5 编辑重发功能（2026-02-18）

- 后端 `POST /api/chat/resend` 利用 LangGraph Time Travel（`get_state_history`）
- 前端 ChatMessage 用户消息 hover 显示编辑按钮
- useChat 中 `streamResponse()` 共享函数消除 `sendMessage` / `resendMessage` 的代码重复

### 9.6 Kimi/Qwen thinking 模式报错修复（2026-02-18）

- **现象：** Kimi K2.5 多轮工具调用后报 `thinking is enabled but reasoning_content is missing in assistant tool call message at index N`
- **根因：** `ChatOpenAI` 解析响应时静默丢弃 `reasoning_content` 字段（非 OpenAI 官方字段）。LangGraph 下一轮重放历史消息时，assistant 消息缺少 `reasoning_content`，Moonshot API 拒绝请求。
- **修复：** 通过 `extra_body` 关闭 thinking 模式。Moonshot 官方 API 用 `{"thinking": {"type": "disabled"}}`（注意：vLLM 自部署用 `chat_template_kwargs` 格式不同）。Qwen 用 `{"enable_thinking": False}`。同时设置 instant 模式推荐温度 0.6。
- **验证：** 四个模型分别多轮工具调用测试全部通过（DeepSeek 3轮10次、Kimi 2轮10次、Qwen 2轮2次、Claude 3轮7次）。
- **参考：** [langchain#35059](https://github.com/langchain-ai/langchain/issues/35059)、[langgraph#6521](https://github.com/langchain-ai/langgraph/issues/6521)

### 9.7 Claude content list 格式兼容（2026-02-18）

- **现象：** Claude 模型返回的消息在前端显示为 `[{'type': 'text', 'text': '...'}]` 原始格式
- **根因：** Anthropic 的 `AIMessage.content` 返回 `list[dict]`，OpenAI 兼容模型返回 `str`。代码中 `isinstance(content, str)` 判断会跳过或 `str()` 序列化 list
- **修复：** 新增 `_extract_text(content)` 统一提取函数，兼容 str 和 list 格式。应用于 stream.py（SSE 流式）、routes.py（历史加载、会话预览）、run.py（CLI 输出）三处

### 9.8 Python 代码执行工具（2026-02-18）

- 新增 `src/tools/code_runner.py`，`run_python` 工具注册到 Agent
- 无状态执行：每次 subprocess 独立进程，30秒超时，10K 字符输出限制
- 安装数据分析依赖：numpy, scipy, pandas, matplotlib
- 测试通过：基本计算、numpy、pandas、matplotlib 画图、scipy IRR、Agent 端到端自主调用

### 9.9 PDF 上传与解析功能（2026-02-18）

- 新增 `src/tools/pdf_parser.py`：MinerU API（云端 vlm）+ pdfplumber（本地）双引擎，自动降级
- 新增 `POST /api/upload/pdf` 端点：接收文件 → 解析 → 以 StoreBackend 格式存入 `/memories/documents/`
- 新增 `src/tools/pdf_reader.py`：CLI 场景直接读取本地 PDF 的工具
- MinerU API 测试：11页 PDF，8574 字符，约30秒完成，vlm 模式表格保留良好
- 存储兼容验证：Agent 通过 `ls("/memories/documents/")` 发现文件，`read_file` 正确读取内容
- key 前缀修复：StoreBackend 存储的 key 需以 `/` 开头（如 `/documents/xxx.md`），与 Agent 写入的文件格式一致
- memory_detail 端点兼容：支持 StoreBackend 格式（`content: [lines]`）和旧格式（`data: str`）
- **MinerU 重试机制（2026-02-19）：** 第 1 次失败 sleep 2s 后重试 1 次，两次都失败才降级 pdfplumber；pdfplumber 提取为空（扫描件）时返回 warning 明确告知用户
- **同名文件防冲突（2026-02-19）：** 上传时检测已有同名文件，内容不同则自动加序号（`报告.md` → `报告_2.md`），内容相同则原地覆盖更新时间戳

### 9.15 memory API key 前缀修复（2026-02-19）

- **现象：** 记忆面板点开文件内容全为空
- **根因：** Store 里 key 带前导 `/`（如 `/decisions/xxx.md`），FastAPI `{key:path}` 路由参数会吞掉前导 `/`，传给函数的是 `decisions/xxx.md`，`store.get` 匹配不上返回 `None`；前端拼 URL 时 key 也带 `/` 导致双斜杠
- **修复：**
  - 后端 `memory_detail`、`memory_update`、`memory_delete` 三个端点：收到 key 后补回前导 `/`
  - 前端 `getMemory`、`updateMemory`、`deleteMemory`：URL 拼接前去掉 key 的前导 `/`

### 9.16 多文件并行上传（2026-02-19）

- **交互：** 点击回形针按钮支持多选（最多 5 个），上传期间输入区显示"解析中 N 个文件..."；完成后各文件独立 chip 出现
- **附件上限：** 每次选 5 个（MinerU batch 限制），总附件上限 30 个，满后按钮变灰
- **后端新增 `POST /api/upload/pdfs`：**
  - 接收 `files: list[UploadFile]`（最多 5 个）
  - 调 `parse_pdfs_batch()` 批量解析
  - 返回 `{"results": [{ok, name, path, pages, method}, ...]}`
- **`parse_pdfs_batch()` 设计：**
  - 所有文件一个 MinerU batch 请求，一次轮询等所有结果
  - 用**数组索引**匹配结果（MinerU 返回 `file_name` 可能来自 PDF 元数据，不等于上传时的文件名）
  - `total_pages` 在 running 阶段缓存（done 后字段消失）
  - 单个文件失败独立降级 pdfplumber，不影响其他文件
  - 1 个文件时直接走单文件 `parse_pdf()`

### 9.17 doc/docx 上传支持（2026-02-19）

- MinerU 本身支持 `.doc/.docx/.ppt/.pptx` 等格式
- 新增 `_parse_with_docx()`：python-docx（已安装 1.2.0）提取段落文本，作为 docx 的本地降级方案
- 新增 `_local_fallback()`：根据文件扩展名选择本地降级（pdf → pdfplumber，docx → python-docx，doc → 无本地方案报错）
- 前端 `accept=".pdf,.doc,.docx"`，后端校验从 `.pdf` 放开到三种格式

### 9.18 记忆文件重命名（2026-02-19）

- **后端 `POST /api/memory/rename`：** 接收 `{old_key, new_name}`，保留目录路径只改文件名；自动补 `.md` 后缀；检测新名是否已存在；读旧内容 → 写新 key → 删旧 key → 更新索引
- **前端 MemoryPanel.tsx：** 右侧内容区顶部的文件路径标题改为可点击；点击后变为 input 编辑框（预填当前文件名），Enter 或失焦提交，Escape 取消；提交成功后左侧列表和 selectedKey 同步更新

### 9.19 百炼知识库本地上传管理（2026-02-19）

完整的知识库文件管理系统，用户不需要登录阿里云控制台即可直接在 Arcstone 内上传、查看、删除百炼知识库文档。

**后端 `src/tools/kb_uploader.py`（新增）：**

`BailianKBManager` 类封装百炼 6 步上传流程：

```
1. ApplyFileUploadLease  → 申请 OSS 预签名上传 URL（无需 OSS 配置）
2. PUT {presigned_url}   → 直接 PUT 文件字节到百炼 OSS
3. AddFile               → 注册文件到百炼，获取 file_id
4. 轮询 DescribeFile     → 等待 PARSE_SUCCESS（最多 5 分钟）
5. SubmitIndexAddDocumentsJob → 提交到指定索引，可传 chunk_size/overlap_size
6. 轮询 GetIndexJobStatus → 等待 COMPLETED（最多 10 分钟）
```

所有方法接受可选 `index_id` 参数，`_resolve_index()` fallback 到环境变量默认值。额外方法：`list_documents()`、`delete_documents()`、`retrieve()`。

**后端 API 端点（`src/api/routes.py` 扩展）：**

- `GET /api/kb/list` — 列出知识库文档（分页）
- `POST /api/kb/upload` — 接收文件，启动 background daemon thread 执行 6 步流程，立即返回 `{job_id}`
- `GET /api/kb/upload/status` — 查询 `_kb_jobs` 字典（`uploading/parsing/indexing/completed/failed`）
- `DELETE /api/kb/delete` — 删除指定文档 ID
- `GET /api/kb/rag/config` — 获取当前 RAG 配置
- `POST /api/kb/rag/config` — 更新 RAG 配置（同时调 `set_rag_kb_configs()`）

**状态存储：** 模块级内存字典 `_kb_jobs: dict[str, dict]`，字段：`{job_id, filename, status, progress, error, file_id, created_at}`。

**前端 `KnowledgeBasePanel.tsx`（新增）：**

- 右侧抽屉面板（与 MemoryPanel 同结构），通过侧边栏 Database 图标打开
- **多知识库切换：** 顶部知识库下拉选择器，点击切换当前活跃知识库（只影响文件列表和上传目标）
- **添加知识库：** 展开表单填写 `index_id`（必填）、名称、描述，添加后保存到 localStorage
- **删除知识库：** 鼠标悬停显示删除按钮，删除后自动切换到下一个
- **文件列表：** 展示文档名称、状态徽章（绿/黄/红）、修改时间，支持勾选删除
- **上传：** 支持百炼所有格式（PDF/DOCX/DOC/TXT/MD/PPTX/XLSX/HTML/图片），每 3 秒轮询状态更新，支持并发多任务
- **高级设置（折叠）：** chunk_size、overlap_size 输入

**Bug 修复 — FileList 引用被提前清除：**

用户选文件后无反应。根因：`e.target.value = ""`（清空 input 以支持重复选同一文件）在 `Array.from(files)` 之前执行，导致 FileList 引用失效，实际上传 0 个文件。修复：先 `const fileList = Array.from(e.target.files)` 保存副本，再清空 input。

**localStorage 持久化：**
- `arcstone-kb-configs`：知识库列表 `[{index_id, name, description}]`
- `arcstone-kb-active`：当前活跃知识库 ID
- App 启动时从 localStorage 自动同步到后端（防后端重启丢失配置）

### 9.20 多知识库 RAG 支持（2026-02-19）

`bailian_rag` 工具重构为支持同时检索多个知识库：

- **全局配置：** `_rag_kb_configs: list[dict]` + `threading.Lock`，线程安全读写
- **工具行为：** 遍历所有 `configs`，每个知识库独立调 `retrieve()`，结果以 `--- 来自知识库「name」---` 标注后合并返回
- **默认兜底：** 无配置时从 `BAILIAN_INDEX_ID` 环境变量初始化默认知识库
- **工具描述改为通用文本**（原为硬编码域名信息），不影响 Agent 行为但更灵活

**配置同步链路：**
```
localStorage(arcstone-kb-configs)
  → App 启动时 POST /api/kb/rag/config
  → set_rag_kb_configs(_rag_kb_configs)
  → bailian_rag 工具遍历所有配置检索
```

KnowledgeBasePanel 每次打开、添加/删除知识库时也触发同步，确保后端实时反映用户的知识库列表。

### 9.21 会话列表按时间排序（2026-02-19）

- **现象：** 会话列表按 UUID 字母顺序排列，不是按最近活跃时间
- **根因：** SQL 查询为 `SELECT DISTINCT thread_id FROM checkpoints ORDER BY thread_id`，UUID 无时间语义
- **修复：** 改为按 `checkpoint_id` 最大值排序。`checkpoint_id` 是 UUID v6/v7 格式，时间编码在前缀，MAX 字典序 = 最新 checkpoint：

```python
rows = conn.execute(
    "SELECT thread_id, MAX(checkpoint_id) AS last_cp "
    "FROM checkpoints GROUP BY thread_id ORDER BY last_cp DESC"
).fetchall()
for tid, _last_cp in rows:
    sessions.append(...)
```

最近有活动的会话排在列表最顶部。

### 9.13 前端 PDF 上传 UI + 附件暂存（2026-02-19）

- **交互流程（ChatGPT/Kimi 模式）：**
  1. 用户点击回形针按钮选择 PDF → 后端解析
  2. 解析成功 → 文件作为"附件标签"出现在输入框上方（文件名 + 页数 + X 关闭）
  3. 可连续上传多个文件，标签累积
  4. 用户输入文字后按发送 → 附件信息 + 用户文字一起发给 Agent
  5. 仅有附件无文字也可发送

- **ChatInput.tsx 改动：**
  - 新增 `Attachment` 接口（name / pages / path）和 `attachments` / `onRemoveAttachment` props
  - `onSend` 签名变为 `(message, attachments?) => void`
  - 输入框上方新增附件标签区（`FileText` 图标 + 文件名 + 页数 + X 关闭按钮）
  - 有附件时即使无文字，发送按钮也高亮可用

- **App.tsx 改动：**
  - 新增 `attachments` state，`handleUploadPdf` 上传成功后追加到列表（不自动发送）
  - `handleSend` 将附件信息以 `[上传文件] xxx（N页），已保存到 path` 格式拼入消息文本前部
  - 发送后 / 新建会话 / 切换会话时清空 attachments

- **Agent 侧适配：** `src/agent/prompts.py` 新增"文件上传处理"规则：收到 `[上传文件]` 消息后简短确认收到，不主动分析，等用户指示

### 9.14 记忆面板可视化管理（2026-02-19）

- **MemoryPanel.tsx 完全重写**：720px 双栏布局
  - 左栏（260px）：5 组分组列表（用户画像 / 项目 / 决策 / 文档 / 其他），可折叠，`index.md` 隐藏不展示
  - 右栏（460px）：Markdown 渲染查看（react-markdown + remarkGfm）+ 编辑模式（textarea + 保存/取消）+ 内联删除确认（3 秒自动收回）
- **后端新增端点：** `PUT /api/memory/{key}` 更新内容、`DELETE /api/memory/{key}` 删除文件
- **前端 API 新增：** `updateMemory(key, content)`、`deleteMemory(key)`
- **Playwright 自动化测试：** `tests/test_frontend_ui.py`，10 项检查全部通过

### 9.10 记忆索引系统 index.md（2026-02-18）

- **问题：** Agent 首轮盲读固定文件（user_profile + instructions），对自己记了什么没有"目录感"，随记忆增长浪费 token
- **方案：** 新增 `/memories/index.md` 索引文件，Agent 首轮只读索引即可知道所有记忆概况
- **改动：**
  - `src/agent/prompts.py`：首轮读取改为 index.md + user_profile.md + instructions.md 三件套，新增"维护索引"规则
  - `src/api/routes.py`：新增 `_update_memory_index()` 辅助函数 + `_INDEX_TEMPLATE`；`upload_pdf` 端点自动写入索引条目
- **索引维护：** Agent 实时维护（每次 write_file 后更新）+ 后端保证（PDF 上传后自动写入）
- **验证：** Agent 首轮正确执行 3 次 read_file（index.md → user_profile → instructions），PDF 上传后索引自动生成
- **设计文档：** `docs/plans/2026-02-18-memory-index-design.md`

### 9.11 规划层 Planning（2026-02-18）

- **问题：** Agent 没有显式规划能力，复杂任务（如全面评估矿山）靠 System Prompt 隐式引导，容易漏步骤、顺序乱、长对话中目标偏移
- **调研：** 综合 Lilian Weng（任务分解+反思）、Anthropic（6种工作流模式）、Manus（Todo-list 注意力锚定+上下文工程）、学术前沿（AOP 三原则）的最佳实践
- **方案：** 3 层递进，不涉及架构改动：
  - **L1 Prompt 引导规划 + 任务路由：** 在 System Prompt 新增"工作方法"章节，教模型区分 4 种任务类型（简单问答/单项分析/多步评估/对比决策），复杂任务先列 3-5 步计划再逐步执行
  - **L2 Todo-list 注意力锚定：** Deep Agents 内置 `TodoListMiddleware`，自动提供 `write_todos` 工具（`{"content": str, "status": "pending|in_progress|completed"}`），框架自带完善的引导 prompt，无需额外开发
  - **L3 执行后自检：** 多步分析完成后，模型自检覆盖完整性、数据来源、结论一致性、遗漏风险
- **改动：** `src/agent/prompts.py`：在"工具使用指南"和"记忆管理"之间插入完整的"工作方法"章节
- **验证（场景 1 通过）：** 简单问答（"JORC标准是什么"）Agent 不列计划，直接查 RAG 后回答。场景 2-4 由用户手动测试。
- **调研报告：** `docs/research/agent-planning-research.md`
- **设计文档：** `docs/plans/2026-02-18-planning-layer.md`

### 9.12 记忆语义检索系统（2026-02-18）

- **问题：** 记忆文件增多后纯目录式检索（index.md + Agent 按文件名判断）会漏掉相关内容；Agent 需要逐个读文件猜内容，token 浪费
- **方案：** DashScope text-embedding-v3（1024维）向量检索 + SQLite FTS5 BM25 关键词混合检索，jieba 中文分词解决 FTS5 对中文无效的问题
- **新增文件：**
  - `src/memory_search.py`：`MemorySearchEngine` 核心类，共享 SqliteStore 的 sqlite3 连接，管理 `embeddings` 表（向量）和 `fts_memory` 表（分词后全文）
  - `src/tools/memory_search.py`：Agent 工具 `memory_search(query, top_k=5)`，返回文件路径 + 相关度 + 摘要
- **改动文件：**
  - `src/store.py`：`__init__` 初始化 `search_engine`；`_handle_put` 写入 `("filesystem",)` 时 hook 触发索引更新/删除
  - `src/agent/main.py`：tools 列表加 `memory_search`
  - `src/agent/prompts.py`：工具指南加第 4 条；记忆读取流程改为 read_file 三件套 + memory_search 语义搜索两步并行
  - `src/api/app.py`：lifespan 中注册全局 engine + 启动时 backfill
- **关键设计：**
  - `text_hash`（SHA256[:16]）变更检测：内容不变不调 API，节省费用
  - `force_fts=True`：backfill 时 embedding 可跳过（hash 未变），FTS 强制刷新（分词器升级时用）
  - `/index.md` 在 `_SKIP_KEYS` 中，不参与语义索引
  - embedding 失败只 log，不阻塞写入
  - jieba `cut_for_search` 模式：长词拆短词（"资源量"→"资源"+"资源量"），提升召回
- **混合检索权重：** cosine 70% + BM25 30%
- **依赖：** `openai`（DashScope 兼容接口）、`numpy`、`jieba`（新增，`pip install jieba`）
- **已知局限：** BM25 对纯英文关键词（IRR、JORC）效果好，jieba 对专业矿业术语分词可能不准（无自定义词典）
- **优化路线图：** `docs/plans/memory-system-roadmap.md`（P0 结构化提取 → P1 冲突检测 → P2 衰减 → P3 UI → P4 主动触发）

---

## 十、开发进度

### 已完成

- [x] 需求分析与 9 篇架构设计文档
- [x] 框架选型：Deep Agents 0.4.1
- [x] 百炼 Retrieve API 联调验证
- [x] MVP：Agent + 3 个工具 + 流式终端 CLI
- [x] 记忆层：SqliteStore + CompositeBackend + 归档功能
- [x] 多轮对话支持（checkpointer）
- [x] 跨会话记忆（/memories/ 持久化）
- [x] Checkpointer 持久化（SqliteSaver → SQLite，跨重启保留对话历史）
- [x] StoreBackend namespace 显式化
- [x] FastAPI 后端 API + SSE 流式输出
- [x] Electron + React 桌面前端（Claude-like 设计）
- [x] Segment-based 消息模型（文字/工具调用交替顺序正确）
- [x] 会话管理（新建/列表/重命名/删除）
- [x] 记忆面板（右侧抽屉查看 /memories/ 内容）
- [x] 智能滚动（不打断用户浏览历史）
- [x] 编辑重发（LangGraph Time Travel）
- [x] 多模型支持（DeepSeek / Kimi / Qwen / Claude，前端切换）
- [x] SSE 断连解耦（agent 后台跑完，切回可见完整回复）
- [x] Tavily 搜索线程安全修复
- [x] Code Review 驱动的性能/安全修复（rAF 节流、CORS、lifespan 等）
- [x] Kimi/Qwen thinking 模式修复（关闭 reasoning，四模型全测试通过）
- [x] Claude content list 格式兼容（`_extract_text` 统一提取）
- [x] Python 代码执行工具（run_python，subprocess 无状态）
- [x] PDF 读取工具（read_pdf，pdfplumber，CLI 用）
- [x] PDF 上传解析功能（MinerU API + pdfplumber 降级，存入 memories）
- [x] 记忆索引系统（index.md，Agent 首轮读索引按需加载，后端 PDF 上传自动写索引）
- [x] 规划层 Planning（Prompt 引导规划 + 任务路由 + Todo-list 注意力锚定 + 执行后自检）
- [x] 记忆语义检索（DashScope Embedding 1024维 + FTS5 BM25 + jieba 中文分词，混合检索 70/30）
- [x] 前端 PDF 上传 UI（附件暂存模式，回形针按钮，多文件累积，随消息一起发送）
- [x] 记忆面板可视化管理（720px 双栏，分组列表，Markdown 渲染，编辑/删除）
- [x] PDF 解析 MinerU 重试机制（失败重试 1 次，扫描件空内容提示）
- [x] 同名文件上传防冲突（内容不同自动加序号）
- [x] memory API key 前缀修复（记忆面板内容读取/编辑/删除全部修复）
- [x] 多文件并行上传（每次最多 5 个，总上限 30，MinerU 批量 batch，索引匹配改用数组顺序）
- [x] doc/docx 上传支持（MinerU + python-docx 降级，前后端均放开文件类型限制）
- [x] 记忆文件重命名（点击文件名内联编辑，后端读旧写新删旧）
- [x] 百炼知识库本地上传管理（6步流程：租约→OSS PUT→AddFile→轮询解析→提交索引→轮询完成）
- [x] 多知识库 RAG 支持（全局 `_rag_kb_configs` 配置，bailian_rag 工具遍历所有知识库汇总结果）
- [x] KnowledgeBasePanel 前端面板（添加/删除/切换知识库，文件列表，上传进度轮询，localStorage 持久化）
- [x] KB 配置启动同步（App 启动时从 localStorage 同步到后端，防后端重启丢失）
- [x] 会话列表按时间排序（按 checkpoint_id MAX 排序，最近活跃在最顶部）

### 未开始

- [ ] Human-in-the-Loop（interrupt_on 中断/恢复）
- [ ] 子代理精细化（researcher / calculator / comparator，目前 Agent 自主创建 subagent）
- [ ] 敏感性分析工具
- [ ] 多模型 A/B 测试
- [ ] Tavily 服务端代理（解决客户无 VPN 问题）
- [ ] read_pdf 智能分流（短 PDF 主 Agent 读，长 PDF sub-agent 分段读取总结）

### 已知问题

1. **DeepSeek 偶尔重复输出：** 已通过 `frequency_penalty=0.3` 缓解，但长回复仍可能出现
2. **记忆写入依赖 LLM 自觉：** Agent 不一定每次都主动写入，归档功能（`/archive`）作为兜底
3. **Tavily 需要 VPN：** 中国大陆无法直接访问 `api.tavily.com`
4. **SQLite 并发写安全：** SqliteStore 在多线程高并发写入时可能出现 `database is locked`，后续可加 threading.Lock
5. **MinerU API key 90天有效期：** 打包给客户后需要续期方案，目前自动降级到 pdfplumber 兜底
6. **PDF 上传不支持图片：** 存入 memories 的是纯文本 markdown，PDF 中的图片不保留
7. **read_file 默认100行限制：** Deep Agents 框架限制，长 PDF 转换后 Agent 需翻页读取（offset/limit），或用 grep 搜索关键词

---

## 十一、开发规则

1. **Python 环境：** 必须用 `"D:/miniconda/envs/miner-agent/python.exe"` 全路径调用
2. **禁止垃圾增量代码：** 不叠 if 补丁、不留废弃变量、不加 TODO 注释。想清楚逻辑再改
3. **查文档再写代码：** deepagents 是 2025 年新库，API 必须查官方文档确认
4. **Code Review：** 每完成一个重要功能后用 code-reviewer 检查
