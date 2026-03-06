# AI Agent 规划能力深度研究

> 调研日期：2026-02-18
> 目标：为 Arcstone 规划层设计提供理论基础和最佳实践参考

---

## 一、Lilian Weng（前 OpenAI）— LLM 驱动的自主智能体

**来源**：[LLM Powered Autonomous Agents](https://lilianweng.github.io/posts/2023-06-23-agent/)

这篇文章是 Agent 领域最经典的综述之一，将 Agent 系统分为三大核心模块：**规划（Planning）**、**记忆（Memory）**、**工具使用（Tool Use）**。

### 1.1 规划方法分类

#### （1）任务分解（Task Decomposition）

| 方法 | 原理 | 特点 |
|------|------|------|
| **Chain of Thought (CoT)** | 提示模型"逐步思考"，将复杂问题分解为简单子步骤 | 单路径推理，最基础的分解方式 |
| **Tree of Thoughts (ToT)** | 每步生成多个思考分支，用 BFS/DFS 搜索最优路径 | 多路径推理，探索不同可能性 |
| **LLM+P** | LLM 翻译为 PDDL → 经典规划器求解 → 结果回译自然语言 | 借助外部规划器，适合有领域定义的场景 |

#### （2）自我反思（Self-Reflection）

| 方法 | 原理 | 特点 |
|------|------|------|
| **ReAct** | Thought → Action → Observation 循环，推理与行动交织 | 可与环境交互，可解释性强 |
| **Reflexion** | 失败后生成反思文本，存入记忆，指导下次尝试 | 引入强化学习思想，从失败中学习 |
| **Chain of Hindsight (CoH)** | 用历史输出的质量排序来微调模型 | 通过对比好坏输出来改进 |

### 1.2 关键洞察

1. **CoT 是规划的基石**：几乎所有高级规划方法都建立在 CoT 之上
2. **反思机制是质量保障**：没有反思的规划容易"一条路走到黑"
3. **工具使用扩展了规划的可执行范围**：计算器、搜索引擎、代码执行器等让规划不只停留在文本层面

### 1.3 已知局限

- **有限上下文窗口**：历史信息无法全部装入
- **长程规划困难**：步骤越多，错误累积越严重
- **自然语言接口不可靠**：模块间传递信息容易出现格式错误
- **错误恢复能力弱**：LLM 遇到意外失败后难以灵活调整计划

---

## 二、Anthropic — 构建高效 Agent

**来源**：[Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)（2024.12，Erik Schluntz & Barry Zhang）

### 2.1 核心区分：Workflow vs Agent

Anthropic 做了一个关键区分：

| 维度 | Workflow（工作流） | Agent（智能体） |
|------|-------------------|----------------|
| **控制流** | 预定义代码路径编排 LLM | LLM 自主决定流程和工具使用 |
| **灵活性** | 低，但可预测 | 高，但不确定 |
| **适用场景** | 固定、可预测的任务 | 开放、步骤数不确定的任务 |
| **成本** | 较低 | 较高（延迟、token 消耗） |

**核心原则：从最简单的方案开始**。很多场景用单次 LLM 调用 + 检索 + 好的 prompt 就够了。

### 2.2 六种工作流模式

#### （1）Prompt Chaining（提示链）
- 任务分解为顺序步骤，每步输出是下步输入
- 步骤间可加验证门控
- **适用**：翻译流水线、文档先提纲后写作

#### （2）Routing（路由）
- 对输入分类，导向专门的处理流程
- **适用**：客服分流、模型选择（简单问题用小模型，复杂问题用大模型）

#### （3）Parallelization（并行化）
- **分段并行**：独立子任务同时执行
- **投票并行**：同一任务跑多次取共识
- **适用**：多维度评估、安全检查与内容生成并行

#### （4）Orchestrator-Workers（编排-工人）
- 中心 LLM 动态分解任务、分配给 worker LLM
- 与并行化的区别：子任务不是预定义的，而是由编排者根据输入动态决定
- **适用**：代码修改（需要改哪些文件事先不知道）、多源研究

#### （5）Evaluator-Optimizer（评估-优化循环）
- 一个 LLM 生成，另一个 LLM 评估，循环迭代
- 前提：有明确的评估标准，且迭代确实能改进质量
- **适用**：文学翻译、复杂检索

#### （6）Autonomous Agent（自主智能体）
- LLM 在循环中使用工具，每步从环境获得真实反馈
- 需要设置停止条件和人工检查点
- **适用**：开放式问题解决

### 2.3 工具设计最佳实践（Agent-Computer Interface）

Anthropic 特别强调工具设计的重要性，认为它和 prompt 工程一样关键：

1. **文档像写给初级开发者**：包含示例、边界情况、格式要求
2. **参数命名要让用法不言自明**
3. **防呆设计（Poka-yoke）**：如要求绝对路径而非相对路径
4. **格式选择**：接近模型训练数据中自然出现的格式，避免需要精确计数的格式
5. **大量测试**：用多种输入测试，找出模型犯错的模式

### 2.4 关键 Trade-off

- **复杂度 vs 性能**：复杂系统增加延迟和成本，只在确实能提升效果时才增加复杂度
- **框架的陷阱**：框架增加抽象层，让 prompt 和响应不透明、难调试。建议从直接调用 API 开始
- **错误放大**：Agent 自主性越高，错误累积风险越大，需要沙箱测试

---

## 三、Manus AI — 产品级 Agent 规划实践

**来源**：
- [Context Engineering for AI Agents: Lessons from Building Manus](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus)
- [Manus AI Architecture Technical Investigation](https://gist.github.com/renschni/4fbc70b31bad8dd57f3370239dccd58f)

Manus 是 2025 年最成功的通用 AI Agent 产品之一，其规划架构有大量实战经验可借鉴。

### 3.1 三模块协作架构

| 模块 | 角色 | 功能 |
|------|------|------|
| **Planner Agent** | 战略家 | 接收用户目标，分解为有序子任务，生成步骤计划 |
| **Executor Agent** | 执行者 | 在沙箱中执行操作（浏览器、代码、文件、API） |
| **Verifier Agent** | 审核者 | 检查执行结果是否正确，决定是否需要重做 |

### 3.2 Agent Loop 结构

每个迭代周期：
1. **分析**：评估当前状态和用户请求
2. **规划/选择行动**：决定下一步操作
3. **执行**：在沙箱环境中执行
4. **观察**：捕获结果，追加到事件流

**关键约束**：每次迭代只执行一个工具调用，防止失控执行。

### 3.3 上下文工程（核心创新）

Manus 将上下文工程视为 Agent 开发最核心的工程挑战：

#### （1）KV-Cache 命中率 = 最重要的指标
- 直接影响延迟和成本（缓存 vs 非缓存 token 成本差 10 倍）
- 保持 prompt 稳定（避免时间戳等动态内容）
- 采用只追加（append-only）的上下文，不修改历史记录
- 确定性序列化，保证相同内容生成相同 token 序列

#### （2）Todo-List 注意力操纵
- 在整个任务执行过程中不断更新 `todo.md` 文件
- 每次更新都将全局计划推送到上下文末尾（模型最近的注意力范围内）
- 有效对抗"中间丢失"（lost-in-the-middle）问题
- 平均每个任务约 50 次工具调用，这个机制确保目标不偏移

#### （3）上下文外部化
- 文件系统作为"无限大、持久化"的记忆
- 压缩是**可逆的**：删除网页内容但保留 URL，删除文档但保留路径
- 避免不可逆的信息丢失

#### （4）Action Space 管理
- 不动态增删工具（会破坏缓存），而是通过 **token logit masking** 约束可用操作
- 工具命名用统一前缀（`browser_`、`shell_`），简化约束逻辑

#### （5）错误保留
- 保留失败操作记录在上下文中，帮助模型避免重复同样的错误
- 错误恢复能力被视为"真正的 agentic 行为最清晰的指标之一"

### 3.4 CodeAct 范式
- 用可执行 Python 代码替代固定的工具 API 调用
- Agent 生成代码片段 → 沙箱执行 → 返回结果
- 实验表明，比文本工具调用在复杂任务上有显著更高的成功率

### 3.5 错误处理策略
- 从错误信息诊断失败原因
- 用调整后的方案重试
- **3 次失败后切换方法**
- 多次失败后才向用户报告无法完成

### 3.6 经验教训
- 框架重建了 **4 次**，每次都是发现更好的上下文管理方式
- 他们幽默地称之为"随机梯度下降（Stochastic Graduate Descent）"
- 选择 in-context learning 而非模型微调，以获得快速迭代能力

---

## 四、学术界 — 系统性综述与前沿进展

### 4.1 规划能力分类体系

**来源**：[Understanding the Planning of LLM Agents: A Survey](https://arxiv.org/abs/2402.02716)（2024，中科大等）

| 类别 | 方法 | 核心思想 |
|------|------|---------|
| **任务分解** | CoT、PoT（Program of Thought）| 将复杂任务简化为可执行步骤 |
| **多计划选择** | ToT、GoT、Beam Search | 生成多个候选计划，搜索选择最优 |
| **外部模块辅助** | LLM+P、PDDL 规划器 | 借助经典规划器增强 LLM 规划能力 |
| **反思与精炼** | Reflexion、Self-Refine | 从失败中反思，迭代改进计划 |
| **记忆增强** | RAG、经验回放 | 用历史经验和知识辅助规划 |

### 4.2 Agent-Oriented Planning (AOP) 三原则

**来源**：ICLR 2025，[Agent-Oriented Planning](https://openreview.net/forum?id=EqcLAU6gyU)

元代理将用户请求分解为子任务时必须满足：

1. **可解性（Solvability）**：每个子任务必须在某个 Agent 的能力范围内
2. **完备性（Completeness）**：所有子任务合起来必须完整覆盖原始请求
3. **非冗余性（Non-redundancy）**：子任务之间不应有重复的职责范围

### 4.3 2025 前沿方法

| 方法 | 作者/时间 | 核心创新 |
|------|----------|---------|
| **HiPlan** | Li et al., 2025.08 | 分层规划：全局里程碑 + 局部逐步提示，配合检索增强的里程碑库 |
| **SagaLLM** | Chang et al., 2025.03 | 事务型 Saga 协议：计划分解、验证、补偿、回滚，类 ACID 保证 |
| **CausalPlan** | Nguyen et al., 2025.08 | 因果规划：从轨迹中学习因果图，用因果分数优先排序行动 |
| **Coarse-to-Fine Grounded Memory** | Yang et al., 2025.08 | 粗到细的记忆检索指导规划 |
| **LWM-Planner** | Holt et al., 2025.06 | 世界模型辅助规划器 |
| **PMC** | 2025 | 零样本多约束任务规划分解 |

### 4.4 ReAct vs Plan-and-Solve

| 维度 | ReAct | Plan-and-Solve |
|------|-------|---------------|
| **策略** | 边想边做，交替推理与行动 | 先规划后执行 |
| **适用场景** | 简单、直接的任务（如从桌上拿笔） | 复杂、多步骤的任务（如做一杯咖啡） |
| **优势** | 实时适应环境变化 | 全局视野，减少盲目试错 |
| **劣势** | 缺乏全局视野 | 前期规划可能因新信息作废 |

### 4.5 ReWOO：效率优化

| 维度 | ReAct | ReWOO |
|------|-------|-------|
| **LLM 调用** | 每个循环多次 | 单次规划调用 |
| **Token 消耗** | 高（重复上下文） | 低（无观察循环） |
| **适应性** | 实时调整 | 预规划序列 |
| **最佳场景** | 动态不可预测任务 | 结构化良好问题 |

---

## 五、Agent 规划的失败模式

**来源**：多篇 2025 论文综合

### 5.1 六大失败模式

| 失败模式 | 描述 | 严重程度 |
|---------|------|---------|
| **幻觉级联** | 一处幻觉传播到后续所有步骤，引发连锁失败 | 极高 |
| **工具幻觉** | 编造不存在的工具、传错参数、捏造工具输出 | 高 |
| **规划脆性** | 计划缺乏弹性，遇到意外就崩溃 | 高 |
| **执行不稳定** | 中途丢失 JSON 格式、忘记前面的决策 | 中 |
| **目标偏移** | 长任务中逐渐偏离原始目标 | 中 |
| **错误累积** | 多步骤中小错误不断叠加，最终导致整体失败 | 高 |

### 5.2 关键理论发现

- **增强推理反而放大幻觉**：用强化学习增强推理能力的模型，在工具使用中反而更容易产生幻觉（[The Reasoning Trap, 2025](https://arxiv.org/html/2510.22977v1)）
- **更大模型更自信地犯错**：大模型不仅表现更好，也以更系统的方式幻觉、误推理、遗忘（[On the Fundamental Limits, 2025](https://arxiv.org/html/2511.12869v1)）
- **无法消除幻觉**：理论证明没有可枚举的模型类能做到完全无幻觉（可计算性与对角化限制）

### 5.3 缓解策略

1. **后执行监控**：每步执行后立即评估中间结果的有效性、一致性、事实性
2. **多层防护**：结构化 prompt + RAG 验证 + 领域对齐微调，多管齐下
3. **AgentDebug 三阶段**：细粒度分析 → 检测关键错误 → 带反馈的迭代重跑
4. **管理不确定性**：2025 年的共识是"管理不确定性，而非追求零幻觉"

---

## 六、综合分析与对 Arcstone 的建议

### 6.1 各方法论对比

| 维度 | Lilian Weng | Anthropic | Manus | 学术前沿 |
|------|------------|-----------|-------|---------|
| **核心观点** | 规划 = 分解 + 反思 + 工具 | 从简单开始，按需增加复杂度 | 上下文工程是核心战场 | 分层规划 + 记忆增强 |
| **方法论** | 理论分类为主 | 工程实践为主 | 产品实战为主 | 算法创新为主 |
| **规划策略** | CoT / ToT / ReAct | 6 种 workflow 模式 | Todo-list + CodeAct | HiPlan / SagaLLM |
| **错误处理** | 提到但未深入 | 沙箱测试 + 人工检查点 | 3 次重试 → 换方法 | AgentDebug 框架 |
| **核心 insight** | LLM 是规划引擎 | 工具设计 = prompt 工程 | KV-cache 命中率决定成败 | 可解性+完备性+非冗余 |

### 6.2 共识发现

所有来源一致认同的关键点：

1. **任务分解是规划的基础**：无论方法多高级，最终都要把大任务拆成小步骤
2. **反馈循环不可或缺**：一次性规划（one-shot planning）在实际中几乎必然失败
3. **记忆/上下文管理是规模化的瓶颈**：随着任务变长，如何管理上下文成为核心挑战
4. **错误恢复比错误预防更重要**：不可能完全避免错误，关键是能发现并修复
5. **工具设计和规划设计同等重要**：再好的规划，工具不好用也白搭

### 6.3 对 Arcstone 规划层的具体建议

基于以上研究，结合 Arcstone 当前架构（`06-架构设计-规划层.md`），建议：

#### 建议 1：采用 Manus 的 Todo-List 注意力操纵模式
当前架构已经使用了 `write_todos` / `read_todos`，这与 Manus 的 `todo.md` 模式高度一致。建议进一步强化：
- **每次工具调用后**都更新 todo 状态，而非只在完成时更新
- 确保 todo 内容出现在上下文末尾，利用模型的 recency bias
- 在 todo 中包含简短的已完成任务摘要，而非仅标记状态

#### 建议 2：实现 Anthropic 的 Orchestrator-Workers 模式
当前的子代理系统（researcher、calculator、comparator）已经是这个模式的雏形。建议：
- 主代理负责规划和分配，不直接执行具体分析
- Worker 代理执行后，主代理验证结果的合理性（引入 Evaluator 角色）
- 对于矿业评估这种有明确步骤的任务，Prompt Chaining 可能比完全自主 Agent 更可靠

#### 建议 3：遵循 AOP 三原则进行任务分解
设计任务分解 prompt 时，显式检查：
- 每个子任务是否能被某个工具/子代理完成？（可解性）
- 所有子任务合起来是否覆盖了用户的完整需求？（完备性）
- 是否有子任务之间存在重复工作？（非冗余性）

#### 建议 4：KV-Cache 友好设计
Arcstone 使用 DeepSeek API，同样受益于缓存优化：
- 系统 prompt 保持稳定，不包含动态内容（时间戳等放在用户消息中）
- 上下文采用 append-only 设计
- 工具输出序列化方式保持确定性

#### 建议 5：分层错误处理
参考 Manus 的"3 次失败换方法"策略：
- 第 1 次失败：检查参数，重试
- 第 2 次失败：换工具/换方法重试
- 第 3 次失败：降级处理（给出部分结果 + 说明限制）
- 所有失败记录保留在上下文中，帮助模型避免重复错误

#### 建议 6：考虑 Plan-and-Solve + ReAct 混合策略
- 对于"全面评估矿业项目"这类可预测的复杂任务：用 Plan-and-Solve（先规划后执行）
- 对于"帮我看看这个报告有什么问题"这类探索性任务：用 ReAct（边想边做）
- 在 system prompt 中指导模型根据任务类型选择策略

---

## 七、参考文献

### 博客与指南
- Lilian Weng, [LLM Powered Autonomous Agents](https://lilianweng.github.io/posts/2023-06-23-agent/), 2023
- Anthropic, [Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents), 2024.12
- Manus, [Context Engineering for AI Agents](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus), 2025

### 技术分析
- [In-depth technical investigation into Manus AI](https://gist.github.com/renschni/4fbc70b31bad8dd57f3370239dccd58f)
- [Agentic AI Planning Pattern - Analytics Vidhya](https://www.analyticsvidhya.com/blog/2024/11/agentic-ai-planning-pattern/)
- [6 Design Patterns for AI Agent Applications](https://valanor.co/design-patterns-for-ai-agents/)

### 学术论文
- Huang et al., [Understanding the Planning of LLM Agents: A Survey](https://arxiv.org/abs/2402.02716), 2024
- [Agent-Oriented Planning in Multi-Agent Systems](https://openreview.net/forum?id=EqcLAU6gyU), ICLR 2025
- [LLM-based Agents Suffer from Hallucinations: A Survey](https://arxiv.org/html/2509.18970v1), 2025
- [Where LLM Agents Fail and How They Can Learn from Failures](https://arxiv.org/pdf/2509.25370), 2025
- [The Reasoning Trap: How Enhancing Reasoning Amplifies Tool Hallucination](https://arxiv.org/html/2510.22977v1), 2025
- [How Do LLMs Fail in Agentic Scenarios?](https://arxiv.org/html/2512.07497v2), 2025
- [On the Fundamental Limits of LLMs at Scale](https://arxiv.org/html/2511.12869v1), 2025
- [LLM-Based Agent Planning - Emergent Mind](https://www.emergentmind.com/topics/llm-based-agent-planning)
