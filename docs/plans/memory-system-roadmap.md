# 记忆系统优化路线图

## 现状

当前记忆系统已具备完整的基础设施：

```
写入：Agent write_file → SqliteStore → items 表（持久化）
                                     → embeddings 表（1024维向量，DashScope）
                                     → fts_memory 表（jieba 分词 + FTS5 BM25）

检索：Agent memory_search → cosine 相似度 (70%) + BM25 关键词 (30%) → top-K 结果

管理：index.md 索引 + backfill 自动重建 + text_hash 去重
```

**能力边界**：存储和检索层可靠，但记忆的写入质量、生命周期管理、用户可控性完全依赖 Agent 自觉和 prompt 指导。这是从"能用"到"好用"的核心差距。

---

## P0：结构化记忆提取

**问题**：Agent 自由写 markdown，格式不统一，关键信息可能遗漏或表述不一致。

**方案**：在 Agent 写入记忆前，增加一层结构化提取。

### 设计思路

定义记忆 schema，不同类型的记忆有不同的结构：

```python
# 用户画像 schema
UserProfile = {
    "investment_preferences": {
        "irr_threshold": float,         # IRR 门槛
        "preferred_minerals": list,      # 偏好矿种
        "preferred_regions": list,       # 偏好地区
        "risk_tolerance": str,           # conservative/moderate/aggressive
    },
    "communication_style": {
        "prefers_tables": bool,
        "prefers_explicit_advice": bool,
        "language_notes": list,          # 术语纠正等
    },
    "updated_at": str,
}

# 项目记忆 schema
ProjectMemory = {
    "name": str,
    "location": str,
    "mineral_type": str,
    "resource_estimate": str,
    "grade": str,
    "irr": float,
    "npv": float,
    "conclusion": str,                   # invest/hold/abandon
    "key_risks": list,
    "discussion_history": list[dict],    # [{date, summary, decision}]
    "updated_at": str,
}
```

### 实现方式

两种路径可选：

**A. Prompt 约束（轻量）**：在 prompt 中规定记忆文件必须包含的字段，Agent 写入时自查。
- 优点：零代码改动
- 缺点：模型不一定遵守

**B. 后处理校验（可靠）**：Agent 写入后，用一个轻量 LLM 调用（或正则）校验格式，缺字段则补全。
- 优点：强制保证格式
- 缺点：多一次 API 调用

**建议**：先 A 后 B，A 效果不够再加 B。

---

## P1：记忆冲突检测与更新

**问题**：用户偏好会变，旧记忆和新信息矛盾时，Agent 不知道该信谁。

### 场景

```
旧记忆：user_profile.md 写着"只看 IRR > 15%"
新对话：用户说"这个项目 IRR 12% 也可以考虑，最近市场不好"
```

当前行为：Agent 可能直接覆盖写入，也可能忽略，取决于模型判断。

### 设计思路

**写入时冲突检测**：

```
Agent 准备写入记忆
  → 读取该文件当前内容
  → 对比新旧内容，检测是否有矛盾字段
  → 如果有矛盾：
      → 向用户确认："您之前说 IRR 门槛是 15%，现在要调整为 12% 吗？"
      → 用户确认后再写入
      → 写入时标注变更历史
```

**记忆文件增加变更日志**：

```markdown
## 变更记录
| 日期 | 字段 | 旧值 | 新值 | 原因 |
|------|------|------|------|------|
| 2026-02-18 | IRR 门槛 | 15% | 12% | 用户表示市场不好可放宽 |
```

这样即使改错了，也有迹可循。

---

## P2：记忆衰减与重要度

**问题**：记忆只增不减，时间久了老旧信息干扰检索。一年前否决的项目和昨天讨论的项目权重一样。

### 设计思路

**给记忆加时间衰减权重**：

```python
def memory_relevance(base_score, last_accessed, last_updated, access_count):
    """
    base_score: 检索相似度 (cosine + bm25)
    last_accessed: 上次被读取的时间
    last_updated: 上次更新的时间
    access_count: 被引用次数
    """
    days_since_access = (now - last_accessed).days
    recency_decay = 0.95 ** (days_since_access / 30)  # 每月衰减 5%
    frequency_boost = min(1.0 + 0.1 * access_count, 2.0)  # 频繁引用加权，上限 2x

    return base_score * recency_decay * frequency_boost
```

**需要新增的字段**：

在 embeddings 表或单独建表，记录：
- `last_accessed_at`：每次 read_file 时更新
- `access_count`：累计被读取次数
- `importance`：手动/自动标记的重要度（如用户决策 > 普通项目讨论）

**记忆归档**：超过 N 天未被访问且重要度低的记忆，自动移入 `/memories/archive/`，不参与默认检索，但仍可通过 memory_search 找到。

---

## P3：记忆管理 UI

**问题**：用户完全看不到 Agent 记了什么，无法修正错误记忆。

### 功能清单

**基础功能（必做）**：
1. **记忆列表**：按分类（画像/项目/决策/指令）展示所有记忆文件
2. **记忆查看**：点击查看完整内容
3. **记忆编辑**：用户可直接修改记忆内容
4. **记忆删除**：删除不需要的记忆

**进阶功能**：
5. **记忆搜索**：前端调用 memory_search API，用户自己搜索
6. **变更历史**：查看每条记忆的修改记录
7. **导出/导入**：备份和恢复记忆数据

### API 设计

```
GET    /api/memories                    # 列出所有记忆文件
GET    /api/memories/{path}             # 读取指定记忆
PUT    /api/memories/{path}             # 更新记忆内容
DELETE /api/memories/{path}             # 删除记忆
POST   /api/memories/search             # 语义搜索记忆
GET    /api/memories/{path}/history      # 查看变更历史
```

### 前端交互

```
┌─────────────────────────────────────────────────┐
│  记忆管理                              [搜索...]  │
├─────────────────────────────────────────────────┤
│                                                 │
│  📋 用户画像          2026-02-18 更新            │
│     IRR门槛: 15% | 关注: 铜矿,锂矿 | 风格: 保守  │
│                                     [查看] [编辑]│
│  ─────────────────────────────────────────────  │
│  📁 项目 (3)                                     │
│     贵州铜矿A      2026-02-15  品位0.8% 已否决    │
│     云南锂矿B      2026-02-10  初步评估中         │
│     甘肃金矿C      2026-01-20  IRR 18% 建议投资   │
│                                                 │
│  📁 决策 (2)                                     │
│     2026-02-15 铜矿A 放弃 — 品位过低              │
│     2026-01-20 金矿C 推进 — IRR达标               │
│                                                 │
│  📁 指令 (1)                                     │
│     自我改进指令     2026-02-18 更新              │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## P4：主动记忆触发

**问题**：完全靠 prompt 指导 Agent "记住"信息，不稳定。

### 设计思路

**对话结束时的记忆审查**：

在每轮对话结束（或用户切换话题/关闭窗口）时，自动触发一次记忆审查：

```
对话结束
  → 提取本轮对话的关键信息（轻量 LLM 调用）
  → 与现有记忆对比：
      → 新信息？→ 写入
      → 更新？→ 更新 + 标注变更
      → 冲突？→ 标记待确认（下次对话开头问用户）
      → 无变化？→ 跳过
```

这比现在"Agent 想起来就写、忘了就算"可靠得多。

**实现方式**：

可以在 API 层的 chat 结束后，额外调用一次 LLM 做信息提取：

```python
async def post_conversation_memory_review(messages, store):
    """对话结束后自动审查是否需要更新记忆"""
    extraction_prompt = """
    分析以下对话，提取需要记忆的信息：
    1. 用户偏好变化
    2. 项目新结论
    3. 投资决策
    4. 需要纠正的错误
    返回 JSON 格式。如果没有需要记忆的，返回空。
    """
    # ... 调用轻量模型提取 → 写入 store
```

---

## P5：记忆可视化与洞察

**更远期的方向，非近期目标。**

- **记忆图谱**：项目之间的关联关系可视化（同一矿种、同一地区、对比过的项目）
- **决策复盘**：展示历史决策的后续验证（当时否决的项目，后来矿价涨了，是否应该重新评估）
- **投资画像演变**：用户偏好随时间的变化趋势

---

## 优先级总结

| 阶段 | 内容 | 依赖 | 价值 |
|------|------|------|------|
| **P0** | 结构化记忆提取 | 无 | 提升记忆质量，是后续所有优化的基础 |
| **P1** | 冲突检测与更新 | P0 | 防止记忆错乱，用户信任度 |
| **P2** | 记忆衰减与重要度 | 无 | 记忆多了之后的检索质量 |
| **P3** | 记忆管理 UI | 无 | 用户可控性，产品化必须 |
| **P4** | 主动记忆触发 | P0 | 彻底解决"Agent 忘记记"的问题 |
| **P5** | 可视化与洞察 | P3 | 锦上添花，远期 |

**建议执行顺序**：P0 → P3 → P1 → P4 → P2 → P5

理由：P0（结构化）是地基；P3（UI）让用户能看到和修正记忆，形成闭环；P1 和 P4 提升自动化程度；P2 和 P5 是记忆量大了之后才需要的优化。
