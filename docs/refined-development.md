# econ-agent 开发速查手册

> 最后更新：2026-03-06 | 详细架构见 `docs/econ/architecture.md`

---

## 项目一句话

`econ-agent` 是一个经济学论文智能体。目标用户是国内本科经济学生，输入一个研究方向后，智能体能够协助完成选题、文献综述、数据获取、实证分析和 Word 论文生成。

---

## 当前状态

这个仓库来自原矿业项目 `Arcstone`，但现在已经作为独立新项目继续维护，当前运行时主身份是经济学论文场景。

已经完成的切换：
- `src/agent/main.py` 使用 `create_econ_agent()`
- `src/agent/prompts.py` 已替换为经济学论文主 Prompt + 4 个 sub-agent Prompt
- `skills/literature` 和 `skills/data` 已成为核心业务技能
- 前端、记忆、SSE、工作区、知识库、设置系统全部沿用原基础设施

隔离要求：
- 环境变量使用 `ECON_AGENT_USER_DATA`
- 打包数据目录使用 `%APPDATA%/econ-agent/data/`
- localStorage key 使用 `econ-agent-*`

这个项目不再与旧 `Arcstone` 安装数据目录共用路径。

---

## 技术栈速查

| 层 | 方案 |
|---|---|
| Agent 框架 | Deep Agents 0.4.1 + LangGraph |
| 模型 | DeepSeek V3.2 / Claude / Kimi / Qwen |
| 后端 | FastAPI + Uvicorn，SSE 流式，端口 8000 |
| 前端 | Electron + React 18 + Vite + Tailwind |
| 记忆存储 | `SqliteStore` → `data/memories.db` |
| 记忆检索 | embedding + FTS5 BM25 + jieba |
| 会话检查点 | `SqliteSaver` → `data/checkpoints.db` |
| 工作区 | `data/workspace/` 或用户自定义目录 |
| 核心外部能力 | 百炼知识库、联网搜索、Python 执行、PDF/图片读取 |

---

## 核心文件

```text
src/
├── agent/
│   ├── config.py          # 模型配置
│   ├── main.py            # create_econ_agent() + DATA_DIR/SKILLS_DIR
│   └── prompts.py         # 经济学论文主 Prompt + 4 个 sub-agent Prompt
├── api/
│   ├── app.py             # FastAPI 入口 + AgentManager + 启动迁移逻辑
│   ├── routes.py          # 全部 HTTP 路由
│   └── stream.py          # SSE 流式封装
├── tools/
│   ├── code_runner.py     # run_python
│   ├── pdf_reader.py      # read_pdf
│   ├── read_image.py      # read_image
│   ├── search.py          # internet_search / fetch_website
│   ├── rag.py             # bailian_rag
│   ├── path_resolver.py   # /workspace/ /skills/ 虚拟路径转换
│   └── memory_search.py   # Agent 工具层记忆检索
├── memory_search.py       # 全局搜索引擎
├── settings.py            # settings.json 管理
└── store.py               # SqliteStore

skills/
├── literature/            # OpenAlex / Semantic Scholar 文献检索
├── data/                  # World Bank / NBS / FRED / IMF / Comtrade
├── pdf/                   # 复用型 PDF skill
└── xlsx/                  # 复用型 Excel/Word skill

frontend/
├── electron/main.cjs      # Electron 主进程
├── src/App.tsx            # 主界面
└── package.json           # 打包配置
```

---

## 业务架构

### 主 Agent

`create_econ_agent()` 当前挂载：
- `bailian_rag`
- `internet_search`
- `fetch_website`
- `run_python`
- `read_pdf`
- `read_image`
- `memory_search`

### 4 个 subagents

| 名称 | 作用 | 主要工具 |
|---|---|---|
| `topic-agent` | 选题策划 | `internet_search` / `fetch_website` / `bailian_rag` / `run_python` |
| `literature-agent` | 文献检索与综述 | `internet_search` / `fetch_website` / `bailian_rag` / `run_python` |
| `empirical-agent` | 实证分析 | `run_python` / `read_image` |
| `writing-agent` | 论文写作与 Word 生成 | `run_python` / `read_image` / `read_pdf` |

### 典型流程

1. 用户给研究方向。
2. `topic-agent` 提供 2-3 个本科可做选题。
3. `literature-agent` 检索真实文献并生成综述草稿。
4. 主 Agent 或 `empirical-agent` 拉数据、清洗、回归、出图。
5. `writing-agent` 汇总结果，输出论文和 `.docx`。

---

## 论文场景红线

1. 参考文献零幻觉：只引用通过脚本验证有真实记录的文献。
2. 实证零编造：所有系数、显著性、样本量必须来自真实运行结果。
3. 数据透明：变量来源、脚本来源、输出文件路径必须可追溯。

---

## 记忆与文件系统

### 虚拟路径

| 虚拟路径 | 实际含义 |
|---|---|
| `/memories/` | 跨会话持久化记忆 |
| `/skills/` | 只读技能目录 |
| `/workspace/` | 用户可见工作区 |

### 记忆机制

```text
write_file("/memories/xxx.md")
  → StoreBackend
  → SqliteStore
  → MemorySearchEngine 建 embedding + FTS 索引

memory_search("数字经济 就业")
  → 语义召回 + BM25
  → 返回 top-K 文件路径和摘要
```

### 默认记忆文件

```text
/memories/index.md
/memories/user_profile.md
/memories/instructions.md
```

每次对话首轮都应先读这三类内容，再按需搜索/精读。

---

## API 速查

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| GET | `/api/models` | 可用模型 |
| POST | `/api/chat/stream` | SSE 流式对话 |
| POST | `/api/chat/resend` | 编辑重发 |
| POST | `/api/chat/cancel` | 取消生成 |
| GET | `/api/session/list` | 会话列表 |
| GET | `/api/session/{id}` | 会话历史 |
| GET | `/api/memory/list` | 记忆文件列表 |
| POST | `/api/upload/pdfs` | 批量上传 PDF/Word/MD |
| POST | `/api/upload/image` | 上传图片 |
| POST | `/api/upload/excel` | 上传 Excel |
| GET | `/api/workspace` | 工作区状态 |
| POST | `/api/workspace/set` | 切换工作区 |
| GET | `/api/settings` | 当前设置 |
| PUT | `/api/settings` | 更新设置 |
| GET | `/api/system-prompt/versions` | 提示词版本列表 |
| GET | `/api/skills` | 技能列表 |

---

## 前端现状

当前前端能力：
- 会话管理
- 编辑重发
- 文件附件卡片持久化
- 记忆面板
- 知识库面板
- 技能面板
- 设置面板
- 工作区面板

需要注意：
- 打包品牌、`userData` 路径和 localStorage key 现在都应该保持 `econ-agent` 命名
- 如果再改产品名，需要连同 Electron `userData`、安装包产物名和 Python 环境变量一起迁移

---

## 开发规则

1. 优先以 `docs/econ/architecture.md` 为业务架构基准，不再以旧矿业文档为准。
2. 改动业务逻辑时，优先检查 `src/agent/prompts.py`、`src/agent/main.py`、`skills/` 是否一致。
3. 旧的 `Arcstone` 命名如果出现在用户可见界面、打包配置、环境变量或本地存储 key，应直接替换掉。
4. 不要重新引入矿业领域术语到 prompt、README 或前端默认文案。

---

## 已知遗留项

| 类型 | 现状 |
|---|---|
| 品牌遗留 | 旧 `Arcstone` 名称仍可能散落在历史文档和注释中 |
| 旧文档遗留 | `docs/` 下大量矿业设计稿还在，仅作历史参考 |
| 路径隔离 | 当前项目应只使用 `%APPDATA%/econ-agent` |
| Git 环境 | 当前仓库有 dubious ownership，直接跑 `git` 会报 safe.directory 错误 |

---

## 改造优先级建议

1. 先统一用户可见身份：README、窗口标题、侧边栏、输入框、终端标题。
2. 再处理开发文档：`refined-development.md`、对外说明、安装文案。
3. 最后再清理历史文档和示例里的旧品牌名。
