# 修改记录 (Changelog)

## 0.5.9 (2026-03-14)

### 修复

- **GPT 中转线路排查结论补充**：确认 `https://chat.apiport.cc.cd/v1` 对应的 GPT 路线存在上游不稳定现象；`http://106.53.52.4` / `/v1` 当前不可用（80 端口拒绝连接，443 超时），因此本版本未切换到该 IP。
- **Claude API 线路验证**：确认 `claude-opus` / `claude-sonnet` 通过 `https://apicn.ai` + `ANTHROPIC_AUTH_TOKEN` 可正常调用，当前 Claude API（API额度）配置有效。
- **版本发布整理**：将桌面端版本号提升至 `0.5.9`，用于本次稳定性排查后的完整构建发布。

## 0.5.8 (2026-03-13)

### 新增

- **CLAUDE.md**: 项目开发指引文档，包含架构说明、常用命令、关键文件位置等

### 修复

#### 1. Electron 主进程优化 (`frontend/electron/main.cjs`)

**问题**: 开发模式 Python 路径硬编码导致在其他环境无法启动

**修改**:
- Python 路径改为动态检测：优先项目 `.venv`，其次环境变量，最后系统 PATH
- 隐藏顶部菜单栏（File/Edit/View/Window/Help）

```javascript
// 开发模式 Python 路径检测
const venvPython = path.join(projectRoot, ".venv", "Scripts", "python.exe");
if (fs.existsSync(venvPython)) return venvPython;
return process.env.PYTHON_EXECUTABLE || "python";
```

#### 2. ModelSelector 显示优化 (`frontend/src/components/ModelSelector.tsx`)

**问题**: 单个可用模型时不显示选择器，用户看不到当前模型

**修改**:
- 始终显示当前模型名称
- 仅在有多个模型时显示下拉箭头
- 模型命名更新（API/Plan 区分）

```tsx
// 模型显示名
"claude-opus": "Claude Opus 4.6 API",
"claude-sonnet": "Claude Sonnet 4.6 API",
"claude-opus-plan": "Claude Opus 4.6 Plan",
"claude-sonnet-plan": "Claude Sonnet 4.6 Plan",
```

#### 3. SettingsPanel 输入修复 (`frontend/src/components/SettingsPanel.tsx`)

**问题**: 敏感字段脱敏后（****1234）粘贴/删除异常

**修改**: 简化输入处理逻辑，直接更新 value

#### 4. 设置面板标签更新 (`src/settings.py`)

**修改**:
- `ANTHROPIC_AUTH_TOKEN`: "Claude（API额度）" → "Claude API（API额度）"
- `ANTHROPIC_SUB_TOKEN`: "Claude（订阅）" → "Claude Plan（订阅）"

#### 5. Clash TUN 模式兼容 (`run_api.py`)

**问题**: TUN 模式强制代理本地流量，导致前后端通信失败

**修改**: 启动时清理代理环境变量

```python
# 清理代理环境变量，避免 TUN 模式干扰本地连接
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ["NO_PROXY"] = "127.0.0.1,localhost,127.0.0.1:18081,localhost:18081"
```

---

## 0.5.7-beta (之前版本)

- 初始经济学论文助手版本
- 集成 Deep Agents + LangGraph
- 支持多模型切换（DeepSeek/Claude/Kimi/GPT）
- 文献检索、数据获取、实证分析技能
