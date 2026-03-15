# Planning 层开发计划

> 日期：2026-02-18
> 状态：L1+L3 已完成，L2 框架内置无需开发，待用户手动测试场景 2-4
> 优先级：P1
> 依赖：P0 记忆索引（已完成）
> 调研基础：`docs/research/agent-planning-research.md`

## 背景

当前 Arcstone Agent 没有显式的规划能力。模型收到复杂任务（如"全面评估这个铜矿"）后，靠 system prompt 里的"评估框架 7 大维度"隐式引导，自行决定先干什么后干什么。

**问题**：
- 复杂任务容易漏步骤、顺序混乱
- 长对话中目标偏移（lost-in-the-middle）
- 用户看不到 Agent 的分析思路，无法中途纠偏
- 执行完不会自检，容易遗漏关键信息

**目标**：通过 prompt 改造 + 1 个新工具，让 Agent 具备显式规划能力，分 3 层递进实施。

---

## 方案总览

基于调研（Lilian Weng、Anthropic、Manus、学术前沿），选择最务实的路线：

| 层次 | 内容 | 改动范围 | 难度 |
|------|------|---------|------|
| **L1** | Prompt 引导规划 + 任务路由 | 改 `prompts.py` | 低 |
| **L2** | Todo-list 注意力锚定 | 新增 1 个工具 + 改 prompt | 中 |
| **L3** | 执行后自检 | 改 `prompts.py` | 低 |

三层可以一次性实施，不涉及架构改动。

---

## L1：Prompt 引导规划 + 任务类型路由

### 设计理念

参考 Anthropic "从最简单方案开始"原则。不需要独立的 planning 模块，在 system prompt 中引导模型：
1. 识别任务复杂度（简单 vs 多步骤）
2. 多步骤任务先列计划再执行
3. 不同类型任务用不同策略

### 在 prompts.py 中新增的内容

在 `# 工具使用指南` 之后、`# 记忆管理` 之前，新增 `# 工作方法` 章节：

```
# 工作方法

## 任务识别与策略选择

收到用户消息后，先判断任务类型，选择对应的工作方式：

| 任务类型 | 典型例子 | 策略 |
|---------|---------|------|
| 简单问答 | "铜价现在多少？""什么是JORC标准？" | 直接回答或调一个工具后回答 |
| 单项分析 | "这个品位算高还是低？""帮我算下IRR" | 查资料/算一下，直接给结论 |
| 多步评估 | "全面评估这个矿""帮我做个可行性分析" | 先列计划，逐步执行（见下文） |
| 对比决策 | "A矿和B矿选哪个？""这三个项目怎么排序？" | 先分别分析，再汇总对比 |

不需要每次都列计划。简单问题直接答，复杂任务才需要规划。

## 多步任务的执行方式

遇到需要多步分析的任务时：

1. **理解需求**：用 1-2 句话确认你理解的核心问题是什么
2. **列出计划**：给出 3-5 个分析步骤（不要超过 5 个），每步说清楚要做什么、用什么工具
3. **逐步执行**：按计划顺序执行，每完成一步简要说明发现了什么
4. **综合结论**：全部完成后给出整体判断和建议

示例：

用户："帮我全面评估下 XX 铜矿"

你的回应：
"好的老朋友，我来系统评估一下这个项目。计划如下：
1. 先查项目基础资料——资源量、品位、矿体规模
2. 看开发条件——交通、电力、水源
3. 估算经济性——初步测算 CAPEX/OPEX 和 IRR
4. 评估主要风险——合规状态、地质风险、政策风险
5. 给出投资建议

我先从第 1 步开始。"

然后逐步执行，每步完成后报告发现，再进入下一步。

## 计划调整

执行过程中如果发现新情况（如缺少关键数据、发现重大风险），允许调整计划：
- 缺数据：暂停当前步骤，向用户说明需要什么信息
- 发现重大问题：提前告知用户，询问是否继续深入分析还是直接给出阶段性结论
- 不要闷头执行到底再说"数据不足无法判断"
```

### 改动文件

- `src/agent/prompts.py`：在 `# 工具使用指南` 和 `# 记忆管理` 之间插入上述内容

---

## L2：Todo-list 注意力锚定

### 设计理念

参考 Manus 的核心经验：**把计划不断推到上下文末尾，对抗"中间丢失"**。

当前 Deep Agents 框架已有 `write_todos` / `read_todos` 内置工具（通过 backend 的 StateBackend 管理）。但 Agent 不知道什么时候该用。需要：

1. 确认 Deep Agents 的 todo 工具 API（需要 WebSearch 确认）
2. 在 prompt 中引导 Agent 使用 todo 机制

### 需要确认的问题

> **重要**：Deep Agents 是 2025 年新框架，必须先搜索确认以下内容再动手：
> - `create_deep_agent` 是否内置 todo 工具？工具名叫什么？
> - todo 数据存在哪里？StateBackend 还是 StoreBackend？
> - 如果没有内置，需要自己写一个 todo 工具

### 方案 A：Deep Agents 内置 todo（如果有）

直接在 prompt 中引导使用：

```
## 进度跟踪（多步任务时使用）

执行多步计划时，用 write_todos 记录和更新进度：
- 列出计划后，立即用 write_todos 写入所有步骤
- 每完成一步，更新该步骤状态并附上简短结论
- 这样你不会在长对话中忘记整体计划和已有发现

格式示例：
☑ 1. 查询资源量 → 铜品位0.8%，333资源量500万吨
☑ 2. 评估开发条件 → 距公路15km，电力充足，水源紧张
☐ 3. 估算经济性（进行中）
☐ 4. 风险评估
☐ 5. 投资建议
```

### 方案 B：自建 todo 工具（如果 Deep Agents 没有内置）

新建 `src/tools/todo.py`：

```python
from langchain_core.tools import tool

# 内存 todo（per thread，不需要持久化，对话结束就没了）
_todos: dict[str, list[dict]] = {}

@tool
def update_todo(thread_id: str, todos: list[dict]) -> str:
    """更新当前任务的执行计划和进度。

    每个 todo 项格式：{"step": "步骤描述", "status": "done/doing/pending", "result": "执行结果摘要"}

    在执行多步分析任务时使用：
    - 列出计划后调用一次，记录所有步骤
    - 每完成一步调用一次，更新状态和结果
    """
    _todos[thread_id] = todos
    # 返回格式化的 todo 列表，会出现在上下文末尾
    lines = []
    for t in todos:
        icon = {"done": "☑", "doing": "▶", "pending": "☐"}.get(t["status"], "☐")
        line = f"{icon} {t['step']}"
        if t.get("result"):
            line += f" → {t['result']}"
        lines.append(line)
    return "当前进度：\n" + "\n".join(lines)
```

**关键设计点**：
- 工具返回值包含完整 todo 列表 → 自动出现在上下文末尾 → 注意力锚定
- 每个已完成步骤带简短结论 → 模型后续步骤能参考前面的发现
- 用内存存储，不需要持久化（todo 是单次对话内的临时规划，不是跨会话的记忆）

### 改动文件

- `src/tools/todo.py`（新建，如果走方案 B）
- `src/agent/main.py`：tools 列表中添加 `update_todo`
- `src/agent/prompts.py`：在 `# 工作方法` 中添加进度跟踪指引

---

## L3：执行后自检

### 设计理念

参考 Manus 的 Verifier 角色和 Anthropic 的 Evaluator-Optimizer 模式。不需要独立的验证 Agent，让同一个模型在完成多步分析后做一次自检。

### 在 prompts.py 中新增的内容

追加到 `# 工作方法` 章节末尾：

```
## 完成后自检（多步任务完成时必做）

完成多步分析后，在给出最终结论前，快速自检：
- 用户的原始问题完整回答了吗？有没有漏掉的维度？
- 关键数据都有来源吗？（知识库查到的 vs 网上搜的 vs 用户提供的 vs 你假设的，要区分清楚）
- 你的结论和前面的数据一致吗？（比如数据显示 IRR 只有 8%，结论却说"建议投资"）
- 有没有需要提醒用户注意的风险被遗漏？

如果自检发现问题，在最终结论中补充说明，而不是重新执行整个流程。
```

### 改动文件

- `src/agent/prompts.py`：追加到 `# 工作方法` 末尾

---

## 实施步骤

### Task 1：Prompt 改造（L1 + L3）

**文件**：`src/agent/prompts.py`

**操作**：在 `# 工具使用指南`（第 73-79 行）之后、`# 记忆管理`（第 81 行）之前，插入完整的 `# 工作方法` 章节，包含：
- 任务识别与策略选择（表格）
- 多步任务的执行方式（4 步流程 + 示例）
- 计划调整（灵活应变指引）
- 完成后自检（自检清单）

**验证**：
1. 启动 API，发送简单问题（"铜价多少"），确认 Agent 不会多此一举列计划
2. 发送复杂任务（"全面评估一个铜矿项目"），确认 Agent 先列出 3-5 步计划再逐步执行
3. 发送对比任务（"A 和 B 哪个好"），确认 Agent 先分别分析再汇总

### Task 2：Todo 工具（L2）

**前置**：WebSearch 确认 Deep Agents 是否内置 todo 工具

**如果内置**：
- 只改 `prompts.py`，添加进度跟踪指引

**如果不内置**：
- 新建 `src/tools/todo.py`
- 修改 `src/agent/main.py`：import 并添加到 tools 列表
- 修改 `prompts.py`：添加进度跟踪指引

**验证**：
1. 发送多步任务，确认 Agent 在列出计划后调用 todo 工具
2. 确认每完成一步 Agent 更新 todo 状态
3. 在 SSE 流中能看到 todo 工具调用事件（前端后续可展示为进度条）

### Task 3：端到端测试

用以下 3 个场景验证整体效果：

**场景 1 — 简单问答**：
```
用户："现在铜价多少？"
期望：直接调 web_search 返回答案，不列计划
```

**场景 2 — 多步评估**：
```
用户："我有一个贵州的铅锌矿项目，帮我全面评估下"
期望：
1. 先列出 3-5 步计划
2. 逐步执行，每步有工具调用
3. 每步完成有简要发现
4. 最后有综合结论和投资建议
5. 能看到 todo 工具调用
```

**场景 3 — 对比决策**：
```
用户："A 矿品位高但交通差，B 矿品位低但靠近港口，帮我比较下"
期望：先分别分析 A 和 B，再汇总对比，给出偏好建议
```

### Task 4：更新文档

- `docs/dev/development.md`：在架构部分新增"规划层"说明
- `docs/research/agent-planning-research.md`：已完成（调研报告）

---

## 后续扩展（不在本期范围）

| 方向 | 说明 | 触发条件 |
|------|------|---------|
| **子代理编排** | Orchestrator-Workers 模式，主代理规划+分配，子代理执行 | 评估维度需要并行处理时 |
| **KV-Cache 优化** | 系统 prompt 保持稳定，上下文 append-only | 多轮对话延迟明显增加时 |
| **分层错误处理** | 1 次重试 → 2 次换方法 → 3 次降级 | 工具调用失败率高时 |
| **Plan-and-Solve + ReAct 混合** | 模型根据任务类型自动选择策略 | L1 的简单路由不够用时 |

---

## 参考

- Lilian Weng: [LLM Powered Autonomous Agents](https://lilianweng.github.io/posts/2023-06-23-agent/)
- Anthropic: [Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
- Manus: [Context Engineering for AI Agents](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus)
- 完整调研报告：`docs/research/agent-planning-research.md`
