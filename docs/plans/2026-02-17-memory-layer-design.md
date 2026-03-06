# Memory Layer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add persistent cross-session memory to the mining investment agent using SQLite.

**Architecture:** Custom `SqliteStore` (extends `langgraph.store.base.BaseStore`) backed by sqlite3. `CompositeBackend` routes `/memories/` paths to `StoreBackend(store=SqliteStore)`, everything else to ephemeral `StateBackend`. Checkpointer enables conversation resume within a thread.

**Tech Stack:** sqlite3 (stdlib), langgraph BaseStore/Item/SearchItem, deepagents CompositeBackend/StateBackend/StoreBackend

---

### Task 1: Create SqliteStore

**Files:**
- Create: `src/store.py`
- Test: manual via Python REPL

**Step 1: Write `src/store.py`**

Implements `BaseStore` with these methods:
- `batch(ops)` — core method, dispatches GetOp/PutOp/SearchOp/ListNamespacesOp
- `get(namespace, key)` — single item read
- `put(namespace, key, value)` — upsert
- `delete(namespace, key)` — remove
- `search(namespace_prefix)` — prefix match, returns SearchItem list
- `list_namespaces(prefix, suffix, max_depth)` — distinct namespaces
- `setup()` — CREATE TABLE IF NOT EXISTS

Key details from source inspection:
- namespace is `tuple[str, ...]`, store as JSON string in DB (e.g. `'["filesystem"]'`)
- value is `dict[str, Any]`, store as JSON string
- Item requires: `value`, `key`, `namespace`, `created_at` (datetime), `updated_at` (datetime)
- SearchItem additionally has `score` (float|None)
- `batch` is the abstract method that must be implemented; `get`/`put`/`delete`/`search`/`list_namespaces` have default implementations that call `batch`

**Step 2: Verify SqliteStore works**

```bash
"D:/miniconda/envs/miner-agent/python.exe" -c "
import sys; sys.path.insert(0, 'D:/miner-agent')
from src.store import SqliteStore
store = SqliteStore('D:/miner-agent/data/test_memories.db')
store.setup()
store.put(('filesystem',), '/memories/test.md', {'content': ['hello', 'world'], 'created_at': '2026-01-01T00:00:00', 'modified_at': '2026-01-01T00:00:00'})
item = store.get(('filesystem',), '/memories/test.md')
print(item.value)
items = store.search(('filesystem',))
print(len(items), 'items found')
store.delete(('filesystem',), '/memories/test.md')
print('deleted, remaining:', len(store.search(('filesystem',))))
import os; os.remove('D:/miner-agent/data/test_memories.db')
print('ALL PASS')
"
```

---

### Task 2: Modify `src/agent/main.py` — wire up memory

**Files:**
- Modify: `src/agent/main.py`

**Changes:**
- Import SqliteStore, CompositeBackend, StateBackend, StoreBackend, MemorySaver
- `create_mining_agent` takes `db_path` parameter (default `./data/memories.db`)
- Create store, checkpointer, and CompositeBackend lambda
- Pass `store`, `backend`, `checkpointer` to `create_deep_agent`
- Return both agent and store (for run.py to pass config)

---

### Task 3: Modify `src/agent/prompts.py` — add memory instructions

**Files:**
- Modify: `src/agent/prompts.py`

**Changes:**
Add a memory management section to MINING_SYSTEM_PROMPT after the tool usage section:

```
# 记忆管理

你有一个持久化文件系统 /memories/，内容跨会话保留。

## 读取记忆
每次对话开始，先检查：
1. 读取 /memories/user_profile.md — 用户投资偏好
2. 如果讨论涉及已知项目，读取 /memories/projects/{项目名}.md
3. 读取 /memories/instructions.md — 自我改进指令

## 写入记忆
主动记录重要信息：
- 用户表达投资偏好时 → 更新 /memories/user_profile.md
- 讨论某个项目后 → 更新 /memories/projects/{项目名}.md
- 用户做出投资决策时 → 创建 /memories/decisions/{日期}_{项目}_{决策}.md
- 用户纠正错误或表达偏好时 → 更新 /memories/instructions.md

## 注意
- 不要告诉用户你在读写记忆文件，自然地融入对话
- 记忆文件用 markdown 格式
- 发现记忆文件不存在时，首次创建即可
```

---

### Task 4: Modify `run.py` — stable thread_id + show memory status

**Files:**
- Modify: `run.py`

**Changes:**
- Import `create_mining_agent` which now returns agent + store
- Use a stable thread_id (stored in `data/thread_id.txt`) instead of random uuid per session
- Show memory DB path on startup
- Support `/new` command to start a new thread (new uuid, save to file)
- Support `/memory` command to show current memory files count

---

### Task 5: End-to-end verification

**Steps:**
1. Start agent, ask "我一般只看IRR 15%以上的项目" → agent should save to user_profile.md
2. Exit and restart agent → ask "我之前的投资偏好是什么" → agent should read from memory
3. Verify `data/memories.db` file exists and contains data
