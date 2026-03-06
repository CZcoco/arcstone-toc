# Memory Index Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an index.md file to the memory system so Agent reads a lightweight directory on first turn instead of loading all files.

**Architecture:** Agent reads `/memories/index.md` + two core files on first turn. Agent updates index after every memory write. Backend auto-updates index on PDF upload.

**Tech Stack:** Python (prompts.py string edit, routes.py index helper function). No new dependencies.

**Design doc:** `docs/plans/2026-02-18-memory-index-design.md`

---

### Task 1: Add index helper function to routes.py

**Files:**
- Modify: `src/api/routes.py` (add helper function after line 17, before router definition)

**Step 1: Write the `_update_memory_index` helper**

Add this function to `src/api/routes.py` after the imports and before `router = APIRouter()`:

```python
_INDEX_KEY = "/index.md"
_INDEX_TEMPLATE = """# 记忆索引

## 用户画像
| 文件 | 摘要 | 更新时间 |
|------|------|---------|

## 项目
| 文件 | 摘要 | 更新时间 |
|------|------|---------|

## 决策
| 文件 | 摘要 | 更新时间 |
|------|------|---------|

## 文档
| 文件 | 摘要 | 更新时间 |
|------|------|---------|
"""


def _update_memory_index(store, file_path: str, summary: str, date: str):
    """更新 /memories/index.md 中某条记录。

    file_path: 相对路径如 "/documents/报告.md"
    summary:   该文件的摘要
    date:      更新日期如 "2026-02-18"
    """
    # 确定所属分区
    if file_path.startswith("/projects/"):
        section = "## 项目"
    elif file_path.startswith("/decisions/"):
        section = "## 决策"
    elif file_path.startswith("/documents/"):
        section = "## 文档"
    else:
        section = "## 用户画像"

    new_row = f"| {file_path} | {summary} | {date} |"

    # 读取现有 index.md
    item = store.get(("filesystem",), _INDEX_KEY)
    if item and isinstance(item.value, dict) and isinstance(item.value.get("content"), list):
        lines = list(item.value["content"])  # copy
        content = "\n".join(lines)
    elif item and isinstance(item.value, dict):
        content = item.value.get("data", "") or item.value.get("content", "")
        if isinstance(content, list):
            content = "\n".join(content)
        lines = content.split("\n")
    else:
        content = _INDEX_TEMPLATE
        lines = content.split("\n")

    # 查找并替换/追加
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"| {file_path} "):
            lines[i] = new_row
            updated = True
            break

    if not updated:
        # 找到目标 section 的表格末尾（下一个 ## 或文件结尾之前的空行）
        section_idx = None
        for i, line in enumerate(lines):
            if line.strip() == section:
                section_idx = i
                break

        if section_idx is not None:
            # 跳过 section header + table header + separator (3 lines)
            insert_at = section_idx + 4
            # 找到该 section 的最后一条记录（下一个空行或下一个 ##）
            while insert_at < len(lines):
                if lines[insert_at].startswith("| "):
                    insert_at += 1
                else:
                    break
            lines.insert(insert_at, new_row)
        else:
            # section not found, append to end
            lines.append(new_row)

    # 写回 store
    now_iso = datetime.now(timezone.utc).isoformat()
    store.put(("filesystem",), _INDEX_KEY, {
        "content": lines,
        "created_at": now_iso,
        "modified_at": now_iso,
    })
```

**Step 2: Verify no syntax errors**

Run:
```bash
"D:/miniconda/envs/miner-agent/python.exe" -c "import ast; ast.parse(open('src/api/routes.py').read()); print('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add src/api/routes.py
git commit -m "feat: add _update_memory_index helper for index.md maintenance"
```

---

### Task 2: Wire upload_pdf to update index

**Files:**
- Modify: `src/api/routes.py` — `upload_pdf` function (add 3 lines before the return statement)

**Step 1: Add index update call**

In the `upload_pdf` function, after the `store.put(...)` call for the PDF content and before the `return` statement, add:

```python
    # 更新记忆索引
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _update_memory_index(store, store_key, f"{base_name}，{result['pages']}页，{result['method']}解析", today)
```

**Step 2: Verify no syntax errors**

Run:
```bash
"D:/miniconda/envs/miner-agent/python.exe" -c "import ast; ast.parse(open('src/api/routes.py').read()); print('OK')"
```
Expected: `OK`

**Step 3: Manual test — upload a PDF and check index**

Run the API server, then test with curl:
```bash
# Start server in background first: "D:/miniconda/envs/miner-agent/python.exe" run_api.py

# Upload test PDF
curl -X POST http://127.0.0.1:8000/api/upload/pdf -F "file=@D:/miner-agent/矿山投资智能体-产品需求文档v1.0.pdf"

# Check index was created
curl http://127.0.0.1:8000/api/memory//index.md
```

Expected: Response contains a markdown table with one row under "## 文档" section for the uploaded PDF.

**Step 4: Commit**

```bash
git add src/api/routes.py
git commit -m "feat: upload_pdf auto-updates memory index"
```

---

### Task 3: Update Agent system prompt

**Files:**
- Modify: `src/agent/prompts.py` — lines 81-102 (memory management section)

**Step 1: Replace the memory management section**

Replace lines 81-102 of `prompts.py` (from `# 记忆管理（重要！）` through `- 文件不存在时直接创建`) with:

```
# 记忆管理（重要！）

你拥有持久化文件系统，/memories/ 路径下的文件跨会话永久保留。你必须善用 write_file 和 read_file 来积累记忆。

## 读取记忆（每次对话第一回合必做）
收到用户第一条消息后，立即用 read_file 依次读取：
1. /memories/index.md — 记忆索引，列出所有已保存的文件及摘要
2. /memories/user_profile.md — 用户投资偏好
3. /memories/instructions.md — 工作改进指令

然后根据 index.md 中的信息和用户消息内容，判断是否需要读取具体文件。
例如用户提到"铜矿A"，就去读 /memories/projects/铜矿A.md。
不要一次读取所有文件，按需读取。

文件不存在是正常的，不需要在意。

## 写入记忆（检测到以下情况时，立即用 write_file 写入，不要等到对话结束）
- 用户说出投资偏好（如"我只看IRR 15%以上的"）→ 立即 write_file 到 /memories/user_profile.md
- 讨论某个项目有结论后 → 立即 write_file 到 /memories/projects/{项目名}.md
- 用户做出投资决策 → 立即 write_file 到 /memories/decisions/{日期}_{项目}_{决策}.md
- 用户纠正你的错误 → 立即 write_file 到 /memories/instructions.md

## 维护索引（每次写入记忆后必做）
每次用 write_file 写入或更新 /memories/ 下的文件后，必须同步更新 /memories/index.md：
- 新文件：在对应分类表格下新增一行
- 更新文件：修改该行的摘要和更新时间
- 摘要要求：
  - 项目和决策类：80-150字，必须包含关键数据和数字（品位、储量、IRR、投资额等）
  - 文档类：20-50字，文件名+页数即可
  - 用户画像和指令类：80-150字
- 分类规则：
  - /user_profile.md、/instructions.md → "## 用户画像" 分区
  - /projects/*.md → "## 项目" 分区
  - /decisions/*.md → "## 决策" 分区
  - /documents/*.md → "## 文档" 分区

## 注意
- 不要告诉用户你在读写记忆文件，静默执行
- 记忆文件用 markdown 格式
- 文件不存在时直接创建
```

**Step 2: Verify no syntax errors**

Run:
```bash
"D:/miniconda/envs/miner-agent/python.exe" -c "import ast; ast.parse(open('src/agent/prompts.py').read()); print('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add src/agent/prompts.py
git commit -m "feat: update prompt - index.md first-turn read + index maintenance rules"
```

---

### Task 4: End-to-end test with Agent

**Step 1: Start API server**

```bash
"D:/miniconda/envs/miner-agent/python.exe" run_api.py
```

**Step 2: Test first-turn behavior**

Send a message to a new thread. Verify in SSE output that Agent calls `read_file` for:
1. `/memories/index.md`
2. `/memories/user_profile.md`
3. `/memories/instructions.md`

```bash
curl -N -X POST http://127.0.0.1:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "你好", "thread_id": "test-index-001"}'
```

Expected: tool_call events for 3 read_file calls in the SSE stream.

**Step 3: Test memory write + index update**

Send a message that triggers a memory write:

```bash
curl -N -X POST http://127.0.0.1:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "记住，我只看IRR 15%以上的项目", "thread_id": "test-index-001"}'
```

Expected: Agent writes to `/memories/user_profile.md` AND updates `/memories/index.md`.

**Step 4: Verify index content**

```bash
curl http://127.0.0.1:8000/api/memory//index.md
```

Expected: JSON response with index.md content containing a row for `user_profile.md` under the "用户画像" section.

**Step 5: Test PDF upload index**

```bash
curl -X POST http://127.0.0.1:8000/api/upload/pdf -F "file=@D:/miner-agent/矿山投资智能体-产品需求文档v1.0.pdf"
curl http://127.0.0.1:8000/api/memory//index.md
```

Expected: Index now also has a row under "文档" for the uploaded PDF.

**Step 6: Commit if all passes**

```bash
git add -A
git commit -m "test: verify memory index end-to-end"
```

---

### Task 5: Update development docs

**Files:**
- Modify: `docs/development.md` — add memory index section

**Step 1: Add documentation**

Add a section to `docs/development.md` documenting:
- Memory index design: index.md format, auto-maintenance by Agent + backend
- Changed prompt behavior: first-turn reads index + profile + instructions
- Backend change: upload_pdf auto-updates index

**Step 2: Commit**

```bash
git add docs/development.md
git commit -m "docs: add memory index system documentation"
```
