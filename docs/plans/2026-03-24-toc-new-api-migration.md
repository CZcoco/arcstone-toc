# ToC New API 迁移实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 econ-agent 从 8 个中转站硬编码模式改为统一 New API 代理模式，为 ToC 产品化做好客户端基础。

**Architecture:** 所有 LLM 调用统一走 `http://43.128.44.82:3000/v1`（New API OpenAI 兼容格式），用 `ECON_USER_TOKEN` 认证。RAG 改为 HTTP 代理模式（服务端部署后对接）。前端模型列表从 New API 动态拉取，删除所有硬编码模型配置。

**Tech Stack:** Python FastAPI + LangChain (ChatOpenAI) + React/TypeScript + New API

**New API Server:** `http://43.128.44.82:3000`
**Test Token:** `sk-W5OtEaifQIykIk0wi1cmWQXoidycm5WmSawqouI6B3PfJSAq`

---

### Task 1: config.py — 删除硬编码，统一 New API

**Files:**
- Modify: `src/agent/config.py` (全文重写)

**Step 1: 重写 config.py**

删除 `CompatChatOpenAI`、`ModelConfigEntry`、`AnthropicFactory`/`OpenAIFactory` Protocol、`MODEL_CONFIG` 字典，统一为：

```python
"""模型配置 - ToC 版（所有调用走 New API）"""
import os
import logging
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

logger = logging.getLogger(__name__)

# New API 服务器地址
NEW_API_BASE_URL = os.environ.get("NEW_API_URL", "http://43.128.44.82:3000/v1")


def get_llm(model_name: str = "deepseek-chat") -> ChatOpenAI:
    """获取 LLM 实例 - 所有模型统一走 New API（OpenAI 兼容格式）"""
    api_key = os.environ.get("ECON_USER_TOKEN", "")
    if not api_key:
        raise ValueError("未登录：缺少用户 token（ECON_USER_TOKEN）")

    return ChatOpenAI(
        base_url=NEW_API_BASE_URL,
        model=model_name,
        api_key=SecretStr(api_key),
        timeout=120,
        max_retries=3,
    )
```

**Step 2: 验证导入兼容**

确认 `src/agent/main.py` 中 `from src.agent.config import get_llm` 调用签名兼容（`get_llm(model_name)` 不需要改）。

**Step 3: Commit**

```bash
git add src/agent/config.py
git commit -m "refactor: rewrite config.py to unified New API mode"
```

---

### Task 2: main.py — 启用 literature-agent

**Files:**
- Modify: `src/agent/main.py` (lines 97-102)

**Step 1: 取消注释 literature-agent**

将 lines 97-102 的注释取消，恢复 literature-agent 子 agent 定义。

**Step 2: Commit**

```bash
git add src/agent/main.py
git commit -m "feat: enable literature-agent subagent"
```

---

### Task 3: stream.py — 添加 API 重试逻辑

**Files:**
- Modify: `src/api/stream.py`

**Step 1: 在 _run_agent 中包裹重试逻辑**

在 `_run_agent()` 函数的 agent.stream() 调用外层添加重试包裹：

```python
import httpx
import time

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRIES = 3
```

在 `except` 块（line 179 附近）识别可重试异常：

```python
except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
    if attempt < MAX_RETRIES - 1:
        wait = 2 ** attempt
        logger.warning("API error (attempt %d/%d), retrying in %ds: %s",
                      attempt + 1, MAX_RETRIES, wait, e)
        emit(sse_event("error", {"message": f"API 暂时不可用，{wait}秒后自动重试..."}))
        time.sleep(wait)
    else:
        raise
```

**Step 2: Commit**

```bash
git add src/api/stream.py
git commit -m "feat: add API retry logic for transient failures"
```

---

### Task 4: rag.py — 改为 HTTP 代理模式

**Files:**
- Modify: `src/tools/rag.py` (全文重写)

**Step 1: 重写 rag.py**

```python
"""百炼知识库检索工具 - 通过服务端代理访问"""
import os
import httpx
from langchain_core.tools import tool


@tool
def bailian_rag(query: str) -> str:
    """从经济学论文知识库中检索相关摘要和文献信息。

    参数：
        query: 检索问题

    返回：
        检索到的相关内容
    """
    rag_url = os.environ.get("RAG_PROXY_URL", "http://43.128.44.82:3000/rag/retrieve")

    try:
        resp = httpx.post(
            rag_url,
            json={"query": query},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return "未检索到相关内容"
        texts = [r.get("text", "") for r in results if r.get("text")]
        return "\n\n---\n\n".join(texts) if texts else "未检索到相关内容"
    except Exception as e:
        return f"知识库检索失败: {e}"
```

**Step 2: Commit**

```bash
git add src/tools/rag.py
git commit -m "refactor: rewrite rag.py to use server-side proxy"
```

---

### Task 5: settings.py — 精简 API Key 配置

**Files:**
- Modify: `src/settings.py` (SETTINGS_SCHEMA + _ALL_KEYS + _SENSITIVE_KEYS)

**Step 1: 精简 SETTINGS_SCHEMA**

```python
SETTINGS_SCHEMA = [
    {"group": "服务配置", "keys": [
        {"key": "NEW_API_URL", "label": "服务器地址", "sensitive": False},
        {"key": "TAVILY_API_KEY", "label": "Tavily 搜索 API Key", "sensitive": True},
    ]},
]
```

同步更新 `_ALL_KEYS` 和 `_SENSITIVE_KEYS`。

**Step 2: Commit**

```bash
git add src/settings.py
git commit -m "refactor: simplify settings schema for New API mode"
```

---

### Task 6: app.py — 清理 KB 初始化 + 改 available_models()

**Files:**
- Modify: `src/api/app.py`

**Step 1: 删除 KB 初始化代码**

在 `lifespan()` 中删除 BailianKBManager 初始化段（约 lines 366-376）。

**Step 2: 重写 available_models()**

```python
def available_models(self) -> list[dict]:
    """从 New API 动态获取可用模型列表"""
    import httpx
    from src.agent.config import NEW_API_BASE_URL
    token = os.environ.get("ECON_USER_TOKEN", "")
    if not token:
        return []
    try:
        resp = httpx.get(
            f"{NEW_API_BASE_URL}/models",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return [
            {
                "id": m["id"],
                "name": m.get("name", m["id"]),
                "model": m["id"],
                "available": True,
            }
            for m in data
        ]
    except Exception:
        return []
```

**Step 3: Commit**

```bash
git add src/api/app.py
git commit -m "refactor: dynamic model list from New API, remove KB init"
```

---

### Task 7: routes.py — 清理 KB 管理路由

**Files:**
- Modify: `src/api/routes.py`

**Step 1: 注释或删除 KB 管理路由**

注释掉 `/kb/upload`、`/kb/delete`、`/kb/list`、`/kb/upload/status` 路由（约 lines 1017-1160）。保留 `/kb/rag/config` 如果前端仍需要。

**Step 2: Commit**

```bash
git add src/api/routes.py
git commit -m "refactor: disable client-side KB management routes"
```

---

### Task 8: ModelSelector.tsx — 动态模型列表

**Files:**
- Modify: `frontend/src/components/ModelSelector.tsx` (全文重写)

**Step 1: 重写 ModelSelector**

删除 `MODEL_LABELS`、`MODEL_FALLBACKS`、`MODEL_PRIORITY`、`resolveFallbackModel()`，改为从 API 动态获取：

```tsx
import { useState, useEffect, useRef } from "react";
import { ChevronDown } from "lucide-react";
import { listModels, type ModelInfo } from "@/lib/api";

interface ModelSelectorProps {
  value: string;
  onChange: (model: string) => void;
  disabled?: boolean;
  refreshKey?: number;
}

export default function ModelSelector({ value, onChange, disabled, refreshKey }: ModelSelectorProps) {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    listModels()
      .then(({ models }) => {
        if (cancelled) return;
        const available = models.filter((m) => m.available);
        setModels(available);
        if (available.length > 0 && !available.some((m) => m.id === value)) {
          onChange(available[0].id);
        }
      })
      .catch(() => { if (!cancelled) setModels([]); });
    return () => { cancelled = true; };
  }, [refreshKey]);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const currentModel = models.find((m) => m.id === value);
  const label = currentModel?.name || value || "未配置模型";
  const showDropdown = models.length > 1;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => !disabled && showDropdown && setOpen(!open)}
        disabled={disabled || !showDropdown}
        className="flex items-center gap-1 px-2.5 py-1.5 text-2xs font-medium
                   text-sand-500 hover:text-sand-700 hover:bg-sand-200/50
                   rounded-lg transition-colors disabled:opacity-60"
      >
        {label}
        {showDropdown && (
          <ChevronDown size={12} className={`transition-transform ${open ? "rotate-180" : ""}`} />
        )}
      </button>
      {open && showDropdown && (
        <div className="absolute bottom-full left-0 mb-1 min-w-[170px]
                        bg-white rounded-xl shadow-[0_4px_16px_rgba(0,0,0,0.1),0_0_0_1px_rgba(0,0,0,0.04)]
                        py-1 animate-fade-in z-50 whitespace-nowrap">
          {models.map((m) => (
            <button
              key={m.id}
              onClick={() => { onChange(m.id); setOpen(false); }}
              className={`flex items-center justify-between w-full px-3.5 py-2 text-[0.8125rem]
                         transition-colors
                         ${m.id === value
                           ? "text-sand-800 bg-sand-50 font-medium"
                           : "text-sand-600 hover:bg-sand-50"}`}
            >
              <span>{m.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/ModelSelector.tsx
git commit -m "refactor: rewrite ModelSelector for dynamic New API models"
```

---

### Task 9: App.tsx — 更新默认模型

**Files:**
- Modify: `frontend/src/App.tsx` (line 31)

**Step 1: 改默认模型**

```typescript
// 改前：
const [model, setModel] = useState(() => localStorage.getItem(STORAGE_KEY) || "gpt");

// 改后：
const [model, setModel] = useState(() => localStorage.getItem(STORAGE_KEY) || "deepseek-chat");
```

**Step 2: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "chore: default model to deepseek-chat"
```

---

### Task 10: 端到端验证

**Step 1: 设置环境变量**

```bash
export ECON_USER_TOKEN="sk-W5OtEaifQIykIk0wi1cmWQXoidycm5WmSawqouI6B3PfJSAq"
export NEW_API_URL="http://43.128.44.82:3000/v1"
```

**Step 2: 启动后端验证**

```bash
python run.py deepseek-chat
```

**Step 3: 检查项**

- [ ] 后端启动无报错
- [ ] `/api/models` 返回 New API 的模型列表
- [ ] 发送消息能收到 DeepSeek 回复
- [ ] 前端模型选择器显示动态模型列表
- [ ] 文献检索（RAG）优雅降级（服务端代理未部署时返回"检索失败"而非崩溃）
