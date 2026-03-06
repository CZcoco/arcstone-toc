# P2: 记忆语义检索方案（待实施）

Date: 2026-02-18
Status: Draft（仅方案，未开始实施）
Priority: P2
Depends on: P0 index.md（已完成）

## 背景

当前记忆检索靠 index.md 索引 + Agent 按文件名/摘要判断。当记忆文件增长到几十上百个时，纯目录式检索会漏掉相关内容。需要语义检索能力。

## 方案：Embedding API + SQLite 混合搜索

```
写入：记忆内容 → 分块(~400 token) → 调 Embedding API → 向量存 SQLite
检索：query → Embedding API → cosine 相似度 + BM25 关键词 → 返回 top-K
```

### 技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| Embedding API | DashScope text-embedding-v3 | 已有 API Key，中文效果好，免费额度大 |
| 向量存储 | SQLite（memories.db）+ numpy cosine | 记忆量小（几百块），不需要向量数据库 |
| 关键词搜索 | SQLite FTS5 (BM25) | Python sqlite3 原生支持 |
| 混合权重 | 向量 70% + BM25 30%（参考 OpenClaw） | 语义召回为主，关键词精确补充 |

### 不选百炼 RAG 的原因

- 记忆是私有小数据，不需要大规模检索引擎
- 写入需同步推送，两份数据容易不一致
- 百炼 RAG 留给外部知识库（行业资料、研报）

### 核心改动预估

1. `src/store.py` 或新建 `src/memory_search.py`：分块 + embedding + 向量存储 + 混合检索
2. `src/agent/main.py`：注册 `memory_search` 工具
3. `src/api/routes.py`：写入记忆时触发 embedding 索引更新
4. Agent prompt：告知有 `memory_search` 工具可用于模糊检索

### 参考

- OpenClaw 记忆系统：Markdown 文件 + 混合搜索（向量 + BM25），验证了这条路可行
- OpenClaw 文档：https://docs.openclaw.ai/concepts/memory
- DashScope Embedding API：https://help.aliyun.com/document_detail/2712195.html

### 触发条件

当以下任一情况出现时启动实施：
- 记忆文件超过 30 个，index.md 变得臃肿
- 用户反馈 Agent 频繁漏读相关记忆
- 前端需要记忆搜索功能
