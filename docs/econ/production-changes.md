# 面向外部用户的生产环境改动记录

> 本文档记录 Arcstone-econ 从开发环境走向外部用户（舍友等）实际使用时，针对生产环境稳定性、兼容性所做的所有改动。
>
> 日期：2026-03-13

---

## 一、问题背景

将打包好的 Arcstone-econ 桌面应用交给外部用户使用后，暴露出三类问题：

1. **系统代理干扰**：用户开了 Clash 等代理工具（如 socks4://127.0.0.1:1080），Electron 渲染进程的 fetch/SSE 请求走代理连 127.0.0.1:18081，导致前端"连接中断"/"连接失败"
2. **固定端口冲突**：18081 端口硬编码，被其他程序占用时后端启动失败
3. **覆盖安装残留**：旧版本的 backend.exe 进程占着端口未退出，新版 app 启动后端失败
4. **启动阻塞卡死**：FastAPI lifespan 中的 `backfill()` 函数无条件调用 embedding API，用户未配 API key 或网络不通时，同步 HTTP 请求挂住导致启动超过 60 秒，触发 "Backend timeout"
5. **模型列表不刷新**：用户在设置页填入新的 API key 后，模型下拉框不会更新，必须刷新页面才能看到新模型
6. **默认模型不合理**：默认模型是 Claude Opus 4.6 Plan（需要订阅 key），普通用户更适合默认 GPT-5.4

---

## 二、改动总览

| # | 问题 | 改动文件 | 改动类型 |
|---|------|---------|---------|
| 1 | 代理干扰 | `frontend/electron/main.cjs` | 新增代理绕过 |
| 2 | 端口冲突 | `run_api.py` + `frontend/electron/main.cjs` + `frontend/src/lib/api.ts` | 动态端口分配 |
| 3 | 覆盖安装残留 | `frontend/electron/main.cjs` | 启动前杀旧进程 |
| 4 | 启动阻塞 | `src/memory_search.py` | backfill 前置检查 + 超时保护 |
| 5 | 模型列表不刷新 | `App.tsx` + `ModelSelector.tsx` + `SettingsPanel.tsx` | 设置保存后触发刷新 |
| 6 | 默认模型 | `App.tsx` | 改为 GPT-5.4 |

---

## 三、各改动详细说明

### 3.1 代理绕过（Electron 渲染进程）

**文件**：`frontend/electron/main.cjs`

**改动**：在 `app.whenReady()` 内、启动后端之前调用：

```js
await session.defaultSession.setProxy({
  proxyBypassRules: "127.0.0.1,localhost",
});
```

**原理**：
- `session.defaultSession.setProxy()` 只影响 Electron 渲染进程（Chromium 内核）的网络请求
- 让前端页面对 localhost 的 fetch/SSE 直连，不走系统代理
- Python 后端进程是独立进程，有自己的网络栈，不受此设置影响——Agent 调外部 API（OpenAI、Anthropic、DeepSeek）仍然走系统代理，梯子正常使用
- Electron 主进程的 `http.get`（健康检查）走 Node.js http 模块，也不受影响

### 3.2 动态端口分配

**问题**：18081 硬编码，被占用时后端启动失败。

**改动涉及 3 个文件**：

#### `run_api.py`（Python 后端启动脚本）

```python
API_PORT = int(os.environ.get("ARCSTONE_ECON_API_PORT", "18081"))

if __name__ == "__main__":
    if API_PORT == 0:
        # 让 OS 分配空闲端口
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        actual_port = sock.getsockname()[1]
        sock.close()
    else:
        actual_port = API_PORT

    # Electron 解析这行拿到实际端口
    print(f"ARCSTONE_PORT={actual_port}", flush=True)

    uvicorn.run("src.api.app:app", host="127.0.0.1", port=actual_port, reload=False)
```

#### `frontend/electron/main.cjs`（Electron 主进程）

- `startPython()` 改为返回 Promise，打包模式传 `ARCSTONE_ECON_API_PORT=0`
- 监听 backend 进程 stdout，正则匹配 `ARCSTONE_PORT=(\d+)` 捕获实际端口
- 30 秒超时保护，进程异常退出时立即 reject
- `waitForBackend()` 和 `createWindow()` 使用捕获到的 `actualPort`
- `loadFile` 通过 query param `?__port=xxxxx` 将端口注入前端页面

#### `frontend/src/lib/api.ts`（前端 API 层）

```ts
const API_PORT = (() => {
  if (window.location.protocol === "file:") {
    const p = parseInt(new URLSearchParams(window.location.search).get("__port") || "", 10);
    if (p > 0) return p;
  }
  return 18081;
})();
```

**端口同步流程**：
```
打包模式：
  main.cjs 传 ARCSTONE_ECON_API_PORT=0
  → Python socket.bind(0) 拿空闲端口
  → stdout 打印 ARCSTONE_PORT=xxxxx
  → Electron 正则捕获存入 actualPort
  → loadFile query param ?__port=xxxxx
  → 前端 api.ts 从 URL 读取端口
  → BASE_URL = http://127.0.0.1:xxxxx/api

开发模式：
  固定 18081，行为完全不变
```

### 3.3 覆盖安装残留清理

**文件**：`frontend/electron/main.cjs`

```js
function killOldBackend() {
  if (!app.isPackaged) return;
  try {
    execSync("taskkill /f /im backend.exe", { windowsHide: true, stdio: "ignore" });
  } catch {
    // 没有旧进程，正常
  }
}
```

在 `app.whenReady()` 中、启动新后端之前调用。仅打包模式生效，开发模式跳过。

### 3.4 启动阻塞修复（backfill 前置检查 + 超时）

**文件**：`src/memory_search.py`

**根因分析**：

`backfill()` 在 FastAPI lifespan 中无条件执行，遍历所有已有 memory 文件，对每个文件调 `openai.embeddings.create()`（DashScope embedding API）。这是同步 HTTP 调用，阻塞 lifespan。

- 用户未配 `DASHSCOPE_API_KEY` 时：`_get_client()` 抛 ValueError 被 catch，但每个文件都重试一遍 + `time.sleep(0.2)` 间隔，多个文件累积耗时
- 用户配了 key 但网络不通时：TCP 连接挂住等超时（默认 30-120 秒），4 个文件 × 30 秒 = 120 秒，远超 60 秒健康检查上限 → "Backend timeout"
- 删掉 AppData 后秒启动：因为没有 memory 文件，`backfill()` 无事可做

**改动 1**：`backfill()` 开头检查 API key

```python
def backfill(self) -> int:
    if not os.environ.get("DASHSCOPE_API_KEY"):
        logger.info("DASHSCOPE_API_KEY not set, skipping backfill")
        return 0
    # ... 原有逻辑
```

**改动 2**：`_get_embedding()` 加 8 秒超时

```python
response = client.embeddings.create(
    model=_EMBEDDING_MODEL,
    input=[truncated],
    dimensions=_EMBEDDING_DIMS,
    timeout=8,
)
```

### 3.5 模型列表保存后自动刷新

**根因**：`ModelSelector` 组件的 `useEffect` 依赖数组为 `[]`，只在挂载时拉一次模型列表。用户在设置页填完 API key 保存后，模型列表不会重新拉取。

**改动涉及 3 个文件**：

| 文件 | 改动 |
|------|------|
| `frontend/src/App.tsx` | 新增 `modelRefreshKey` state；`SettingsPanel` 传入 `onSaved` 回调（+1）；`ModelSelector` 传入 `refreshKey` |
| `frontend/src/components/ModelSelector.tsx` | 接收 `refreshKey` prop，加入 useEffect 依赖数组 |
| `frontend/src/components/SettingsPanel.tsx` | 接收 `onSaved` 回调，保存成功且有变更时调用 |

**流程**：用户保存设置 → `onSaved()` → `modelRefreshKey` +1 → `ModelSelector` useEffect 重新触发 → `GET /api/models` → 新模型出现在下拉框

### 3.6 默认模型改为 GPT-5.4

**文件**：`frontend/src/App.tsx`

```ts
// 改前
const [model, setModel] = useState(() => localStorage.getItem(STORAGE_KEY) || "claude-opus-plan");
// 改后
const [model, setModel] = useState(() => localStorage.getItem(STORAGE_KEY) || "gpt");
```

新用户默认选 GPT-5.4 xhigh Plan。已有用户 localStorage 里存了之前的选择，不受影响。

---

## 四、不需要改的部分

- **Python 后端业务逻辑**：Agent、工具、prompt、API 路由——全部不动
- **backend.spec / build_backend.bat**：打包配置不涉及
- **前端其他组件**：所有 API 调用通过 `BASE_URL` 统一管理，端口改动自动生效
- **Python 后端调外部 API**（config.py 里的 base_url）：独立进程，不受 Electron 代理设置影响

---

## 五、验证清单

| 场景 | 预期结果 | 状态 |
|------|---------|------|
| 开 Clash 代理 → 启动 app → 对话 | 正常，不再"连接中断" | ✅ 已验证 |
| 18081 被占用 → 启动 app | 自动分配其他端口，正常工作 | ✅ 已验证（手动测试 port=0） |
| 覆盖安装后启动 | 不报端口占用 | ✅ killOldBackend 逻辑已加 |
| 未配 DASHSCOPE_API_KEY → 启动 | 秒启动，不卡 backfill | ✅ 已加前置检查 |
| 开发模式 `npm run electron:dev` | 仍用 18081，不受影响 | ✅ 已验证 |
| 设置页填 API key → 保存 → 模型列表 | 立即出现新模型 | ✅ refreshKey 机制已加 |
| 新用户首次打开 | 默认选中 GPT-5.4 | ✅ 已改默认值 |
