# API 使用指南

> 基于 [New API](https://apicn.ai) 搭建的 OpenAI 兼容中转站，支持 Claude、Sora 等模型。
> 完整官方文档：[docs.newapi.pro](https://docs.newapi.pro/zh/docs/api)

## 认证方式

所有接口均使用 Bearer Token 认证，在 `Authorization` 请求头中携带：

```
Authorization: Bearer sk-xxxxxx
```

> [!NOTE]
> New API 支持三种格式，根据请求头自动识别：
> - **OpenAI 格式**（默认）：只传 `Authorization`
> - **Anthropic 格式**：同时携带 `x-api-key` + `anthropic-version` 头
> - **Gemini 格式**：携带 `x-goog-api-key` 头或 `key` 查询参数

---

## 快速开始（Python OpenAI SDK）

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-xxxxxx",
    base_url="https://apicn.ai/v1"
)

response = client.chat.completions.create(
    model="claude-opus-4-6",
    messages=[
        {"role": "user", "content": "你好！"}
    ]
)

print(response.choices[0].message.content)
```

---

## 接口参考

### 1. 获取模型列表

```
GET https://apicn.ai/v1/models
```

**示例（Python requests）**：

```python
import requests

resp = requests.get(
    "https://apicn.ai/v1/models",
    headers={"Authorization": "Bearer sk-xxxxxx"}
)
print(resp.json())
```

**响应格式**：

```json
{
  "object": "list",
  "data": [
    {
      "id": "claude-opus-4-6",
      "object": "model",
      "created": 0,
      "owned_by": "anthropic"
    }
  ]
}
```

---

### 2. 聊天对话（Chat Completions）

```
POST https://apicn.ai/v1/chat/completions
```

**请求体**：

```json
{
  "model": "claude-opus-4-6",
  "messages": [
    {"role": "system", "content": "你是一个有帮助的助手。"},
    {"role": "user", "content": "帮我写一段 Python 快速排序代码"}
  ],
  "max_tokens": 1024,
  "temperature": 0.7,
  "stream": false
}
```

**流式输出（stream: true）示例**：

```python
response = client.chat.completions.create(
    model="claude-opus-4-6",
    messages=[{"role": "user", "content": "讲个故事"}],
    stream=True
)

for chunk in response:
    delta = chunk.choices[0].delta
    if delta.content:
        print(delta.content, end="", flush=True)
```

---

## 可用模型

| 模型名                   | 适用场景                          |
| ------------------------ | --------------------------------- |
| `claude-opus-4-6`        | 最新旗舰，复杂推理 / 代码 / Agent |
| `claude-opus-4-6-high`   | Opus 4.6 高思考预算               |
| `claude-opus-4-6-medium` | Opus 4.6 中思考预算               |
| `claude-opus-4-6-low`    | Opus 4.6 低思考预算               |
| `claude-opus-4-6-max`    | Opus 4.6 最大思考预算             |

---

## 本次实测补充

### apicn.ai（Claude 线路）

- `apicn.ai` 同时支持 **OpenAI 兼容** 和 **Anthropic 兼容** 两种调用方式。
- **OpenAI 兼容** 推荐使用：`https://apicn.ai/v1`
  - 适用于 `OpenAI SDK`、`ChatOpenAI`、`/v1/models`、`/v1/chat/completions`
- **Anthropic 兼容** 推荐使用：`https://apicn.ai`
  - 适用于 `Anthropic SDK`、`ChatAnthropic`，SDK 会自动请求 `/v1/messages`
- 本次排查里，默认 Python 请求一度返回 `403 / error code: 1010`。
- 实测在请求头中补上 `User-Agent: curl/8.0` 后，OpenAI 兼容和 Anthropic 兼容两种方式都能正常返回。
- 对当前 `econ-agent-build` 项目，最小改动接入方案是：
  - 保持 `ChatAnthropic` 写法不变
  - 将 Claude API 的 `base_url` 切到 `https://apicn.ai`
  - 同时补充 `User-Agent: curl/8.0`
- 当前项目里 Claude 线路默认读取的是 `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_SUB_TOKEN`，不是 `ANTHROPIC_API_KEY`。

### apiport.cc.cd（GPT/OpenAI 线路）

- 本次实测确认：**可用的 OpenAI 兼容入口是** `https://apiport.cc.cd/v1`。
- 对应聊天接口为：`https://apiport.cc.cd/v1/chat/completions`。
- `openai-python` 直连 `base_url="https://apiport.cc.cd/v1"` + `model="gpt-5.4"` 可返回 `200`。
- 直接 `POST https://apiport.cc.cd/v1/chat/completions` 的最小请求也可返回 `200`。
- 当前项目之前使用的 `https://chat.apiport.cc.cd/v1` **与本次实测成功入口不一致**，应避免继续使用。
- `http://106.53.52.4` / `/v1` 当前实测连接被拒绝，不应作为默认候选入口。

---

## 注意事项

- API 地址：`https://apicn.ai/v1`
- OpenAI SDK 兼容场景下，直接替换 `base_url` 和 `api_key` 即可
- Anthropic SDK 兼容场景下，`base_url` 用 `https://apicn.ai`
- 如遇 `403 / 1010`，优先检查请求头里的 `User-Agent`
- 如遇 503 错误，请联系站长确认 Token 所在分组是否包含对应模型的渠道
- 在线调试工具：[Apifox 操练场](https://apifox.newapi.ai/)
