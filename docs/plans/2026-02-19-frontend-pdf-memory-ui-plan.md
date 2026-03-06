# 前端 PDF 上传 + 记忆管理 UI 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 Arcstone 前端实现 PDF 上传功能（输入框旁回形针按钮）和记忆管理面板重构（双栏 Markdown 渲染 + 编辑 + 删除）。

**Architecture:** ChatInput 新增文件上传按钮，通过 FormData 调用已有的 `POST /api/upload/pdf` 端点。MemoryPanel 从 380px 单栏只读抽屉重构为 720px 双栏（列表 + Markdown 渲染/编辑），后端新增 PUT/DELETE memory API。

**Tech Stack:** React 18, TypeScript, Tailwind CSS, react-markdown + remark-gfm, lucide-react, FastAPI

---

### Task 1: 后端 — 新增 memory PUT/DELETE API

**Files:**
- Modify: `src/api/routes.py:351-384`（memory 区域末尾）

**Step 1: 在 routes.py memory 区域末尾添加两个端点**

在 `memory_detail` 函数之后、`# --- Upload ---` 之前插入：

```python
class MemoryUpdateRequest(BaseModel):
    content: str


@router.put("/memory/{key:path}")
def memory_update(key: str, req: MemoryUpdateRequest, request: Request):
    """更新记忆文件内容。"""
    store, _ = _get_shared(request)
    now = datetime.now(timezone.utc).isoformat()
    store.put(("filesystem",), key, {
        "content": req.content.split("\n"),
        "created_at": now,
        "modified_at": now,
    })
    return {"ok": True}


@router.delete("/memory/{key:path}")
def memory_delete(key: str, request: Request):
    """删除记忆文件。"""
    store, _ = _get_shared(request)
    store.delete(("filesystem",), key)
    return {"ok": True}
```

**Step 2: 验证后端启动无语法错误**

Run: `"D:/miniconda/envs/miner-agent/python.exe" -c "import ast; ast.parse(open('D:/miner-agent/src/api/routes.py', encoding='utf-8').read()); print('OK')"`
Expected: `OK`

**Step 3: 启动后端验证端点可达**

Run: `curl -s http://localhost:8000/api/health`
Expected: `{"status":"ok"}`

---

### Task 2: 前端 API 层 — 新增 uploadPdf, updateMemory, deleteMemory

**Files:**
- Modify: `frontend/src/lib/api.ts`

**Step 1: 在 api.ts 末尾添加三个函数**

```typescript
export function uploadPdf(file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<{ ok: boolean; path?: string; pages?: number; chars?: number; method?: string; error?: string }>(
    `${BASE_URL}/upload/pdf`,
    { method: "POST", body: form }
  );
}

export function updateMemory(key: string, content: string) {
  return request<{ ok: boolean }>(`${BASE_URL}/memory/${key}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
}

export function deleteMemory(key: string) {
  return request<{ ok: boolean }>(`${BASE_URL}/memory/${key}`, {
    method: "DELETE",
  });
}
```

---

### Task 3: 前端 — ChatInput PDF 上传按钮

**Files:**
- Modify: `frontend/src/components/ChatInput.tsx`

**Step 1: 添加 PDF 上传功能**

改动要点：
- props 新增 `onUploadPdf: (file: File) => void` 和 `uploadStatus: "idle" | "uploading" | "success" | "error"`
- 在 ModelSelector 右侧添加回形针按钮 + 隐藏 `<input type="file">`
- 按钮根据 `uploadStatus` 显示不同图标和颜色

完整的底部栏改动（`{/* Bottom bar */}` 区域内 `{/* Model selector (left) */}` 的 div）：

```tsx
<div className="flex items-center gap-1.5">
  {modelSelector}
  {/* PDF upload */}
  <input
    ref={fileInputRef}
    type="file"
    accept=".pdf"
    className="hidden"
    onChange={(e) => {
      const f = e.target.files?.[0];
      if (f) onUploadPdf(f);
      e.target.value = "";
    }}
  />
  <button
    onClick={() => fileInputRef.current?.click()}
    disabled={uploadStatus !== "idle"}
    className={`flex items-center justify-center w-7 h-7 rounded-lg transition-colors
      ${uploadStatus === "success" ? "text-emerald-500" :
        uploadStatus === "error" ? "text-red-500" :
        "text-sand-400 hover:text-sand-600 hover:bg-sand-200/50"}`}
    title="上传 PDF"
  >
    {uploadStatus === "uploading" ? <Loader2 size={15} className="animate-spin" /> :
     uploadStatus === "success" ? <CheckCircle2 size={15} /> :
     uploadStatus === "error" ? <AlertCircle size={15} /> :
     <Paperclip size={15} />}
  </button>
</div>
```

新增 imports: `Paperclip, Loader2, CheckCircle2, AlertCircle`，新增 `useRef` 的 `fileInputRef`。

---

### Task 4: 前端 — App.tsx 上传逻辑 + 系统消息

**Files:**
- Modify: `frontend/src/App.tsx`

**Step 1: 添加上传状态管理和处理函数**

```tsx
const [uploadStatus, setUploadStatus] = useState<"idle" | "uploading" | "success" | "error">("idle");
```

```tsx
const handleUploadPdf = useCallback(async (file: File) => {
  setUploadStatus("uploading");
  try {
    const result = await uploadPdf(file);
    if (result.ok) {
      setUploadStatus("success");
      // 插入系统提示消息到聊天区
      const sysMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: `已上传并解析 **${file.name}**（${result.pages} 页），可以让 Arcstone 分析这份文档。`,
        segments: [{ type: "text", content: `已上传并解析 **${file.name}**（${result.pages} 页），可以让 Arcstone 分析这份文档。` }],
      };
      // 需要 useChat 暴露 addMessage 方法
    } else {
      setUploadStatus("error");
    }
  } catch {
    setUploadStatus("error");
  }
  setTimeout(() => setUploadStatus("idle"), uploadStatus === "error" ? 2000 : 1500);
}, []);
```

**Step 2: useChat.ts 新增 addMessage**

在 `useChat` hook 末尾，`return` 对象中新增：

```typescript
const addMessage = useCallback((msg: Message) => {
  setMessages(prev => [...prev, msg]);
}, []);
```

并将 `addMessage` 加入返回值。

**Step 3: 传递 props 给 ChatInput**

```tsx
<ChatInput
  onSend={handleSend}
  onStop={stopStreaming}
  isStreaming={isStreaming}
  onUploadPdf={handleUploadPdf}
  uploadStatus={uploadStatus}
  modelSelector={...}
/>
```

---

### Task 5: 前端 — MemoryPanel 完全重写

**Files:**
- Rewrite: `frontend/src/components/MemoryPanel.tsx`

**Step 1: 完全重写 MemoryPanel**

这是最大的改动。关键设计：

- 宽度 720px，左栏 260px 列表 + 右栏 460px 内容
- 左侧：按 5 个分组折叠展示，每组可点击展开/收起
- 右侧：默认 markdown 渲染视图，点「编辑」切换到 textarea
- 底部操作栏：删除（内联确认）+ 编辑/保存/取消
- 分组规则：
  - 用户画像：`/user_profile.md`, `/instructions.md`
  - 项目：`/projects/` 前缀
  - 决策：`/decisions/` 前缀
  - 文档：`/documents/` 前缀
  - 其他：兜底

分组逻辑函数：

```typescript
function categorize(key: string): string {
  if (key === "/user_profile.md" || key === "/instructions.md") return "profile";
  if (key.startsWith("/projects/")) return "projects";
  if (key.startsWith("/decisions/")) return "decisions";
  if (key.startsWith("/documents/")) return "documents";
  return "other";
}

const GROUP_CONFIG: Record<string, { label: string; icon: typeof User }> = {
  profile:   { label: "用户画像", icon: User },
  projects:  { label: "项目", icon: FolderOpen },
  decisions: { label: "决策", icon: Scale },
  documents: { label: "文档", icon: FileText },
  other:     { label: "其他", icon: File },
};
```

右侧查看/编辑切换：

```
state: mode = "view" | "edit"
view 模式：<ReactMarkdown className="prose" remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          底部：[删除]  [编辑]
edit 模式：<textarea>{editContent}</textarea>
          底部：[删除]  [取消] [保存] (保存仅在 editContent !== content 时激活)
```

删除内联确认：

```
state: confirmDelete = false
点击删除 → confirmDelete = true → 显示「确认删除？」+「取消」
3 秒 setTimeout 自动恢复 confirmDelete = false
点击确认 → 调 deleteMemory API → 刷新列表 → 清空右侧
```

---

### Task 6: Playwright 测试 — PDF 上传 UI

**Files:**
- Create: `tests/test_pdf_upload_ui.py`

**Step 1: 写 Playwright 脚本截图验证**

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto("http://localhost:5173")
    page.wait_for_load_state("networkidle")

    # 截图：初始状态（应能看到回形针按钮）
    page.screenshot(path="tests/screenshots/01_chat_input.png", full_page=True)

    browser.close()
```

Run: `"D:/miniconda/envs/miner-agent/python.exe" tests/test_pdf_upload_ui.py`

---

### Task 7: Playwright 测试 — 记忆面板 UI

**Files:**
- Create: `tests/test_memory_panel_ui.py`

**Step 1: 写 Playwright 脚本截图验证**

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto("http://localhost:5173")
    page.wait_for_load_state("networkidle")

    # 点击侧边栏的记忆按钮打开面板
    page.locator("text=记忆").click()
    page.wait_for_timeout(500)

    # 截图：记忆面板
    page.screenshot(path="tests/screenshots/02_memory_panel.png", full_page=True)

    # 点击第一个记忆文件
    items = page.locator("[data-testid='memory-item']").all()
    if items:
        items[0].click()
        page.wait_for_timeout(500)
        page.screenshot(path="tests/screenshots/03_memory_detail.png", full_page=True)

    browser.close()
```

---

## 执行顺序

1. Task 1：后端 API（PUT/DELETE）
2. Task 2：前端 API 层
3. Task 3：ChatInput 上传按钮
4. Task 4：App.tsx 上传逻辑 + useChat addMessage
5. Task 5：MemoryPanel 重写（最大任务）
6. Task 6：Playwright 测试上传 UI
7. Task 7：Playwright 测试记忆面板

Task 1-2 无依赖可并行。Task 3-4 依赖 Task 2。Task 5 依赖 Task 2。Task 6-7 依赖前面全部完成。
