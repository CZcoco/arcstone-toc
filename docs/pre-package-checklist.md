# 打包前检查清单

## 1. 预填 API Key

编辑 `data/settings.json`，填入要预置给用户的 Key：

```json
{
  "DEEPSEEK_API_KEY": "sk-xxx",
  "DASHSCOPE_API_KEY": "sk-xxx",
  "TAVILY_API_KEY": "tvly-xxx",
  "MINERU_API_KEY": "eyJ...",
  "BAILIAN_WORKSPACE_ID": "llm-xxx",
  "ALIBABA_CLOUD_ACCESS_KEY_ID": "LTAI...",
  "ALIBABA_CLOUD_ACCESS_KEY_SECRET": "xxx",
  "ANTHROPIC_AUTH_TOKEN": "sk-xxx"
}
```

只填需要的，不需要的留空或不写。

## 2. 把 settings.json 加入打包

当前 `frontend/package.json` 的 `extraResources` filter 没有包含 `data/`，需要加一行：

```diff
 "filter": [
   "run_api.py",
   "src/**/*",
   "skills/**/*",
+  "data/settings.json",
   "requirements.txt"
 ]
```

位置：`frontend/package.json` → `build.extraResources[0].filter` 数组里。

> 不要用 `data/**/*`，否则会把 memories.db、checkpoints.db、tmp/ 等运行时数据也打包进去。

## 3. 打包命令

```bash
cd frontend
npm run build
npx electron-builder --win
```

产物在 `frontend/release/`：
- `econ-agent Setup 0.4.1-econ.exe` — NSIS 安装包
- `win-unpacked/econ-agent.exe` — 免安装版

## 4. 验证

安装后检查：
- 打开设置面板，API Key 应该已经显示 `****xxxx`（脱敏后的值）
- 直接发消息，Agent 能正常回复（不需要用户手动填 Key）
