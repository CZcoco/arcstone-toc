# ToC 改造变更记录

> 记录 econ-agent 从单用户桌面版向 ToC 付费产品的改造过程。

## Phase 0+1：统一 New API 模式（2026-03-24）

### 服务端

- **New API 部署**：阿里云香港轻量服务器 `43.128.44.82:3000`
  - Docker 镜像：`calciumion/new-api:latest`
  - 已配置模型：`deepseek-chat`, `deepseek-reasoner`, `qwen-plus`, `qwen-turbo`
  - 管理后台：`http://43.128.44.82:3000`
- **RAG 代理**：待部署（代码已准备，见下方"待完成"）

### 客户端代码改动

| 文件 | 改动 | 说明 |
|------|------|------|
| `src/agent/config.py` | **重写** (295→35行) | 删除 8 个中转站硬编码、`CompatChatOpenAI`、`ModelConfigEntry`、`AnthropicFactory`/`OpenAIFactory`，统一 `ChatOpenAI` + `NEW_API_BASE_URL` |
| `src/agent/main.py` | 修改 | 启用 `literature-agent` 子 agent；默认模型改为 `deepseek-chat` |
| `src/api/stream.py` | 修改 | 添加 API 重试逻辑（3 次指数退避，捕获 `httpx.TimeoutException`/`HTTPStatusError`）；默认模型改为 `deepseek-chat` |
| `src/tools/rag.py` | **重写** (103→35行) | 从客户端直连百炼改为 HTTP 请求到服务端 RAG 代理；删除 `BailianKBManager` 依赖 |
| `src/settings.py` | 修改 | `SETTINGS_SCHEMA` 从 11 个 API Key 字段精简为 2 个：`NEW_API_URL`、`TAVILY_API_KEY` |
| `src/api/app.py` | 修改 | `available_models()` 从遍历 `MODEL_CONFIG` 改为调用 New API `/v1/models`；删除 `BailianKBManager` 初始化；默认模型改为 `deepseek-chat` |
| `src/api/routes.py` | 修改 | KB 管理路由（`/kb/rag/config`）改为空实现；settings 更新逻辑简化；所有默认模型改为 `deepseek-chat` |
| `frontend/src/components/ModelSelector.tsx` | **重写** (155→83行) | 删除 `MODEL_LABELS`、`MODEL_FALLBACKS`、`MODEL_PRIORITY` 硬编码，改为从 API 动态获取模型列表 |
| `frontend/src/App.tsx` | 修改 | 默认模型从 `gpt` 改为 `deepseek-chat` |
| `run.py` | 修改 | 默认模型改为 `deepseek-chat` |

### 环境变量变化

| 变量 | 状态 | 说明 |
|------|------|------|
| `ECON_USER_TOKEN` | **新增** | New API 的用户 token（`sk-...` 格式），登录后自动设置 |
| `NEW_API_URL` | **新增** | New API 服务器地址，默认 `http://43.128.44.82:3000/v1` |
| `RAG_PROXY_URL` | **新增** | RAG 代理地址，默认 `http://43.128.44.82:3000/rag/retrieve` |
| `ANTHROPIC_AUTH_TOKEN` | 删除 | 不再需要 |
| `ANTHROPIC_HON_TOKEN` | 删除 | 不再需要 |
| `ANTHROPIC_SUB_TOKEN` | 删除 | 不再需要 |
| `OPENAI_API_KEY` | 删除 | 不再需要 |
| `MODEL_API_KEY` | 删除 | 不再需要 |
| `ALIBABA_CLOUD_*` | 删除 | 迁移到服务端 |
| `BAILIAN_WORKSPACE_ID` | 删除 | 迁移到服务端 |

### 验证结果（2026-03-24）

- [x] `config.py` 导入 + `ChatOpenAI` 创建成功
- [x] DeepSeek 实际调用通过 New API 正常返回
- [x] `/v1/models` 动态获取 4 个模型
- [x] RAG 优雅降级（服务端未部署时返回错误信息，不崩溃）
- [x] `settings.py` 精简为 2 个 key
- [x] 前端 TypeScript 编译零错误
- [x] 前端 Vite 构建成功

### 待完成

- [ ] **RAG 代理部署**：服务端 `rag-proxy/` Docker 容器（代码已在 `docs/TOC_PLAN.md` 1.2 节）
  - 需要百炼凭证（已有）：`LTAI5tQtx7CSACPwFh8A1NB1` / `llm-fo524vmjsvgfy4fo` / `nvtgp3wdzi`
  - 需要在服务器上执行部署命令
  - 安全组需放行 TCP 8100
- [ ] **Phase 2：登录/注册/计费 UI**
  - `src/api/auth.py` — Auth 服务
  - `frontend/src/components/AuthScreen.tsx` — 登录页
  - `frontend/src/hooks/useAuth.ts` — Auth hook
  - `App.tsx` Auth 门控 + 余额显示
  - `Sidebar.tsx` 用户信息 + 退出
- [ ] **Phase 3：体验打磨**
  - 新手引导、论文模板、品牌更新
