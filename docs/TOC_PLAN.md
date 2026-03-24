# econ-agent ToC 产品化开发计划

> **给谁看的**：拉取本仓库后负责实施 ToC 改造的开发者。本文档包含完整的架构说明、代码改动细节和验证方法。
>
> **仓库**：https://github.com/CZcoco/econ-agent-build （main 分支，v0.6.6）
>
> **日期**：2026-03-24

---

## 一、背景与目标

### 当前状态
econ-agent v0.6.6 是一个**单用户 Electron 桌面应用**，内嵌 Python 后端（FastAPI），通过第三方 API 中转站调用 Claude/GPT。用户需要自己配置 API Key。

### 要解决的问题
1. **API 中转站不稳定**：6 条线路经常挂，sub-agent 执行到一半断掉，整个任务白费
2. **无法按用户计费**：代码里零用量统计，API Key 是开发者的，无法区分用户
3. **知识库需用户配置**：百炼 RAG 需要阿里云 AK/SK，普通学生不可能自己配
4. **安装门槛高**：110MB 安装包 + 首启装依赖 + 配 Key，流失率极高

### 目标产品
面向大学生的付费论文助手：注册 → 充值/开会员 → 打开就用 → 自动出论文初稿。

### 核心决策

| 决策 | 选择 |
|------|------|
| 客户端 | 保留 Electron 桌面版，app 内登录 |
| 中间层 | **New API**（github.com/QuantumNous/new-api）作为 LLM 代理网关 |
| 模型 | **排除 qwen**，DeepSeek 优先测试，通过 New API 可随时加减模型 |
| 计费 | 三档订阅：免费(5万tokens/月) / 基础¥29(100万) / 专业¥79(500万)，超出按量 |
| 支付 | New API 网页充值（EPay 接微信/支付宝），app 内显示余额 + "充值"跳转浏览器 |
| 知识库 | VPS 服务端代理百炼调用，用户无需配置 |
| 模型列表 | 动态从 New API 拉取，后台加模型 → 客户端自动出现，无需发版 |

---

## 二、目标架构

```
┌─────────────────────────────────────────────────────┐
│  用户电脑 (Electron)                                 │
│  ┌──────────────┐   ┌──────────────────────────┐    │
│  │ React 前端   │──▶│ 本地 Python FastAPI       │    │
│  │ (登录/余额/  │   │ (Agent 逻辑，不变)         │    │
│  │  对话/模型)  │   │ base_url → New API 服务器  │    │
│  └──────────────┘   └──────┬───────────┬────────┘    │
│                            │           │             │
└────────────────────────────┼───────────┼─────────────┘
                             │ LLM 调用   │ RAG 检索
                             ▼           ▼
┌────────────────────────────────────────────────────────┐
│  VPS 服务器 (Docker)                                    │
│                                                        │
│  ┌──────────┐   ┌──────────────────┐   ┌───────────┐  │
│  │ Caddy    │──▶│ New API :3000    │   │ RAG Proxy  │  │
│  │ :443     │   │ - 用户注册/登录   │   │ :8100     │  │
│  │ (HTTPS)  │   │ - token 分发     │   │ - 百炼调用 │  │
│  │          │   │ - LLM 代理转发   │   │ - 服务端   │  │
│  │          │   │ - token 计量     │   │   AK/SK   │  │
│  │          │   │ - 额度/计费管理  │   │           │  │
│  └──────────┘   └────────┬─────────┘   └───────────┘  │
│                          │                             │
│                          ▼                             │
│                    DeepSeek API                        │
│                    (api.deepseek.com)                  │
└────────────────────────────────────────────────────────┘
```

### 与现有架构的对应关系

| 现有（v0.6.6） | 改造后 | 改动大小 |
|----------------|--------|---------|
| `config.py`: 8 个中转站模型硬编码 | 只配一个 New API 地址，模型列表动态拉取 | **重写** |
| `get_llm()`: 分 Anthropic/OpenAI 两种构造 | 统一 `ChatOpenAI`（New API 兼容格式） | **简化** |
| `settings.py`: 10 个 API Key 字段 | 只剩 `ECON_USER_TOKEN` | **精简** |
| `rag.py`: 客户端直连百炼 | HTTP 请求到 VPS RAG 代理 | **重写** |
| `app.py`: AgentManager 遍历 MODEL_CONFIG | 从 New API `/v1/models` 拉取 | **修改** |
| `ModelSelector.tsx`: 硬编码模型名/优先级/fallback | 从 API 动态渲染 | **重写** |
| `SettingsPanel.tsx`: 10 个 API Key 输入框 | 删除或仅保留非敏感设置 | **大幅简化** |
| `Sidebar.tsx`: 无用户信息 | 底部加用户名+余额+退出 | **新增** |
| `App.tsx`: 无登录门控 | 加 AuthScreen 门控 | **修改** |
| 无 | `AuthScreen.tsx` 登录/注册页面 | **新建** |
| 无 | `src/api/auth.py` 后端 auth 服务 | **新建** |
| 无 | `rag-proxy/` VPS 上的 RAG 代理服务 | **新建** |

---

## 三、分阶段实施

---

### Phase 0：验证 DeepSeek 驱动全流程（本地，零架构改动）

**目标**：确认国产模型能跑通 选题→文献→实证→Word 全流程。如果 DeepSeek 不达标，Phase 1 需要在 New API 里加 Claude channel。

#### 0.1 启用 literature-agent

**文件**：`src/agent/main.py`，lines 97-102

当前 literature-agent 被注释掉了，取消注释即可：

```python
# 改前（lines 97-102）：
#     {
#         "name": "literature-agent",
#         "description": "用于搜索和整理学术文献、生成参考文献列表。调用时机：选题确定后，需要文献综述时；或需要验证某篇引用是否真实存在时。",
#         "system_prompt": LITERATURE_AGENT_PROMPT,
#         "tools": [internet_search, fetch_website, bailian_rag, run_python],
#     },

# 改后：
            {
                "name": "literature-agent",
                "description": "用于搜索和整理学术文献、生成参考文献列表。调用时机：选题确定后，需要文献综述时；或需要验证某篇引用是否真实存在时。",
                "system_prompt": LITERATURE_AGENT_PROMPT,
                "tools": [internet_search, fetch_website, bailian_rag, run_python],
            },
```

对应的 prompt `LITERATURE_AGENT_PROMPT` 已定义在 `src/agent/prompts.py`，无需改动。

#### 0.2 验证 DeepSeek 配置

**文件**：`src/agent/config.py`，lines 207-213

当前配置：
```python
"deepseek": {
    "base_url": "https://www.autodl.art/api/v1",
    "model": "DeepSeek-V3.2",
    "env_key": "MODEL_API_KEY",
    "max_input_tokens": 131072,
    "frequency_penalty": 0.3,
},
```

确认事项：
- `autodl.art` 这个 base_url 是否仍然可用？如不可用换成 `https://api.deepseek.com/v1`
- `MODEL_API_KEY` 环境变量是否设置了有效的 DeepSeek key
- 模型名 `DeepSeek-V3.2` 是否正确（DeepSeek 官方 API 用的是 `deepseek-chat`）

**注意**：DeepSeek 不支持图像输入。`stream.py` line 77 已有降级处理（`if model.startswith("deepseek")`），无需改动。

#### 0.3 任务失败重试机制

**文件**：`src/api/stream.py`

当前问题：sub-agent 连续 5 次工具失败后直接停止（line 149），主对话也停了，之前做的全丢。

**改动 1**：在 `_run_agent` 的 `except` 块（line 179）加入 API 层面的重试

```python
# 改前（line 179）：
except Exception as e:
    logger.error("Agent stream error: %s", e, exc_info=True)
    err_msg = str(e)
    ...

# 改后：加入可重试异常的识别
import httpx
import time

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRIES = 3

# 在 _run_agent 函数内部，包裹 agent.stream() 调用：
for attempt in range(MAX_RETRIES):
    try:
        for stream_mode, data in agent.stream(...):
            # ... 现有逻辑不变 ...
        break  # 正常结束，跳出重试
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

**改动 2**：新增重试端点

**文件**：`src/api/routes.py`

```python
@router.post("/chat/retry")
def chat_retry(req: ChatRequest, request: Request):
    """基于 LangGraph checkpoint 重放最后一条用户消息"""
    # 1. 读取 thread_id 对应的 checkpoint
    # 2. 从 checkpoint 的 messages 里找到最后一条 HumanMessage
    # 3. 重新调用 stream_to_sse 发送该消息
    # 实现思路：复用 chat_stream 逻辑，但不传新消息，而是从 checkpoint 恢复
```

#### 0.4 端到端测试

手动测试流程：
1. 启动后端：`python run.py deepseek`
2. 发送选题请求 → 验证 topic-agent 被调用
3. 要求文献综述 → 验证 literature-agent 被调用
4. 要求实证分析 → 验证 empirical-agent 执行 Python 回归
5. 要求生成论文 → 验证 writing-agent 生成 Word 文件到 `/workspace/`
6. 评估质量：公式是否正确、引用是否真实、回归结果是否合理

**Phase 0 的产出**：一份 DeepSeek 可行性评估报告，决定是否需要在 New API 里加 Claude 作为高端模型。

---

### Phase 1：部署 New API + 服务端 RAG 代理

**目标**：所有 LLM 调用走 New API 服务器，知识库走服务端代理。用户不再接触任何 API Key。

#### 1.1 VPS 部署 New API

**服务器要求**：
- 国内云（阿里云 ECS / 腾讯云 CVM），2 vCPU + 4GB RAM 即可
- 装 Docker + Docker Compose
- 域名（如 `api.econ-agent.com`），配 HTTPS

**docker-compose.yml**：

```yaml
version: "3"
services:
  new-api:
    image: calciumion/new-api:latest
    container_name: new-api
    ports:
      - "3000:3000"
    volumes:
      - ./data/new-api:/data
    environment:
      - SQL_DSN=sqlite:///data/one-api.db
      - SESSION_SECRET=<生成一个随机字符串>
      - REGISTER_ENABLED=true
      # 可选：开启验证码防注册滥用
      # - TURNSTILE_SECRET_KEY=<cloudflare-turnstile-secret>
    restart: always

  rag-proxy:
    build: ./rag-proxy
    container_name: rag-proxy
    ports:
      - "8100:8100"
    environment:
      - ALIBABA_CLOUD_ACCESS_KEY_ID=<你的阿里云AK>
      - ALIBABA_CLOUD_ACCESS_KEY_SECRET=<你的阿里云SK>
      - BAILIAN_WORKSPACE_ID=<你的百炼空间ID>
      - BAILIAN_INDEX_ID=<默认知识库索引ID>
    restart: always

  caddy:
    image: caddy:latest
    container_name: caddy
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
    restart: always

volumes:
  caddy_data:
```

**Caddyfile**：

```
api.econ-agent.com {
    # New API（LLM 代理 + 用户管理）
    handle /v1/* {
        reverse_proxy new-api:3000
    }
    handle /api/* {
        reverse_proxy new-api:3000
    }
    handle /topup* {
        reverse_proxy new-api:3000
    }
    # RAG 代理
    handle /rag/* {
        reverse_proxy rag-proxy:8100
    }
    # New API 前端页面（注册/登录/充值）
    handle {
        reverse_proxy new-api:3000
    }
}
```

**New API 后台配置步骤**：
1. 首次访问 `https://api.econ-agent.com` → 默认管理员 `root` / `123456`（立即改密码）
2. 系统管理 → 添加渠道（Channel）：
   - 类型：DeepSeek
   - Base URL：`https://api.deepseek.com`
   - 密钥：你的 DeepSeek API Key
   - 模型：`deepseek-chat`
3. 如果要加 Claude：类型 Anthropic，Base URL 直连或用稳定中转
4. 系统管理 → 运营设置：
   - 设置模型倍率（不同模型消耗不同积分）
   - 配置用户分组（free / basic / pro）
5. 如果用 EPay 支付：系统管理 → 支付设置 → 填入 EPay 商户信息

#### 1.2 服务端 RAG 代理

**新建独立项目**：`rag-proxy/`（部署在 VPS，与 New API 同一台机器）

**目录结构**：
```
rag-proxy/
├── Dockerfile
├── requirements.txt
├── main.py
```

**main.py**：

```python
"""百炼知识库服务端代理 - 用户无需配置 AK/SK"""
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

# 延迟初始化百炼客户端
_manager = None

def get_manager():
    global _manager
    if _manager is None:
        from alibabacloud_bailian20231229.client import Client
        from alibabacloud_tea_openapi.models import Config
        config = Config(
            access_key_id=os.environ["ALIBABA_CLOUD_ACCESS_KEY_ID"],
            access_key_secret=os.environ["ALIBABA_CLOUD_ACCESS_KEY_SECRET"],
            endpoint="bailian.cn-beijing.aliyuncs.com",
        )
        _manager = Client(config)
    return _manager


class RetrieveRequest(BaseModel):
    query: str
    index_id: str | None = None


@app.post("/rag/retrieve")
def retrieve(req: RetrieveRequest):
    workspace_id = os.environ.get("BAILIAN_WORKSPACE_ID")
    index_id = req.index_id or os.environ.get("BAILIAN_INDEX_ID")
    if not workspace_id or not index_id:
        raise HTTPException(400, "知识库未配置")

    try:
        mgr = get_manager()
        from alibabacloud_bailian20231229.models import RetrieveRequest as BailianReq
        bailian_req = BailianReq(
            query=req.query,
            index_id=index_id,
        )
        resp = mgr.retrieve(workspace_id, bailian_req)
        # 提取检索结果
        nodes = resp.body.data.nodes if resp.body.data else []
        results = []
        for node in nodes:
            results.append({
                "text": node.text,
                "score": node.score,
                "metadata": node.metadata,
            })
        return {"results": results}
    except Exception as e:
        raise HTTPException(500, f"检索失败: {e}")


@app.get("/rag/health")
def health():
    return {"status": "ok"}
```

**Dockerfile**：
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
COPY main.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8100"]
```

**requirements.txt**：
```
fastapi
uvicorn
alibabacloud-bailian20231229
alibabacloud-tea-openapi
```

#### 1.3 改 config.py：动态模型 + 指向 New API

**文件**：`src/agent/config.py`

这是**最核心的改动**。当前 `get_llm()` 根据 `MODEL_CONFIG` 字典硬编码了 8 个模型，分 Anthropic 和 OpenAI 两种构造方式。改造后统一走 `ChatOpenAI`（因为 New API 把所有模型都转成 OpenAI 兼容格式）。

**改前**（完整代码见文件 lines 158-294）：
```python
MODEL_CONFIG: dict[str, ModelConfigEntry] = {
    "gpt": {"base_url": "https://apiport.cc.cd/v1", "env_key": "OPENAI_API_KEY", ...},
    "claude-opus": {"provider": "anthropic", "base_url": "https://apicn.ai", "env_key": "ANTHROPIC_AUTH_TOKEN", ...},
    "claude-sonnet": {...},
    "claude-opus-hon": {...},
    "claude-sonnet-hon": {...},
    "claude-opus-plan": {...},
    "claude-sonnet-plan": {...},
    "deepseek": {"base_url": "https://www.autodl.art/api/v1", "env_key": "MODEL_API_KEY", ...},
}

def get_llm(model_name: str = "claude-sonnet") -> ChatOpenAI | ChatAnthropic:
    config = MODEL_CONFIG[model_name]
    api_key = os.getenv(config["env_key"])
    if config.get("provider") == "anthropic":
        # 复杂的 header 处理...
        return ChatAnthropic(...)
    else:
        # OpenAI 兼容构造...
        return ChatOpenAI(...)
```

**改后**：

```python
"""模型配置 - ToC 版（所有调用走 New API）"""
import os
from langchain_openai import ChatOpenAI
from pydantic import SecretStr


# New API 服务器地址（环境变量或默认值）
NEW_API_BASE_URL = os.environ.get("NEW_API_URL", "https://api.econ-agent.com/v1")


def get_llm(model_name: str = "deepseek-chat") -> ChatOpenAI:
    """获取 LLM 实例 - 所有模型统一走 New API（OpenAI 兼容格式）

    model_name: New API 中配置的模型 ID（如 "deepseek-chat", "claude-sonnet-4-6"）
    认证：使用 ECON_USER_TOKEN 环境变量（用户登录后自动设置的 New API token）
    """
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

**注意**：
- 可以删除整个 `CompatChatOpenAI` 类（lines 14-113）、`ModelConfigEntry` TypedDict、`AnthropicFactory`/`OpenAIFactory` Protocol——它们都是为中转站兼容而写的
- 可以删除 `from langchain_anthropic import ChatAnthropic` 导入
- `create_econ_agent()` 中的 `get_llm(model_name)` 调用不需要改（签名兼容）
- `max_input_tokens` / `profile` 注入暂时去掉，后续根据模型动态判断

#### 1.4 模型列表动态化

**文件**：`src/api/app.py`，`AgentManager.available_models()` method（lines 96-107）

**改前**：
```python
def available_models(self) -> list[dict]:
    """返回可用模型列表（有 API Key 的才算可用）"""
    models = []
    for name, cfg in MODEL_CONFIG.items():
        has_key = bool(os.getenv(cfg["env_key"]))
        models.append({
            "id": name,
            "name": name,
            "model": cfg["model"],
            "available": has_key,
        })
    return models
```

**改后**：
```python
def available_models(self) -> list[dict]:
    """从 New API 动态获取可用模型列表"""
    import httpx
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

需要在文件顶部加 `from src.agent.config import NEW_API_BASE_URL`。

同时 `AgentManager.get()` 中调用 `create_econ_agent(model_name=model_name, ...)` 时，`model_name` 现在是 New API 返回的模型 ID（如 `deepseek-chat`），而不是之前的 config key（如 `deepseek`）。`get_llm(model_name)` 会直接用这个 ID 构造 `ChatOpenAI(model=model_name)`，所以是兼容的。

**文件**：`frontend/src/components/ModelSelector.tsx`（整个文件重写）

**改前**（155 行，大量硬编码）：
- `MODEL_LABELS`: 8 个模型的中文名映射
- `MODEL_FALLBACKS`: 每个模型的降级链
- `MODEL_PRIORITY`: 模型优先级排序
- `resolveFallbackModel()`: 复杂的降级逻辑

**改后**（简化到 ~80 行）：

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
        // 如果当前选中的模型不在列表里，自动选第一个
        if (available.length > 0 && !available.some((m) => m.id === value)) {
          onChange(available[0].id);
        }
      })
      .catch(() => { if (!cancelled) setModels([]); });
    return () => { cancelled = true; };
  }, [refreshKey]);

  // 点击外部关闭
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

#### 1.5 改 RAG 工具调用服务端代理

**文件**：`src/tools/rag.py`（整个文件重写）

**改前**（103 行）：直接导入 `BailianKBManager`，用客户端 AK/SK 调阿里云

**改后**（~30 行）：

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
    rag_url = os.environ.get("RAG_PROXY_URL", "https://api.econ-agent.com/rag/retrieve")

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

**注意**：
- 不再需要 `threading.Lock`、`_rag_kb_configs`、`_get_cached_manager()` 等——知识库配置在服务端
- 不再需要 `ALIBABA_CLOUD_ACCESS_KEY_ID` 等环境变量在客户端
- 删除 `src/tools/kb_uploader.py` 中的客户端调用逻辑（或保留但标记为 server-only）

#### 1.6 简化 settings.py

**文件**：`src/settings.py`

**改前** SETTINGS_SCHEMA（lines 18-40）：
```python
SETTINGS_SCHEMA = [
    {"group": "模型 API", "keys": [
        {"key": "ANTHROPIC_AUTH_TOKEN", ...},
        {"key": "ANTHROPIC_HON_TOKEN", ...},
        {"key": "ANTHROPIC_SUB_TOKEN", ...},
        {"key": "OPENAI_API_KEY", ...},
        {"key": "MODEL_API_KEY", ...},
        {"key": "TAVILY_API_KEY", ...},
        {"key": "MINERU_API_KEY", ...},
        {"key": "DASHSCOPE_API_KEY", ...},
    ]},
    {"group": "百炼知识库", "keys": [
        {"key": "ALIBABA_CLOUD_ACCESS_KEY_ID", ...},
        {"key": "ALIBABA_CLOUD_ACCESS_KEY_SECRET", ...},
        {"key": "BAILIAN_WORKSPACE_ID", ...},
    ]},
]
```

**改后**：
```python
SETTINGS_SCHEMA = [
    {"group": "服务配置", "keys": [
        {"key": "NEW_API_URL", "label": "服务器地址", "sensitive": False},
        # ECON_USER_TOKEN 由登录流程自动设置，不在设置面板显示
        # TAVILY_API_KEY 如果搜索也迁移到服务端，也可以删
    ]},
]
```

大部分 key 都不需要了。`ECON_USER_TOKEN` 由登录流程写入 `settings.json`，不需要用户手动配置。

#### 1.7 清理 app.py 客户端 KB 初始化

**文件**：`src/api/app.py`

在 `lifespan()` 函数中（约 lines 367-376），有一段初始化 `BailianKBManager` 的代码：

```python
# 改前：
if os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID") and os.environ.get("BAILIAN_WORKSPACE_ID"):
    try:
        from src.tools.kb_uploader import BailianKBManager
        app.state.kb_manager = BailianKBManager()
    except Exception as e:
        logger.warning("KB manager init failed: %s", e)

# 改后：删除这段代码
# 知识库管理功能迁移到服务端，客户端不再直接连百炼
```

同时在 `routes.py` 中，删除或注释掉知识库管理相关的路由（上传/删除文档到百炼的端点），因为这些操作现在应该在 VPS 服务端进行。保留 `/api/kb/rag/config` 端点的查询功能（如果前端仍需要展示知识库列表）。

---

### Phase 2：App 内登录 + 计费 UI

**目标**：用户在 app 内注册/登录，看到余额，没钱跳转充值页面。

#### 2.1 后端 Auth 服务

**新建文件**：`src/api/auth.py`

```python
"""用户认证服务 - 封装 New API 的注册/登录/用户信息接口"""
import os
import httpx
import logging

logger = logging.getLogger(__name__)

NEW_API_URL = os.environ.get("NEW_API_URL", "https://api.econ-agent.com")


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def register(username: str, password: str, email: str = "") -> dict:
    """注册新用户"""
    resp = httpx.post(
        f"{NEW_API_URL}/api/user/register",
        json={"username": username, "password": password, "email": email},
        timeout=15,
    )
    data = resp.json()
    if not data.get("success"):
        raise AuthError(data.get("message", "注册失败"))
    return data


def login(username: str, password: str) -> dict:
    """登录并获取 API token

    流程：
    1. POST /api/user/login → 获取 session cookie
    2. POST /api/token → 创建 API token（sk-...）
    3. GET /api/user/self → 获取用户信息（余额等）
    4. 返回 {token, user_info}
    """
    # Step 1: 登录获取 session
    with httpx.Client(timeout=15) as client:
        login_resp = client.post(
            f"{NEW_API_URL}/api/user/login",
            json={"username": username, "password": password},
        )
        login_data = login_resp.json()
        if not login_data.get("success"):
            raise AuthError(login_data.get("message", "登录失败"))

        # New API 登录成功后在 data 字段返回 JWT token
        session_token = login_data.get("data", "")

        # Step 2: 用 session token 创建 API key
        token_resp = client.post(
            f"{NEW_API_URL}/api/token",
            json={"name": "econ-agent-app", "remain_quota": 0, "unlimited_quota": True},
            headers={"Authorization": f"Bearer {session_token}"},
        )
        token_data = token_resp.json()
        api_key = token_data.get("data", {}).get("key", "") if token_data.get("success") else ""

        # 如果创建 token 失败，可能已有 token，尝试获取
        if not api_key:
            list_resp = client.get(
                f"{NEW_API_URL}/api/token?p=0&size=1",
                headers={"Authorization": f"Bearer {session_token}"},
            )
            list_data = list_resp.json()
            tokens = list_data.get("data", [])
            if tokens:
                api_key = tokens[0].get("key", "")

        if not api_key:
            raise AuthError("获取 API Token 失败")

        # Step 3: 获取用户信息
        user_resp = client.get(
            f"{NEW_API_URL}/api/user/self",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        user_data = user_resp.json()
        user_info = user_data.get("data", {})

    return {
        "token": api_key,         # sk-... 格式的 API key，用于 LLM 调用
        "session": session_token, # JWT，用于查询用户信息
        "user": {
            "username": user_info.get("username", username),
            "quota": user_info.get("quota", 0),
            "used_quota": user_info.get("used_quota", 0),
            "group": user_info.get("group", "free"),
        },
    }


def get_user_info(session_token: str) -> dict:
    """查询用户信息（余额、用量等）"""
    resp = httpx.get(
        f"{NEW_API_URL}/api/user/self",
        headers={"Authorization": f"Bearer {session_token}"},
        timeout=10,
    )
    data = resp.json()
    if not data.get("success"):
        raise AuthError(data.get("message", "获取用户信息失败"), 401)
    user = data.get("data", {})
    return {
        "username": user.get("username", ""),
        "quota": user.get("quota", 0),
        "used_quota": user.get("used_quota", 0),
        "group": user.get("group", "free"),
    }
```

#### 2.2 后端 Auth 路由

**文件**：`src/api/routes.py`

在文件顶部的路由定义区域新增 auth 端点：

```python
from src.api.auth import register as auth_register_fn, login as auth_login_fn, get_user_info, AuthError
from src.settings import update_settings, load_settings
from src.agent.main import DATA_DIR

# --- Auth ---

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str = ""

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/auth/register")
def auth_register(req: RegisterRequest):
    try:
        result = auth_register_fn(req.username, req.password, req.email)
        return {"ok": True, "message": "注册成功"}
    except AuthError as e:
        return JSONResponse(status_code=e.status_code, content={"ok": False, "message": e.message})

@router.post("/auth/login")
def auth_login(req: LoginRequest):
    try:
        result = auth_login_fn(req.username, req.password)
        # 将 token 存入 settings.json 和环境变量
        token = result["token"]
        session = result["session"]
        os.environ["ECON_USER_TOKEN"] = token
        os.environ["ECON_SESSION_TOKEN"] = session
        # 持久化到 settings.json
        current = load_settings(DATA_DIR)
        current["ECON_USER_TOKEN"] = token
        current["ECON_SESSION_TOKEN"] = session
        from src.settings import save_settings
        save_settings(DATA_DIR, current)
        # 清除 agent 缓存（token 变了）
        from fastapi import Request as Req
        # 注意：这里需要从 app.state 获取 manager，通过 request 参数
        return {"ok": True, "user": result["user"], "token": token}
    except AuthError as e:
        return JSONResponse(status_code=e.status_code, content={"ok": False, "message": e.message})

@router.get("/auth/user")
def auth_user_info():
    session = os.environ.get("ECON_SESSION_TOKEN", "")
    if not session:
        return JSONResponse(status_code=401, content={"ok": False, "message": "未登录"})
    try:
        user = get_user_info(session)
        return {"ok": True, "user": user}
    except AuthError as e:
        return JSONResponse(status_code=e.status_code, content={"ok": False, "message": e.message})

@router.post("/auth/logout")
def auth_logout():
    os.environ.pop("ECON_USER_TOKEN", None)
    os.environ.pop("ECON_SESSION_TOKEN", None)
    # 从 settings.json 删除
    current = load_settings(DATA_DIR)
    current.pop("ECON_USER_TOKEN", None)
    current.pop("ECON_SESSION_TOKEN", None)
    from src.settings import save_settings
    save_settings(DATA_DIR, current)
    return {"ok": True}
```

**注意**：`auth_login` 需要能访问 `request.app.state.agent_manager` 来清缓存。可以把 `request: Request` 加到参数里。

#### 2.3 后端 Auth 中间件

**文件**：`src/api/app.py`

在 `lifespan()` 后面，给 app 加中间件：

```python
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class AuthMiddleware(BaseHTTPMiddleware):
    # 不需要认证的路径
    EXEMPT_PATHS = {"/api/health", "/api/auth/login", "/api/auth/register", "/api/install-status"}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(p) for p in self.EXEMPT_PATHS):
            return await call_next(request)
        token = os.environ.get("ECON_USER_TOKEN", "")
        if not token:
            return JSONResponse(status_code=401, content={"ok": False, "message": "请先登录"})
        return await call_next(request)

# 在 app 创建后添加：
app.add_middleware(AuthMiddleware)
```

#### 2.4 前端 Auth API 函数

**新建文件**：`frontend/src/lib/auth.ts`

```typescript
import { BASE_URL } from "./api";

export interface UserInfo {
  username: string;
  quota: number;
  used_quota: number;
  group: string;
}

export async function login(username: string, password: string): Promise<{ user: UserInfo; token: string }> {
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const data = await res.json();
  if (!data.ok) throw new Error(data.message || "登录失败");
  return data;
}

export async function register(username: string, password: string, email?: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password, email: email || "" }),
  });
  const data = await res.json();
  if (!data.ok) throw new Error(data.message || "注册失败");
}

export async function getUserInfo(): Promise<UserInfo | null> {
  try {
    const res = await fetch(`${BASE_URL}/auth/user`);
    if (res.status === 401) return null;
    const data = await res.json();
    if (!data.ok) return null;
    return data.user;
  } catch {
    return null;
  }
}

export async function logout(): Promise<void> {
  await fetch(`${BASE_URL}/auth/logout`, { method: "POST" });
}
```

#### 2.5 前端 Auth Hook

**新建文件**：`frontend/src/hooks/useAuth.ts`

```typescript
import { useState, useEffect, useCallback } from "react";
import { login as apiLogin, register as apiRegister, getUserInfo, logout as apiLogout, type UserInfo } from "@/lib/auth";

export function useAuth() {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  // 启动时检查是否已登录
  useEffect(() => {
    getUserInfo()
      .then(setUser)
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const { user } = await apiLogin(username, password);
    setUser(user);
  }, []);

  const register = useCallback(async (username: string, password: string, email?: string) => {
    await apiRegister(username, password, email);
  }, []);

  const logout = useCallback(async () => {
    await apiLogout();
    setUser(null);
  }, []);

  const refreshBalance = useCallback(async () => {
    const info = await getUserInfo();
    if (info) setUser(info);
  }, []);

  return { user, loading, login, register, logout, refreshBalance };
}
```

#### 2.6 登录/注册页面

**新建文件**：`frontend/src/components/AuthScreen.tsx`

实现一个全屏登录/注册表单，两个 tab 切换。风格沿用现有的 sand-tone 设计系统。

关键要素：
- 用户名/密码输入框
- 登录/注册按钮
- 错误提示
- "注册"tab 额外显示邮箱输入框（可选）
- 底部显示产品名和版本

#### 2.7 修改 App.tsx 加入 Auth 门控

**文件**：`frontend/src/App.tsx`

**改动 1**：导入 auth 相关模块

```typescript
// 新增导入
import { useAuth } from "@/hooks/useAuth";
const AuthScreen = lazy(() => import("@/components/AuthScreen"));
```

**改动 2**：在 `App()` 组件顶部加入 auth 状态

```typescript
export default function App() {
  const { user, loading, login, register, logout, refreshBalance } = useAuth();

  // 未登录：显示登录页面
  if (loading) return <div className="flex items-center justify-center h-screen">加载中...</div>;
  if (!user) return (
    <Suspense fallback={null}>
      <AuthScreen onLogin={login} onRegister={register} />
    </Suspense>
  );

  // 已登录：显示正常界面（现有代码）
  // ...
```

**改动 3**：在界面头部/底部显示余额

在 ChatInput 区域旁边（或 Sidebar 底部）添加：
```tsx
<div className="text-xs text-sand-400">
  余额: {user.quota - user.used_quota} tokens
  <button onClick={() => window.open("https://api.econ-agent.com/topup")}>
    充值
  </button>
</div>
```

**改动 4**：定期刷新余额

```typescript
// 每次发送消息后刷新余额
const handleSend = async (msg, ...) => {
  await sendMessage(msg, ...);
  refreshBalance();  // 新增
};
```

#### 2.8 修改 Sidebar 加用户信息

**文件**：`frontend/src/components/Sidebar.tsx`

在 `SidebarProps` 接口中新增：

```typescript
interface SidebarProps {
  // ... 现有 props ...
  user?: { username: string; quota: number; used_quota: number; group: string };
  onLogout?: () => void;
}
```

在 Sidebar 底部（Settings 按钮区域，约 line 200+）加入用户信息显示：

```tsx
{/* 用户信息 - 替换或放在 Settings 按钮旁边 */}
{props.user && (
  <div className="p-3 border-t border-sand-200">
    <div className="text-xs text-sand-600">{props.user.username}</div>
    <div className="text-xs text-sand-400">
      余额: {((props.user.quota - props.user.used_quota) / 500).toFixed(0)} 积分
    </div>
    <div className="flex gap-2 mt-1">
      <button onClick={() => window.open("https://api.econ-agent.com/topup")}
              className="text-xs text-blue-500">充值</button>
      <button onClick={props.onLogout}
              className="text-xs text-red-400">退出</button>
    </div>
  </div>
)}
```

#### 2.9 简化/删除 SettingsPanel

**文件**：`frontend/src/components/SettingsPanel.tsx`

原来 194 行，10 个 API Key 输入框。ToC 版用户不需要配任何 Key。

选择：
- **方案 A**：直接删除整个组件，`App.tsx` 中删除 `settingsOpen` 状态和 `SettingsPanel` 引用
- **方案 B**：保留但只显示"服务器地址"等非敏感设置（用于调试）

建议先用方案 A，后期有需求再恢复。

#### 2.10 修改默认模型

**文件**：`frontend/src/App.tsx`，line 31

```typescript
// 改前：
const [model, setModel] = useState(() => localStorage.getItem(STORAGE_KEY) || "gpt");

// 改后：
const [model, setModel] = useState(() => localStorage.getItem(STORAGE_KEY) || "deepseek-chat");
```

---

### Phase 3：ToC 体验打磨

#### 3.1 新手引导

**新建**：`frontend/src/components/OnboardingWizard.tsx`

首次登录后显示引导流程：
1. 欢迎页（产品介绍）
2. 简单教程（输入框里输入研究方向）
3. 示例 prompt（可点击直接发送）

用 `localStorage.getItem("econ-agent-onboarding-done")` 判断是否首次。

#### 3.2 论文模板

**文件**：`frontend/src/App.tsx` — 空对话时（lines 241-259 的 logo 区域）显示模板卡片：

```tsx
const TEMPLATES = [
  { title: "实证分析论文", prompt: "我想写一篇关于..的实证论文，请帮我从选题开始" },
  { title: "文献综述", prompt: "请帮我围绕..主题做一篇文献综述" },
  { title: "政策分析", prompt: "请帮我分析..政策的经济影响" },
];
```

#### 3.3 品牌更新

需要统一更新的位置：
- `frontend/electron/main.cjs` line 7: `app.setName("econ-agent")` → 新品牌名
- `frontend/src/App.tsx` line 252: h1 文本
- `frontend/package.json`: `productName`, `appId`
- `src/api/app.py` line 385: FastAPI title

---

## 四、环境变量变化

### 客户端（Electron app）

| 变量 | v0.6.6（改前） | ToC 版（改后） |
|------|---------------|---------------|
| `ANTHROPIC_AUTH_TOKEN` | 用户手动配 | **删除** |
| `ANTHROPIC_SUB_TOKEN` | 用户手动配 | **删除** |
| `OPENAI_API_KEY` | 用户手动配 | **删除** |
| `MODEL_API_KEY` | 用户手动配 | **删除** |
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | 用户手动配 | **删除**（迁到服务端） |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | 用户手动配 | **删除**（迁到服务端） |
| `BAILIAN_WORKSPACE_ID` | 用户手动配 | **删除**（迁到服务端） |
| `ECON_USER_TOKEN` | 不存在 | **新增**（登录后自动设置） |
| `ECON_SESSION_TOKEN` | 不存在 | **新增**（登录后自动设置） |
| `NEW_API_URL` | 不存在 | **新增**（默认 `https://api.econ-agent.com/v1`） |
| `RAG_PROXY_URL` | 不存在 | **新增**（默认 `https://api.econ-agent.com/rag/retrieve`） |

### 服务端（VPS）

| 变量 | 用途 |
|------|------|
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | RAG 代理用，调百炼 |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | RAG 代理用，调百炼 |
| `BAILIAN_WORKSPACE_ID` | RAG 代理用，指定百炼空间 |
| `BAILIAN_INDEX_ID` | RAG 代理用，默认知识库索引 |
| `SESSION_SECRET` | New API 用，JWT 签名 |

---

## 五、文件改动清单

### Phase 0（4 个文件）
| 文件 | 操作 | 说明 |
|------|------|------|
| `src/agent/main.py` | 修改 | 取消注释 literature-agent (lines 97-102) |
| `src/agent/config.py` | 修改 | 验证/修正 DeepSeek endpoint |
| `src/api/stream.py` | 修改 | 加 API 重试逻辑 |
| `src/api/routes.py` | 修改 | 新增 `/chat/retry` 端点 |

### Phase 1（6 个文件 + 1 个新服务）
| 文件 | 操作 | 说明 |
|------|------|------|
| `src/agent/config.py` | **重写** | 删除 MODEL_CONFIG，统一走 New API |
| `src/tools/rag.py` | **重写** | 改为 HTTP 请求到 VPS RAG 代理 |
| `src/settings.py` | 修改 | 删除大部分 API Key schema |
| `src/api/app.py` | 修改 | 删除 KB init，改 available_models() |
| `src/api/routes.py` | 修改 | 删除 KB 管理路由 |
| `frontend/src/components/ModelSelector.tsx` | **重写** | 动态模型列表 |
| `rag-proxy/` | **新建** | VPS 上的百炼代理服务 |

### Phase 2（10+ 个文件）
| 文件 | 操作 | 说明 |
|------|------|------|
| `src/api/auth.py` | **新建** | Auth 服务，封装 New API 接口 |
| `src/api/routes.py` | 修改 | 新增 `/auth/*` 端点 |
| `src/api/app.py` | 修改 | 加 AuthMiddleware |
| `frontend/src/lib/auth.ts` | **新建** | 前端 auth API 函数 |
| `frontend/src/hooks/useAuth.ts` | **新建** | Auth 状态管理 hook |
| `frontend/src/components/AuthScreen.tsx` | **新建** | 登录/注册页面 |
| `frontend/src/App.tsx` | 修改 | Auth 门控 + 余额显示 |
| `frontend/src/components/Sidebar.tsx` | 修改 | 用户信息 + 退出 |
| `frontend/src/components/SettingsPanel.tsx` | 删除或简化 | 不再需要 API Key 配置 |
| `frontend/src/components/ModelSelector.tsx` | 已在 Phase 1 重写 | — |

### Phase 3（5+ 个文件）
| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src/components/OnboardingWizard.tsx` | **新建** | 新手引导 |
| `frontend/src/App.tsx` | 修改 | 模板卡片 + 引导集成 |
| `src/agent/prompts.py` | 修改 | 论文模板 prompt |
| 多个文件 | 修改 | 品牌名更新 |

---

## 六、验证方法

### Phase 0 验证
```bash
# 启动后端
python run.py deepseek

# 在前端依次测试：
# 1. 发送 "我想写一篇关于数字经济对就业影响的实证论文"
# 2. 检查 topic-agent 是否被调用
# 3. 请求文献综述 → 检查 literature-agent
# 4. 请求实证分析 → 检查 empirical-agent
# 5. 请求生成 Word → 检查 writing-agent + workspace 目录下有 .docx 文件
```

### Phase 1 验证
```bash
# 1. 在 VPS 上启动 docker-compose
docker-compose up -d

# 2. 验证 New API
curl https://api.econ-agent.com/v1/models \
  -H "Authorization: Bearer sk-xxx"  # 用 New API 生成的 token

# 3. 验证 RAG 代理
curl -X POST https://api.econ-agent.com/rag/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "数字经济"}'

# 4. 本地 app 修改 config.py 后启动，发送消息
# 5. 检查 New API 后台日志：能看到该请求的 token 消耗
# 6. 检查 RAG 检索正常返回（无需客户端配百炼 AK/SK）
```

### Phase 2 验证
```
1. 启动 app → 显示登录页面（未登录）
2. 点击注册 → 填写用户名/密码 → 注册成功
3. 登录 → 进入主界面，看到余额
4. 发送一条消息 → 余额减少
5. 在 New API 后台将用户额度设为 0
6. 再发消息 → 提示"余额不足，请充值"
7. 点击"充值"按钮 → 打开浏览器到 New API 充值页面
8. 充值后回到 app → 余额恢复 → 可以继续使用
9. 点击"退出登录" → 回到登录页面
10. 重启 app → 自动恢复登录状态（token 持久化在 settings.json）
```

---

## 七、风险与缓解

| 风险 | 严重度 | 缓解措施 |
|------|--------|---------|
| DeepSeek 工具调用不可靠 | 高 | Phase 0 先验证；不行就在 New API 加 Claude channel |
| 用户反编译 app 获取 token | 低 | token 只对应该用户的额度，泄露不影响其他人 |
| New API 服务器宕机 | 中 | Docker auto-restart + 健康检查 + 监控告警 |
| 代理延迟增加 | 低 | New API 增加 ~10-50ms，相比 LLM 生成时间可忽略 |
| 注册垃圾账号 | 中 | New API 支持 Turnstile 验证码 |
| 并发用户多时 VPS 扛不住 | 中 | 初期 2c4g 够用，用户增长后升配或多节点部署 |
| New API AGPLv3 协议 | 低 | 我们不修改 New API 源码就不受影响；如需修改可买商业 license |

---

## 八、成本估算

| 项目 | 月成本（估算） |
|------|---------------|
| VPS（2c4g 阿里云） | ¥50-100 |
| 域名 + HTTPS | 免费（Caddy 自动 Let's Encrypt） |
| DeepSeek API | 按量付费，极便宜（约 ¥1/百万 tokens） |
| 百炼知识库 | 按量付费，检索费用极低 |
| **总计** | **~¥100-200/月** + DeepSeek API 用量 |
