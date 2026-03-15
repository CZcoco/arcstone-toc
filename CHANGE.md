# 修改记录 (Changelog)

## 0.6.2 (2026-03-15)

### 优化

- 首启 loading 页改为显示真实启动阶段，用户现在可以看到依赖检查、安装、回退与健康检查进度。
- Electron 主进程新增结构化启动状态桥接，启动失败时会附带最后阶段信息，便于排障。
- 新增 `GET /api/install/status`，启动后可读取首启依赖安装结果用于诊断。
- 新增 `用户环境.md`，统一开发环境、打包环境、用户环境以及 non-git 关键配置说明。

### 依赖与运行时

- 延续最小首启依赖策略，继续使用 embedded Python 3.12 作为 runtime 本体，uv 负责安装，pip 作为 fallback。
- 对外明确 startup 依赖与 optional 扩展依赖分层，避免把开发依赖等同于用户首启依赖。

### 版本

- `frontend/package.json` 版本提升至 `0.6.2`。
- 同步更新 Electron 安装包版本与锁文件版本。

## 0.6.1 (2026-03-15)

### 修复

- 在线安装依赖时显式绑定 `PYTHON_EXECUTABLE` 指向的 embedded Python，避免误用 `backend.exe` 或其他 Python 环境。
- 核心依赖改为通过目标 Python 子进程校验，并增加 `Asia/Shanghai` 时区烟测，减少安装状态误判。
- 补充 `tzdata` 与 Excel/PDF 常用运行时依赖，降低打包态 `run_python` 与技能脚本缺包问题。
- 打包态延长后端启动等待时间，并在失败提示中补充“首次启动可能正在联网安装依赖”的说明。

### 版本

- `frontend/package.json` 版本提升至 `0.6.1`。
- 同步更新 Electron 安装包版本与锁文件版本。

## 0.6.0 (2026-03-15)

### 架构变更

- 切换为在线安装版（精简包），安装包从约 410MB 降至约 110MB。
- 安装包仅携带 Python 3.12.10 与 uv，其余依赖在首次启动时自动安装。
- 默认使用阿里云 PyPI 镜像加速依赖安装。

### 新增

- 新增依赖安装器，支持分阶段安装、uv 优先、pip 回退与失败隔离。
- 安装状态支持持久化记录，便于首启诊断。
- 在系统提示与工具文档中补充 uv 用法说明。

### 修改

- `scripts/setup_python.bat` 调整为仅准备 Python 与 uv，不再预装完整依赖。
- `src/api/app.py` 在应用启动时增加首次依赖检测与自动安装流程。

## 0.5.12 (2026-03-14)

### 优化

- 调整对话区域响应式宽度，小屏更紧凑，大屏限制最大宽度以提升阅读体验。
- 修复 Markdown、用户消息与工具输出中的超长文本换行问题。

## 0.5.11 (2026-03-14)

### 重要变更

- 移除 DeepSeek 和 Kimi API 支持，并从模型配置、设置项、前端选择器与环境变量模板中同步清理相关入口。
- 默认模型切换为 `claude-sonnet`，避免继续落到已移除的旧线路。

### 构建

- 切换到 Python 3.12.10 embedded runtime，并打包完整数据科学与 Web 服务依赖。
- `scripts/setup_python.bat` 改用 PowerShell `Expand-Archive` 处理解压，修复 Windows 路径问题。
- 版本号提升至 `0.5.12`，并完成完整安装包构建验证。

### 修复

- 清理 DeepSeek 默认参数残留，统一 `run.py`、`src/api/app.py`、`src/api/routes.py`、`src/api/stream.py` 与前端会话默认模型为 `claude-sonnet`。
- 简化 `read_image` 视觉支持判断逻辑，移除仅针对 DeepSeek 的旧分支。

## 0.5.10 (2026-03-14)

### 修复

- 为 `gpt` 路线补充更稳妥的请求头、超时与重试参数，改善中转兼容性。
- 将 `gpt` 默认 `base_url` 校正为本次实测可用地址。
- 重新构建 `backend.exe` 并重打安装包，确保前后端逻辑一致。
- 明确最终用户环境必须包含独立的 `resources/python/python.exe`，不能只依赖 `backend.exe`。

## 0.5.9 (2026-03-14)

### 修复

- 补充 GPT 中转线路排查结论，确认旧入口不稳定且候选 IP 当前不可用。
- 验证 `claude-opus` / `claude-sonnet` 通过 `https://apicn.ai` + `ANTHROPIC_AUTH_TOKEN` 可正常调用。
- 将桌面端版本提升至 `0.5.9`，用于稳定性排查后的完整构建发布。

## 0.5.8 (2026-03-13)

### 新增

- 新增 `CLAUDE.md` 项目开发指引文档。

### 修复

- Electron 主进程改为动态检测开发模式 Python 路径，避免硬编码路径导致启动失败。
- `ModelSelector` 始终显示当前模型，仅在多个模型时展示下拉能力。
- 修复设置面板敏感字段在脱敏后粘贴与删除异常的问题。
- 更新设置面板中 Claude 相关标签文案。
- 兼容 Clash TUN 模式，避免本地前后端通信被代理干扰。

---

## 0.5.7-beta (之前版本)

- 初始经济学论文助手版本。
- 集成 Deep Agents + LangGraph。
- 支持多模型切换（DeepSeek / Claude / Kimi / GPT）。
- 支持文献检索、数据获取与实证分析技能。
