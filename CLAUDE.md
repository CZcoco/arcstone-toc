# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 提供操作本代码仓库的指引。

## 项目概述

`econ-agent` 是一个基于 LangChain Deep Agents 的经济学论文 AI 助手，面向国内本科经济学生，协助完成选题、文献综述、数据获取、实证分析和 Word 论文生成等毕业论文全流程。

## 架构

```
用户 (Electron/Web) → FastAPI + SSE → create_econ_agent()
                                      ├── 工具: 搜索、Python、PDF、记忆
                                      ├── topic-agent (选题策划)
                                      ├── literature-agent (文献检索)
                                      ├── empirical-agent (回归/分析)
                                      └── writing-agent (文档生成)
```

**关键架构决策：**

- **Agent 框架**: Deep Agents 0.4.1 + LangGraph，支持会话状态持久化 (checkpointing)
- **记忆存储**: 双 SQLite 数据库 - `memories.db`（语义检索 + FTS5 全文搜索）和 `checkpoints.db`（会话状态）
- **虚拟路径**: 通过 `CompositeBackend` 映射的三类文件系统后端：
  - `/memories/` → `SqliteStore`（持久化记忆）
  - `/skills/` → 只读技能脚本目录
  - `/workspace/` → 用户工作区目录
- **流式输出**: 通过 `/api/chat/stream` 提供 SSE 流式响应，事件类型包括：`token`、`tool_start`、`tool_end`、`error`、`complete`

## 仓库与发布

- **ToC 版仓库**：`https://github.com/CZcoco/arcstone-toc.git`（当前活跃）
- 原版仓库：`https://github.com/CZcoco/econ-agent-build`（v0.6.6 存档）
- 当前可用 GitHub 账号：`Yonder-Solivagant`

## 开发环境

**Python 环境**：使用 conda `miner-agent` 环境（`D:/miniconda/envs/miner-agent/python.exe`）

```bash
# 激活环境（Windows cmd）
conda activate miner-agent

# 或直接用绝对路径
D:/miniconda/envs/miner-agent/python.exe run.py
```

## 常用命令

### 开发

```bash
# 终端模式（无前端界面）
python run.py [MODEL_NAME]  # MODEL_NAME: deepseek-chat（默认）, 或 New API 中的任意模型 ID

# 仅启动 API 服务
python run_api.py  # 端口从 ARCSTONE_ECON_API_PORT 读取或自动分配

# 前端开发
cd frontend
npm install
npm run dev          # Vite 开发服务器运行于 :5173
npm run electron:dev # Electron 热重载模式

# 前端构建
cd frontend
npx tsc -b && npx vite build  # TypeScript 检查 + 构建

# 后端可执行文件（Windows）
build_backend.bat  # 需要 PyInstaller，输出 dist/backend/backend.exe
```

### 环境配置

```bash
# 关键变量（ToC 版）：
# - ECON_USER_TOKEN（New API 用户 token，登录后自动设置）
# - NEW_API_URL（默认 http://43.128.44.82:3000/v1）
# - TAVILY_API_KEY（联网搜索）
```

## 关键文件位置

| 用途 | 路径 |
|---------|------|
| Agent 工厂 | `src/agent/main.py` (`create_econ_agent()`) |
| 系统提示词 | `src/agent/prompts.py` (ECON_SYSTEM_PROMPT + 4 个子 Agent) |
| 模型配置 | `src/agent/config.py` (`NEW_API_BASE_URL`, `get_llm()`) |
| FastAPI 应用 | `src/api/app.py` (`AgentManager`, lifespan) |
| API 路由 | `src/api/routes.py` |
| 认证服务 | `src/api/auth.py` (`quick_start()`, `get_user_info()`) |
| 前端认证 | `frontend/src/lib/auth.ts`, `frontend/src/hooks/useAuth.ts` |
| 登录页面 | `frontend/src/components/AuthScreen.tsx` |
| 工具注册 | `src/tools/` |
| 技能模块 | `skills/literature/`, `skills/data/` |
| 前端入口 | `frontend/src/App.tsx` |
| Electron 主进程 | `frontend/electron/main.cjs` |

## 数据与安装隔离

本项目使用 `econ-agent` 品牌标识，与旧版 `Arcstone` 项目完全隔离：

- **开发数据**: `./data/` (memories.db, checkpoints.db, workspace/)
- **生产数据**: `%APPDATA%/econ-agent/data/`
- **环境变量前缀**: `ARCSTONE_ECON_USER_DATA`, `ARCSTONE_ECON_INSTALL_ROOT`
- **localStorage 键名**: `econ-agent-*`

从旧版路径的数据迁移在 `src/api/app.py` 的 lifespan 中自动完成。

详细环境边界、非 git 但必须统一的配置，以及 embedded Python / uv / pip 的职责说明见：`用户环境.md`。

## 测试
```bash
# Playwright UI 测试（需要先启动开发服务器）
python tests/test_frontend_ui.py
```

## 模型配置（ToC 版）

所有 LLM 调用统一走 **New API**（OpenAI 兼容格式），模型列表从 `/v1/models` 动态获取。

- **New API 服务器**：`http://43.128.44.82:3000`
- **认证**：每用户独立 token（登录时自动创建），存 `ECON_USER_TOKEN` 环境变量
- **Token 获取**：`POST /api/token/` → `GET /api/token/` → `POST /api/token/:id/key`
- **当前可用模型**：`deepseek-chat`（默认）、`deepseek-reasoner`、`qwen-plus`、`qwen-turbo`、`glm-5`、`kimi-k2.5`
- **添加模型**：在 New API 后台添加渠道，客户端自动出现

## 规则与准则

1. **参考文献零幻觉**: 只引用通过 `literature-agent` 验证的真实文献（OpenAlex/Semantic Scholar）
2. **实证数据零编造**: 所有回归结果必须来自实际的 `run_python` 执行
3. **数据可追溯**: 变量来源、脚本、输出文件路径必须清晰可查
4. **品牌一致性**: 用户可见字符串使用 `econ-agent`，不使用 `Arcstone`

## 开发注意

- `ModelSelector` 从 New API 动态获取模型列表，无硬编码。始终显示当前模型，多于 1 个时显示下拉箭头
- 设置面板保存后自动刷新模型列表（通过 `modelRefreshKey` 触发）
- **Clash TUN 模式兼容**：`run_api.py` 启动时会清理 `HTTP_PROXY`/`HTTPS_PROXY` 环境变量，避免本地连接被代理干扰
- **生产版设置路径**：安装版优先读取 `%APPDATA%/econ-agent/data/settings.json`；开发环境 fallback 才是仓库内 `./data/settings.json`
- **API 重试**：`stream.py` 对 `httpx.TimeoutException`/`HTTPStatusError` 自动重试 3 次（指数退避 1s/2s/4s）
- **RAG 代理模式**：`src/tools/rag.py` 通过 HTTP 请求服务端代理，不再依赖客户端百炼 SDK
- **最终用户 Python 运行时**：v0.6.x 延续 Python 3.12 embedded runtime 作为产品运行时本体；uv 仅负责向该解释器安装依赖，pip 为 fallback
- **首启依赖策略**：`src/api/dependency_installer.py` 将 startup 依赖与 optional 扩展分层；用户首启只安装最小启动集，可选能力缺失时不应阻塞应用启动

## ToC 改造进度

详细改动记录见 `docs/TOC_CHANGELOG.md`，完整计划见 `docs/TOC_PLAN.md`。

- [x] **Phase 0+1**：统一 New API 模式（已完成 2026-03-24）
- [x] **Phase 2**：登录门控 + 每用户独立 Token（已完成 2026-03-24）
- [ ] **Phase 2.5**：接入支付（微信/支付宝 → New API 用户充值）
- [ ] **Phase 3**：新手引导、论文模板、品牌更新

## 版本记录

### v0.7.1-toc (2026-03-24)

- **登录门控**：首次输入用户名+密码 → 自动注册+登录 → 存本地 → 以后自动进
- **每用户独立 Token**：通过 `POST /api/token/:id/key` 获取明文 key，New API 服务端按用户扣费
- **AuthMiddleware**：未登录请求返回 401
- **Sidebar 用户信息**：显示用户名、余额、充值/退出按钮

### v0.7.0-toc (2026-03-24)

- **统一 New API 模式**：删除 8 个中转站硬编码，所有 LLM 调用走 `http://43.128.44.82:3000/v1`
- **动态模型列表**：从 New API `/v1/models` 拉取，后台加模型客户端自动出现
- **RAG 代理化**：知识库检索改为 HTTP 请求服务端代理，客户端无需百炼 SDK
- **API 重试**：stream.py 加入 3 次指数退避重试
- **启用 literature-agent**：恢复文献检索子 agent
- **精简设置**：11 个 API Key → 2 个字段

### v0.6.6 (2026-03-20)

- 工作区面板增强、会话工作区绑定与并发隔离

### v0.6.0 (2026-03-15)

- **在线安装版**：安装包从 ~410MB 降至 ~110MB
- **uv 支持**：优先使用 uv 安装依赖（比 pip 快 10-100 倍），失败自动降级到 pip
