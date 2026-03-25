# econ-agent ToC 版 — 项目交接文档

> 最后更新：2026-03-25 | 当前版本：v0.7.2-toc

---

## 1. 项目概述

**econ-agent** 是面向中国本科经济学生的 AI 论文助手，基于 LangChain Deep Agents + LangGraph 构建，帮助用户完成从选题到定稿的毕业论文全流程。

ToC 版本在原版基础上增加了：登录系统、按用户计费、云端配置管理（模式/模型/技能/Key）、新手引导等。

**仓库**：`https://github.com/CZcoco/arcstone-toc.git`（私有）
**VPS**：`43.128.44.82`（腾讯云，Caddy + Docker）
**New API 后台**：`http://43.128.44.82:3000`（端口 3001 内部，Caddy 代理到 3000）

---

## 2. 架构总览

```
┌─────────────────────────────────────────────────────┐
│  用户端 (Electron / Vite dev)                        │
│  React + TypeScript + TailwindCSS                    │
│  ├── AuthScreen     → 登录/注册                      │
│  ├── ModeSelector   → 切换模式（从 VPS 拉取）         │
│  ├── WelcomeScreen  → 模板卡片（随模式变化）           │
│  ├── ChatMessage    → Markdown + LaTeX + 图片渲染     │
│  ├── RightPanel     → 工作区文件 + AI记忆（平铺右侧）  │
│  └── ChatInput      → 支持 PDF/Word/Excel/图片上传    │
└──────────────┬──────────────────────────────────────┘
               │ HTTP / SSE
┌──────────────▼──────────────────────────────────────┐
│  FastAPI 后端 (run_api.py → src/api/app.py)          │
│  ├── AuthMiddleware  → 未登录返回 401                 │
│  ├── AgentManager    → 按 (model, workspace) 缓存    │
│  ├── SSE /chat/stream → token/tool_start/tool_end    │
│  └── 启动时拉取 VPS 配置:                             │
│       ├── /config/keys.json     → Tavily/MinerU key  │
│       ├── /config/modes.json    → 模式 + 提示词 + 卡片│
│       ├── /config/models.json   → 模型白名单          │
│       └── /config/skills-*      → 技能包同步          │
└──────────────┬──────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────┐
│  Agent 层 (src/agent/main.py)                        │
│  create_econ_agent() → CompiledStateGraph            │
│  ├── 系统提示词: modes.json 的 system_prompt          │
│  ├── 工具: 8 个（见下文）                             │
│  ├── 虚拟路径:                                       │
│  │    /memories/ → SqliteStore                       │
│  │    /skills/   → FilesystemBackend (只读)          │
│  │    /workspace/ → FilesystemBackend (用户工作区)    │
│  └── 持久化: checkpoints.db (会话) + memories.db (记忆)│
└──────────────┬──────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────┐
│  VPS 服务 (43.128.44.82)                             │
│  ├── Caddy (:3000 → :3001 New API + /config/ 静态)   │
│  ├── New API Docker (:3001) — 用户管理 + LLM 转发     │
│  └── RAG Proxy Docker (:8100) — 百炼知识库检索         │
└─────────────────────────────────────────────────────┘
```

---

## 3. 目录结构

```
econ-agent-toc/
├── src/
│   ├── agent/
│   │   ├── main.py          # Agent 工厂 create_econ_agent()
│   │   ├── prompts.py       # 系统提示词（ECON_SYSTEM_PROMPT + 4个子agent提示词）
│   │   └── config.py        # get_llm() + NEW_API_BASE_URL
│   ├── api/
│   │   ├── app.py           # FastAPI 入口, AgentManager, lifespan
│   │   ├── routes.py        # 所有 API 路由 (~1300行)
│   │   ├── auth.py          # 登录/注册/Token 管理
│   │   ├── stream.py        # SSE 流式输出 + 3次重试
│   │   ├── key_pool.py      # VPS Key 池轮询 (Tavily/MinerU)
│   │   ├── modes.py         # 云端模式管理
│   │   ├── model_whitelist.py # 模型白名单过滤
│   │   └── skills_sync.py   # 技能云端同步 (版本比对+配置保留)
│   ├── tools/
│   │   ├── rag.py           # 百炼 RAG 检索 (HTTP 代理)
│   │   ├── search.py        # internet_search + fetch_website
│   │   ├── code_runner.py   # run_python (虚拟路径支持)
│   │   ├── pdf_reader.py    # read_pdf
│   │   ├── read_image.py    # read_image
│   │   ├── memory_search.py # memory_search (纯 FTS5)
│   │   └── image_gen.py     # generate_image (qwen-image-2.0-pro)
│   ├── store.py             # SqliteStore (记忆后端)
│   ├── memory_search.py     # FTS5 + jieba 全文搜索引擎
│   └── settings.py          # 设置管理
├── frontend/
│   ├── src/
│   │   ├── App.tsx           # 主组件
│   │   ├── components/
│   │   │   ├── AuthScreen.tsx      # 登录页
│   │   │   ├── ChatMessage.tsx     # 消息渲染 (Markdown/LaTeX/图片)
│   │   │   ├── ChatInput.tsx       # 输入框 + 文件上传
│   │   │   ├── ModeSelector.tsx    # 模式选择器
│   │   │   ├── WelcomeScreen.tsx   # 模板卡片 (随模式联动)
│   │   │   ├── OnboardingModal.tsx # 新手引导 (3页)
│   │   │   ├── RightPanel.tsx      # 右侧面板 (工作区+记忆)
│   │   │   ├── Sidebar.tsx         # 左侧边栏 (会话列表+用户信息)
│   │   │   ├── ToolCallCard.tsx    # 工具调用卡片
│   │   │   └── ModelSelector.tsx   # 模型选择 (从白名单过滤)
│   │   ├── hooks/
│   │   │   ├── useAuth.ts    # 认证状态
│   │   │   ├── useChat.ts    # 聊天 SSE 逻辑
│   │   │   └── useTopup.ts   # 充值弹窗
│   │   └── lib/
│   │       ├── api.ts        # API 客户端 (所有后端接口)
│   │       └── auth.ts       # 认证工具函数
│   └── electron/
│       ├── main.cjs          # Electron 主进程
│       └── preload.cjs       # 预加载脚本
├── skills/                   # 技能模块 (云端同步)
│   ├── literature-search/    # 文献检索 (OpenAlex/Semantic Scholar)
│   ├── data/                 # 数据获取 (世界银行/统计局/FRED/IMF/Comtrade)
│   ├── stata/                # Stata 集成
│   ├── word/                 # Word 文档生成
│   ├── pdf/                  # PDF 解析
│   └── xlsx/                 # Excel 操作
├── vps-config/               # VPS 配置文件本地副本
│   ├── modes.json            # 模式列表 (含 system_prompt + templates)
│   └── models.json           # 模型白名单
├── rag-proxy/                # RAG 代理 Docker 项目
│   ├── Dockerfile
│   ├── app.py                # FastAPI + 百炼 SDK
│   └── requirements.txt
├── deploy_vps.sh             # VPS 一键部署脚本
├── run_api.py                # 后端启动入口
├── run.py                    # 终端模式入口
└── CLAUDE.md                 # Claude Code 项目指引
```

---

## 4. 本地开发环境搭建

### 4.1 前置条件

- Python 3.12+（推荐 conda）
- Node.js 18+ / npm
- Git

### 4.2 克隆与安装

```bash
git clone https://github.com/CZcoco/arcstone-toc.git
cd arcstone-toc

# Python 依赖
conda create -n miner-agent python=3.12
conda activate miner-agent
pip install -r requirements.txt

# 前端依赖
cd frontend
npm install
cd ..
```

### 4.3 配置

创建 `.env` 文件（可选，也可以通过登录自动设置）：

```bash
# .env 示例（最小配置，登录后自动写入 settings.json）
NEW_API_URL=http://43.128.44.82:3000/v1
```

### 4.4 启动

```bash
# 终端 1：后端
conda activate miner-agent
python run_api.py
# 输出: Uvicorn running on http://127.0.0.1:18081

# 终端 2：前端
cd frontend
npm run dev
# 输出: Vite dev server on http://localhost:5173
```

打开 `http://localhost:5173`，输入用户名+密码登录（首次自动注册）。

---

## 5. VPS 配置管理

所有云端配置文件通过 Caddy 静态服务托管，路径 `/srv/config/`，访问地址 `http://43.128.44.82:3000/config/*`。

### 5.1 文件说明

| 文件 | 用途 | 更新方式 |
|------|------|----------|
| `/srv/config/modes.json` | 模式列表 + system_prompt + 模板卡片 | 编辑 `vps-config/modes.json` → 复制到 VPS |
| `/srv/config/models.json` | 模型白名单 | 编辑 `vps-config/models.json` → 复制到 VPS |
| `/srv/config/keys.json` | Tavily/MinerU API key 池 | 直接在 VPS 编辑 |
| `/srv/config/skills-version.json` | 技能包版本号 | 改版本号触发客户端同步 |
| `/srv/config/skills.tar.gz` | 技能包 | `bash pack_skills.sh` 生成后上传 |

### 5.2 修改模式/卡片

1. 编辑本地 `vps-config/modes.json`
2. 在腾讯云控制台 → 文件管理 → `/srv/config/modes.json` → 粘贴覆盖
3. 客户端重启后生效

### 5.3 modes.json 结构

```json
{
  "modes": [
    {
      "id": "thesis",
      "name": "论文辅导",
      "description": "毕业论文全流程",
      "icon": "graduation-cap",
      "system_prompt": "你是一个经济学论文写作AI助手...",
      "templates": [
        {
          "title": "帮我选题",
          "description": "根据兴趣推荐题目",
          "icon": "lightbulb",
          "message": "我是经济学本科生..."
        }
      ]
    }
  ]
}
```

- `system_prompt`：该模式下 Agent 使用的系统提示词（不传给前端）
- `templates`：该模式下 WelcomeScreen 显示的模板卡片
- `icon`：lucide-react 图标名（bot/graduation-cap/pencil-line/presentation/lightbulb/book-open/bar-chart-3/file-edit/calculator/check-circle/file-text）

### 5.4 Caddy 配置

```
# /etc/caddy/Caddyfile
:3000, :80 {
    handle_path /config/* {
        root * /srv/config
        file_server
    }
    handle /rag/* {
        reverse_proxy 127.0.0.1:8100
    }
    handle {
        reverse_proxy 127.0.0.1:3001
    }
}
```

Caddy 管理命令：
```bash
systemctl status caddy
systemctl restart caddy
# 如果端口占用: pkill caddy; sleep 1; systemctl start caddy
```

---

## 6. 认证与计费流程

### 6.1 用户登录

```
用户输入用户名+密码
  → POST /api/auth/start
  → 后端调用 New API 注册/登录
  → 创建 per-user Token (sk-xxx)
  → 存入 settings.json + 环境变量
  → 后续所有 LLM 调用使用该 Token
  → New API 按 Token 扣费
```

### 6.2 余额查询

- `GET /api/auth/user` → 返回 `{ username, quota, used_quota, group }`
- 前端显示：`${ (quota / 500000).toFixed(2) }`（与 New API 后台一致）
- 有 60 秒缓存，`?refresh=true` 强制刷新

### 6.3 充值（待完成）

当前只有手动在 New API 后台给用户加额度。自动充值需要：
1. 营业执照 → 注册支付宝商户
2. 接入彩虹易支付/虎皮椒等聚合支付
3. 支付回调 → 调用 New API 接口给用户加额度

---

## 7. Agent 工具详解

| 工具 | 函数 | 用途 | 备注 |
|------|------|------|------|
| `bailian_rag` | `src/tools/rag.py` | 知识库检索 | HTTP 请求 VPS RAG 代理 |
| `internet_search` | `src/tools/search.py` | 网络搜索 | Tavily API，key 从 VPS 池轮询 |
| `fetch_website` | `src/tools/search.py` | 抓取网页 | 返回文本，图片不渲染 |
| `run_python` | `src/tools/code_runner.py` | 执行 Python | 支持虚拟路径 /workspace/ |
| `read_pdf` | `src/tools/pdf_reader.py` | 读取 PDF | pdfplumber + MinerU fallback |
| `read_image` | `src/tools/read_image.py` | 读取图片 | base64 传给模型 |
| `memory_search` | `src/tools/memory_search.py` | 搜索记忆 | 纯 FTS5 + jieba 分词 |
| `generate_image` | `src/tools/image_gen.py` | 生成图片 | qwen-image-2.0-pro，保存到 workspace |

### 7.1 子 Agent（已禁用）

代码中仍保留 4 个子 agent 提示词（`prompts.py`），但 `create_econ_agent()` 已不注册子 agent。系统提示词中有严格禁止使用 task 工具的规则，防止主 agent 调用内置的 general-purpose subagent。

---

## 8. Skills 云端同步机制

### 8.1 工作流程

```
客户端启动
  → GET /config/skills-version.json → {"version": "2026-03-24-001"}
  → 比较本地 skills/.cloud-version
  → 版本不同 → 下载 /config/skills.tar.gz
  → 备份 *_config.json / *.local.json（用户配置）
  → 删除旧技能 → 解压新包 → 恢复用户配置
```

### 8.2 更新技能

```bash
# 1. 修改 skills/ 下的文件
# 2. 打包
bash pack_skills.sh
# 3. 上传 skills.tar.gz 到 VPS /srv/config/
# 4. 更新 /srv/config/skills-version.json 的版本号
```

### 8.3 用户配置保留

匹配 `*_config.json` 或 `*.local.json` 的文件在同步时会自动备份和恢复。例如 `skills/stata/scripts/stata_config.json`（Stata 安装路径）不会被覆盖。

---

## 9. 前端关键设计

### 9.1 SSE 流式渲染

`useChat.ts` 解析 SSE 事件流：
- `token` → 追加文字到当前消息
- `tool_start` → 创建 ToolCallCard（显示"执行中"）
- `tool_end` → 更新 ToolCallCard 结果
- `error` → 显示错误信息
- `complete` → 标记流结束，刷新余额

### 9.2 图片渲染规则

- **只渲染 `/workspace/` 路径的图片**（ChatMessage.tsx `resolveWorkspaceImage()`）
- `fetch_website` 抓到的外部图片只显示 alt 文本
- `generate_image` 工具的图片保存到 workspace 后通过 markdown 语法渲染

### 9.3 工具调用中断

流式中断/报错时，`markToolCallsAborted()` 将所有运行中的工具标记为 `status: "done"` + `result: "(已中断)"`，避免 UI 卡在"执行中"。

### 9.4 Mode-卡片联动

```
ModeSelector 加载/切换 mode
  → onChange(modeId, templates)
  → Sidebar 透传 → App.tsx state
  → WelcomeScreen 接收 templates prop
  → 渲染对应模式的卡片（有 fallback 默认值）
```

---

## 10. 已完成的改造 (Phase 0-3)

| 阶段 | 内容 | 状态 |
|------|------|------|
| Phase 0+1 | 统一 New API 模式，删除 8 个中转站硬编码 | ✅ 完成 |
| Phase 2 | 登录门控 + 每用户独立 Token + AuthMiddleware | ✅ 完成 |
| Phase 2.5 | 充值弹窗 UI（支付接口待接入） | ⚠️ UI 完成，支付待做 |
| Phase 3 | WelcomeScreen + OnboardingModal + RightPanel + ModeSelector + 模型白名单 + Skills 配置保留 + Mode-卡片联动 + 生图工具 + 子 agent 移除 + FTS5 简化 | ✅ 完成 |

---

## 11. 未来开发方向

### 11.1 支付系统（P0 — 最重要）

**目标**：用户在客户端内完成充值，资金到账后 New API 自动加额度。

**路径**：
1. 获取营业执照（个体工商户即可）
2. 注册支付宝/微信商户号
3. 接入聚合支付（推荐：彩虹易支付 / 虎皮椒 / YunGouOS）
4. 实现 `POST /api/topup/create` → 生成支付链接/二维码
5. 实现 `POST /api/topup/callback` → 支付成功回调 → 调用 New API 给用户加额度
6. 前端 `useTopup.ts` 已有弹窗逻辑，接入后端即可

**关键文件**：
- `frontend/src/hooks/useTopup.ts` — 前端充值 hook（已有）
- `src/api/routes.py` — `/auth/topup-context` 端点（已有，需要改为真实支付）

### 11.2 系统提示词优化（P1）

**当前问题**：
- 子 agent 已删除，但提示词还是原来的大一统版本
- 不同模式的 system_prompt 可以更精细化
- 工具使用指导可以更具体

**改进方向**：
- 在 `vps-config/modes.json` 里为每个模式写更专业的 system_prompt
- 加入具体的工具使用示例（few-shot）
- 针对 kimi 模型的特性优化提示词
- 加入更多模式（如"数据可视化"、"文献翻译"）

### 11.3 Skills 增强（P1）

**当前技能**：literature-search / data / stata / word / pdf / xlsx

**可增加**：
- **Python 数据分析**：封装 pandas/statsmodels/matplotlib 常用操作
- **Stata 增强**：更多计量模型模板（DID/RDD/PSM/合成控制法）
- **PPT 生成**：python-pptx 封装（配合"做PPT"模式）
- **文献翻译**：论文翻译+术语对照
- **查重降重**：接入查重 API + 改写建议

### 11.4 VPS 基础设施（P1）

- **HTTPS + 域名**：买域名，Caddy 自动 HTTPS
- **监控告警**：Caddy 日志 + New API 错误监控
- **自动备份**：定时备份 New API 数据库
- **CDN**：静态资源（skills.tar.gz）走 CDN 加速

### 11.5 用户体验（P2）

- **对话导出**：导出为 PDF/Word
- **多语言**：英文界面支持
- **深色模式**
- **移动端适配**
- **品牌更新**：从 "Arcstone-econ" 改为正式品牌名

### 11.6 商业化（P2）

- **套餐体系**：免费试用额度 + 月卡/季卡
- **邀请返利**：用户邀请新用户获得额度
- **数据分析**：用户使用数据统计面板
- **客服系统**：接入在线客服

---

## 12. 常见问题

### Q: 启动时报 "Server disconnected without sending a response"
**A**: VPS 上的 Caddy 挂了。SSH 到 VPS 执行 `pkill caddy; sleep 1; systemctl start caddy`。

### Q: 模型列表为空
**A**: 检查 New API 后台是否有可用渠道，以及 `vps-config/models.json` 白名单是否包含该模型。

### Q: 如何添加新模型
**A**:
1. 在 New API 后台添加渠道
2. 修改 `vps-config/models.json` 白名单加入模型 ID
3. 上传到 VPS `/srv/config/models.json`

### Q: 技能更新后用户配置丢失
**A**: 不会了。`skills_sync.py` 已加入备份/恢复逻辑，匹配 `*_config.json` 和 `*.local.json` 的文件会自动保留。

### Q: 生图不工作
**A**: 生图使用 `qwen-image-2.0-pro-2026-03-03` 模型，需要确保 New API 后台有该模型的渠道（不受白名单限制，工具内部直接调用）。

### Q: 如何在服务器修改配置
**A**:
1. 本地修改 `vps-config/` 下的文件
2. 腾讯云控制台 → 文件管理 → 导航到 `/srv/config/` → 编辑对应文件 → 粘贴内容
3. 客户端重启后生效（无需重启服务器）

---

## 13. 关键联系方式

- **New API 后台**：`http://43.128.44.82:3000`（管理员账号密码问原作者）
- **GitHub 账号**：`CZcoco`（仓库主），`Yonder-Solivagant`（备用）
- **VPS 管理**：腾讯云控制台（SSH 密钥 `skey-1p6e342h`）
