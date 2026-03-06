# econ-agent Electron 打包指南

> 版本：v0.4.1-econ | 更新：2026-03-06

## 打包前提

1. Node.js 已安装，`frontend/` 下 `npm install` 已执行
2. `frontend/resources/python/` 里有完整的 embedded Python 环境（含所有依赖）
3. 开发环境的后端（8000 端口）已关闭

## 一、准备 embedded Python

首次或 `requirements.txt` 有变更时执行：

```bash
# 如果 resources/python 还不存在，先跑 setup 脚本
scripts\setup_python.bat

# 如果已存在，只需同步依赖
"D:/econ-agent/frontend/resources/python/python.exe" -m pip install -r "D:/econ-agent/requirements.txt" --no-warn-script-location
```

验证：所有包都显示 `Requirement already satisfied` 即可。

## 二、打包命令

```bash
cd D:/econ-agent/frontend
npm run build            # tsc + vite build → dist/
npx electron-builder --win   # → release/econ-agent Setup x.x.x.exe
```

产物：
- `frontend/release/econ-agent Setup x.x.x.exe` — NSIS 安装包
- `frontend/release/win-unpacked/` — 解压版（可直接运行，用于调试）

## 三、关键配置说明

### package.json build 字段

```jsonc
{
  "build": {
    "appId": "com.econagent.desktop",
    "productName": "econ-agent",
    "directories": { "output": "release" },
    "files": [
      "dist/**/*",       // Vite 构建的前端
      "electron/**/*"    // Electron 主进程
    ],
    "extraResources": [
      {
        "from": "../",
        "to": "app",
        "filter": ["run_api.py", "src/**/*", "skills/**/*", "requirements.txt"]
        // 注意：不打包 .env（含开发者 API Key）和 data/（用户数据）
      },
      {
        "from": "resources/python",
        "to": "python",
        "filter": ["**/*"]
      }
    ]
  }
}
```

### 不打包的内容及原因

| 排除项 | 原因 |
|--------|------|
| `.env` | 含开发者 API Key，泄露风险。用户通过设置面板配置，存 `data/settings.json` |
| `data/` | 用户运行时数据（数据库、设置），首次启动由 `main.cjs` 自动创建空目录 |
| `node_modules/` | 前端已 build 到 `dist/`，不需要 |
| `__pycache__/` | 会被打包进去但无害，Python 会自动重建 |
| `docs/`、`scripts/`、`README.md` | 开发文档，用户不需要 |

## 四、打包后目录结构

```
安装目录/
├── econ-agent.exe
├── resources/
│   ├── app.asar              ← Electron 前端（dist/ + electron/）
│   ├── app/                  ← 后端代码（extraResources）
│   │   ├── run_api.py
│   │   ├── src/
│   │   ├── skills/
│   │   └── requirements.txt
│   └── python/               ← 嵌入式 Python 3.11 + 所有依赖
│       ├── python.exe
│       ├── python311.dll
│       └── Lib/site-packages/
```

首次启动后 `app/` 下会多出：
```
app/
├── .env                      ← main.cjs 创建的空文件
└── data/
    ├── memories.db
    ├── checkpoints.db
    ├── settings.json
    └── tmp/
```

## 五、路径解析机制

### Electron 主进程（main.cjs）

```javascript
// 打包态
getPythonPath()   → process.resourcesPath + "/python/python.exe"
getProjectRoot()  → process.resourcesPath + "/app"

// 开发态
getPythonPath()   → "D:/miniconda/envs/miner-agent/python.exe"
getProjectRoot()  → __dirname + "/../.."  (即 D:/econ-agent)
```

### Python 后端路径

全部基于 `__file__` 相对路径，打包后自动兼容：

| 变量 | 代码位置 | 打包后解析结果 |
|------|----------|----------------|
| `ROOT_DIR` | `app.py:11` | `resources/app/` |
| `DATA_DIR` | `main.py:27` | `resources/app/data/` |
| `SKILLS_DIR` | `main.py:31` | `resources/app/skills/` |
| `_WORK_DIR` | `code_runner.py:36` | `resources/app/data/tmp/` |
| `_PYTHON` | `code_runner.py:15` | 优先 `PYTHON_EXECUTABLE` 环境变量 → `resources/python/python.exe` |

### code_runner 的 Python 查找顺序

1. `os.environ["PYTHON_EXECUTABLE"]`（main.cjs 启动时注入）
2. `__file__` 往上三级 + `python/python.exe`（embedded 路径）
3. `sys.executable`（当前进程的 Python）

## 六、踩坑记录

### 1. .env 泄露 API Key

**问题**：早期 filter 里包含 `.env`，打包后用户能看到开发者的 API Key。
**解决**：filter 移除 `.env`，`main.cjs` 首次启动创建空文件，用户走设置面板。

### 2. 端口冲突导致连错后端

**问题**：本机开发后端占着 8000 端口，安装版 Electron 的 `waitForBackend` 检测到端口已通，直接连上了开发后端。表现为安装版能看到开发环境的会话和记忆。
**解决**：测试前关闭开发环境后端。

### 3. 系统环境变量泄露到打包版

**问题**：`startPython` 用 `{ ...process.env }` 传环境变量，开发机上的系统环境变量（如 `ALIBABA_CLOUD_ACCESS_KEY_ID`）会被继承。设置面板会显示 `****` 脱敏值。
**影响**：仅影响开发者本机测试，分发给别人不受影响。

### 4. Windows 进程树残留

**问题**：`pyProcess.kill()` 只杀主进程，uvicorn 的子进程可能残留。
**解决**：用 `execSync("taskkill /T /F /PID ...")` 杀整个进程树。

### 5. data/ 目录不存在

**问题**：electron-builder 不打包空目录，首次启动时 Python 后端找不到 `data/` 报错。
**解决**：`main.cjs` 的 `ensureDataDir()` 在启动 Python 前创建 `data/` 和 `data/tmp/`。

### 6. Embedded Python 中文编码乱码

**问题**：Windows 下 embedded Python 3.11 默认编码不是 UTF-8，导致工具的中文 docstring 传给模型时变成乱码，模型无法识别工具。
**解决**：`main.cjs` 启动 Python 时注入 `PYTHONUTF8: "1"` 环境变量，强制 UTF-8。

### 7. 自定义工具名与 Anthropic 内置工具冲突

**问题**：Anthropic Claude API 有内置的 `web_search` 服务端工具（`type: "web_search_20250305"`）。如果自定义工具也叫 `web_search`，Claude 模型会将其视为保留名而忽略，导致"没有搜索工具"。DeepSeek/Kimi 不受影响。
**表现**：Claude 模型列出工具时漏掉 `web_search`，让它搜东西也不调用；换 DeepSeek 则正常。
**解决**：将工具函数名从 `web_search` 改为 `internet_search`，同步更新 `main.py` import、`prompts.py` 工具指南。
**教训**：避免使用 `web_search`、`code_execution` 等 Anthropic 保留的工具名。

## 七、版本升级检查清单

每次发新版前过一遍：

- [ ] `requirements.txt` 有变更？→ 重新 `pip install` 到 `resources/python/`
- [ ] `package.json` 版本号更新了？（`version` 字段影响安装包文件名）
- [ ] 新增了 Python 文件/目录？→ 确认 `extraResources` filter 能匹配到
- [ ] 新增了需要打包的非 `src/` 目录？→ 加到 filter
- [ ] `.env` 里新增了配置项？→ 确认 `settings.py` 的 schema 和设置面板已同步
- [ ] 关闭开发环境后端再测试安装包
- [ ] 在没有 miniconda 的干净机器上测试（最终验证）
