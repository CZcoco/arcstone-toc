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

## 常用命令

### 开发

```bash
# 终端模式（无前端界面）
python run.py [MODEL_NAME]  # MODEL_NAME: deepseek, claude-sonnet, kimi, gpt

# 仅启动 API 服务
python run_api.py  # 端口从 ARCSTONE_ECON_API_PORT 读取或自动分配

# 前端开发
cd frontend
npm install
npm run dev          # Vite 开发服务器运行于 :5173
npm run electron:dev # Electron 热重载模式

# 生产构建
cd frontend
npm run build           # 构建前端资源
npm run electron:build  # 构建 Electron 安装包

# 后端可执行文件（Windows）
build_backend.bat  # 需要 PyInstaller，输出 dist/backend/backend.exe
```

### 环境配置

```bash
# 复制并填写环境变量
cp .env.example .env

# 关键变量：
# - DEEPSEEK_API_KEY / MOONSHOT_API_KEY / ANTHROPIC_API_KEY
# - TAVILY_API_KEY（联网搜索）
# - ALIBABA_CLOUD_ACCESS_KEY_ID + BAILIAN_WORKSPACE_ID（RAG 知识库）
```

## 关键文件位置

| 用途 | 路径 |
|---------|------|
| Agent 工厂 | `src/agent/main.py` (`create_econ_agent()`) |
| 系统提示词 | `src/agent/prompts.py` (ECON_SYSTEM_PROMPT + 4 个子 Agent) |
| 模型配置 | `src/agent/config.py` (`MODEL_CONFIG`, `get_llm()`) |
| FastAPI 应用 | `src/api/app.py` (`AgentManager`, lifespan) |
| API 路由 | `src/api/routes.py` |
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

## 测试

```bash
# Playwright UI 测试（需要先启动开发服务器）
python tests/test_frontend_ui.py
```

## 模型配置

`src/agent/config.py` 中定义的可用模型：
- `deepseek` (DeepSeek V3.2) - 默认模型
- `claude-opus`, `claude-sonnet` (Anthropic 通过代理)
- `claude-opus-plan`, `claude-sonnet-plan` (订阅端点)
- `kimi` (Moonshot K2.5)
- `gpt` (GPT-5.4 通过代理)

## 规则与准则

1. **参考文献零幻觉**: 只引用通过 `literature-agent` 验证的真实文献（OpenAlex/Semantic Scholar）
2. **实证数据零编造**: 所有回归结果必须来自实际的 `run_python` 执行
3. **数据可追溯**: 变量来源、脚本、输出文件路径必须清晰可查
4. **品牌一致性**: 用户可见字符串使用 `econ-agent`，不使用 `Arcstone`

## 开发注意

- `ModelSelector` 应始终显示当前模型（即使只有一个可用），仅在有多个模型时显示下拉箭头
- 设置面板保存 API Key 后自动刷新模型列表（通过 `modelRefreshKey` 触发）
- **Clash TUN 模式兼容**：`run_api.py` 启动时会清理 `HTTP_PROXY`/`HTTPS_PROXY` 环境变量，避免本地连接被代理干扰
- **生产版设置路径**：安装版优先读取 `%APPDATA%/econ-agent/data/settings.json`；开发环境 fallback 才是仓库内 `./data/settings.json`
- **Claude API 线路**：`claude-opus` / `claude-sonnet` 使用 `ANTHROPIC_AUTH_TOKEN`，当前走 `https://apicn.ai`，实测 Anthropic 兼容接口可返回 200
- **GPT 中转结论**：`https://chat.apiport.cc.cd/v1` 对应的 GPT 路线当前存在不稳定现象；`http://106.53.52.4` 及 `/v1` 当前不可用（80 拒绝连接，443 超时）
- **打包注意**：后端配置变更后必须先重建 `dist/backend/backend.exe`，再执行 `frontend/npm run electron:build`；否则安装包可能仍包含旧后端逻辑
