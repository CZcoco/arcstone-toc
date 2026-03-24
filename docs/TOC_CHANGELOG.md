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

---

## Phase 2：登录门控 + 每用户独立 Token（2026-03-24）

### 认证流程

用户点"开始使用" → 后台自动注册+登录 → 创建独立 token → 存本地 → 以后自动进

**Token 获取流程**（New API v0.11.x 的三步）：
1. `POST /api/token/` → 创建 token（响应不含明文 key）
2. `GET /api/token/?p=0` → 列表拿到 token id
3. `POST /api/token/:id/key` → 取回明文 key

每个用户有独立 `sk-...` token，New API 服务端自动按用户扣费，无需应用层计费。

### 新增文件

| 文件 | 说明 |
|------|------|
| `src/api/auth.py` | 后端认证服务：`quick_start()` 自动注册+登录+创建独立 token；`get_user_info()` 查余额；`auto_login()` 自动重登录 |
| `frontend/src/lib/auth.ts` | 前端认证 API：`quickStart()`、`getUserInfo()`、`logout()` |
| `frontend/src/hooks/useAuth.ts` | React hook：`useAuth()` → `{user, loading, start, logout, refreshBalance}` |
| `frontend/src/components/AuthScreen.tsx` | 极简"开始使用"页面，输入用户名+密码即可，首次自动创建账号 |

### 修改文件

| 文件 | 改动 |
|------|------|
| `src/api/routes.py` | 新增 `/auth/start`（一步注册+登录）、`/auth/user`（获取用户信息，session 过期自动重登录）、`/auth/logout`；登录时保存 `ECON_USER_TOKEN` 到环境变量和 settings.json |
| `src/api/app.py` | 新增 `AuthMiddleware`：非 auth/health 路径需已登录（检查 `ECON_SESSION_COOKIE`） |
| `src/settings.py` | `_AUTH_KEYS` 新增 `ECON_USER_TOKEN`、`ECON_SESSION_COOKIE`、`ECON_USER_ID`、`ECON_USERNAME`、`ECON_PASSWORD`，启动时加载到环境变量 |
| `frontend/src/App.tsx` | 导入 `useAuth` + `AuthScreen`；auth 门控（未登录显示 AuthScreen）；发消息后刷新余额 |
| `frontend/src/components/Sidebar.tsx` | 底部新增用户信息区：用户名、余额、充值按钮（跳 New API 充值页）、退出按钮 |

### 环境变量变化

| 变量 | 状态 | 说明 |
|------|------|------|
| `ECON_USER_TOKEN` | 更新 | 现在是**每用户独立 token**（非共享），登录时自动创建 |
| `ECON_SESSION_COOKIE` | **新增** | New API session cookie，用于查询用户信息 |
| `ECON_USER_ID` | **新增** | New API 用户 ID |
| `ECON_USERNAME` | **新增** | 用户名（用于自动重登录） |
| `ECON_PASSWORD` | **新增** | 密码（用于自动重登录，存本地 settings.json） |

### New API 认证要点

- 登录：`POST /api/user/login` → 返回 session cookie + user info
- 用户管理 API：session cookie + `New-Api-User: {user_id}` header
- Token 明文获取：`POST /api/token/:id/key` → `data.key`
- 限流较严格：注册/登录频繁调用会 429，代码中加了 `sleep(1)` 和 `_safe_json` 防护

### 验证结果（2026-03-24）

- [x] 已有用户登录成功，拿到 session cookie + user info
- [x] 新用户自动注册+登录成功
- [x] 错误密码正确拒绝
- [x] `POST /api/token/:id/key` 成功取回明文 token
- [x] Per-user token 调 `/v1/models` 返回 6 个模型
- [x] auto_login 正常工作（成功/失败均正确）
- [x] 前端 TypeScript 编译零错误
- [x] 前端 Vite 构建成功

---

### 待完成

- [ ] **Phase 2.5：接入支付**（微信/支付宝 → New API 用户充值）
- [ ] **Phase 3：体验打磨**
  - 新手引导、论文模板、品牌更新
