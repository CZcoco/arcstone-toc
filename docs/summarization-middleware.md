# SummarizationMiddleware 调研笔记

> 调研日期：2026-02-23 | 结论：暂不改动，记录备查

---

## 背景

Agent 对话达到一定长度后，Deep Agents 框架会自动触发摘要压缩。调研其机制，评估是否需要调整。

---

## 核心机制

**源文件**：`deepagents/middleware/summarization.py`

### 触发条件（二选一，取决于 model.profile）

| 条件 | 有 profile | 无 profile（当前 DeepSeek/Kimi/Qwen） |
|------|-----------|--------------------------------------|
| 触发阈值 | `max_input_tokens × 0.85` | **170,000 tokens**（硬编码） |
| 摘要后保留 | `max_input_tokens × 0.10` 的最近消息 | **最近 6 条消息** |
| 工具参数截断触发 | `max_input_tokens × 0.85` | 20 条消息后 |
| 工具参数截断保留 | `max_input_tokens × 0.10` | 最近 20 条不截断 |

DeepSeek/Kimi/Qwen 使用 `ChatOpenAI` 兼容接口，LangChain 不自动填充 profile，所以走无 profile 分支。

Claude 使用 `ChatAnthropic`，LangChain 内置 profile 数据，走 fraction 分支。

### 触发后的固定动作（写死，不可配置）

1. **LLM 生成摘要**：用 `summary_prompt` 模板，喂入旧消息（最多 `trim_tokens_to_summarize` 个 token）
2. **历史写入文件**：旧消息以 markdown 追加到 `/conversation_history/{thread_id}.md`（通过 backend）
3. **替换消息**：旧消息替换为一条 `HumanMessage`，内容为摘要 + 历史文件路径引用
4. **ContextOverflowError 兜底**：即使未达阈值，模型返回上下文溢出错误时也自动触发摘要

### SummarizationMiddleware 可配置参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `trigger` | `ContextSize` | 见上表 | 何时触发摘要 |
| `keep` | `ContextSize` | 见上表 | 摘要后保留多少最近消息 |
| `summary_prompt` | `str` | 内置模板 | 生成摘要的提示词 |
| `trim_tokens_to_summarize` | `int \| None` | 4000 | 喂给 LLM 做摘要的最大 token |
| `history_path_prefix` | `str` | `/conversation_history` | 历史文件存储路径前缀 |
| `truncate_args_settings` | `dict \| None` | 见上表 | 工具参数截断策略 |
| `token_counter` | `callable` | `count_tokens_approximately` | token 计数函数 |

### 不可配置的行为

- 摘要后固定替换为 `HumanMessage`（不能改为 SystemMessage）
- 历史必定写入 markdown 文件（不能关闭）
- 摘要消息格式模板硬编码
- 工具参数截断只针对 `write_file` / `edit_file`

---

## ContextSize 类型

三种格式：

```python
("tokens", 170000)    # 绝对 token 数
("messages", 6)        # 消息条数
("fraction", 0.85)     # max_input_tokens 的百分比（需要 profile）
```

---

## model.profile 结构

来自 `langchain_core.language_models.model_profile.ModelProfile`（TypedDict, total=False）：

```python
{
    # SummarizationMiddleware 唯一使用的字段
    "max_input_tokens": 131072,    # 最大上下文窗口

    # 以下字段目前对 Summarization 无影响，但框架其他部分可能用
    "max_output_tokens": 8192,
    "text_inputs": True,
    "image_inputs": False,
    "tool_calling": True,
    "structured_output": True,
    # ... 等，共 18 个可选字段
}
```

**SummarizationMiddleware 只看 `max_input_tokens`**，其他字段无影响。

---

## 我们能怎么改（备选方案，暂不实施）

### 方案 A：给 ChatOpenAI 注入 profile（最小改动）

在 `src/agent/config.py` 的 `get_llm()` 中：

```python
llm = ChatOpenAI(...)
llm.profile = {"max_input_tokens": 131072}  # DeepSeek V3.2: 128K
```

效果：trigger 从 170k 硬编码变为 `131072 × 0.85 = 111411`，keep 从 6 条变为 `131072 × 0.10 = 13107 tokens`。

各模型 context window：

| 模型 | max_input_tokens | 触发点 (×0.85) | 保留量 (×0.10) |
|------|-----------------|---------------|---------------|
| DeepSeek V3.2 | 131,072 (128K) | ~111K | ~13K |
| Kimi K2.5 | 131,072 (128K) | ~111K | ~13K |
| Qwen 3.5 Plus | 131,072 (128K) | ~111K | ~13K |
| Claude Sonnet 4 | 200,000 | ~170K | ~20K |

### 方案 B：自己组装 middleware 栈（完全控制）

不用 `create_deep_agent`，自己调 `create_agent` + 手动拼 middleware。可以自定义所有参数，但：
- 工作量大，要拼完整栈（TodoList + Filesystem + SubAgent + Summarization + PromptCaching + PatchToolCalls）
- 框架升级后要手动同步

### 决定

**已实施方案 A（仅 DeepSeek）**。在 `src/agent/config.py` 的 `MODEL_CONFIG["deepseek"]` 中加入 `max_input_tokens: 131072`，`get_llm()` 创建 ChatOpenAI 后注入 `llm.profile`，让 SummarizationMiddleware 走 fraction 分支（0.85 触发 ≈ 111K tokens）。

其他模型（Kimi 200K、Claude 自带 profile）不需要改，170k 硬编码阈值对它们合理。

---

## 附加：工具输出截断

**源文件**：`deepagents/backends/utils.py`

| 参数 | 值 | 说明 |
|------|-----|------|
| `TOOL_RESULT_TOKEN_LIMIT` | 20,000 tokens | 单次工具返回上限 |
| 换算 | ~80,000 字符 | 按 4 chars/token 估算 |

超过此限制的工具输出会被自动截断。这个值写死在源码中，无法通过参数调整。
