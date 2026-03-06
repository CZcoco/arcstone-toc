# 前端 PDF 上传 + 记忆管理 UI 设计

> 日期：2026-02-19 | 状态：Approved

---

## 一、PDF 上传 UI

### 入口

ChatInput.tsx 底部左侧，ModelSelector 左边，回形针图标按钮（Paperclip）。

### 交互流程

```
点击回形针 → <input type="file" accept=".pdf"> →
用户选文件 → spinning Loader2 + 禁用按钮 →
POST /api/upload/pdf (FormData) →
  成功 → 绿色 CheckCircle2 1.5s → 恢复 idle
       → 聊天区插入系统消息："已上传并解析 {filename}，可以让 Arcstone 分析这份文档。"
  失败 → 红色 AlertCircle 2s → 恢复 idle
```

### 状态机

| 状态 | 图标 | 颜色 | 可点击 |
|------|------|------|--------|
| idle | Paperclip | sand-400 | 是 |
| uploading | Loader2 (spin) | sand-400 | 否 |
| success | CheckCircle2 | emerald-500 | 否 |
| error | AlertCircle | red-500 | 否 |

### 改动文件

- `frontend/src/components/ChatInput.tsx`：加回形针按钮 + 隐藏 file input + 上传逻辑
- `frontend/src/lib/api.ts`：新增 `uploadPdf(file: File)` 函数
- `frontend/src/App.tsx`：传 `onUploadSuccess` 回调给 ChatInput + 聊天区插入系统提示消息

---

## 二、记忆管理面板

### 布局

从 380px 扩到 720px，双栏：

```
┌─────────────────────────────────────────────────────────┐
│  记忆管理                                          [×]  │
├──────────────────┬──────────────────────────────────────┤
│  左侧 260px       │  右侧 460px                         │
│                   │                                      │
│  ▼ 用户画像 (2)   │  /memories/projects/铜矿A.md         │
│    user_profile   │                                      │
│    instructions   │  [Markdown 渲染视图]                  │
│  ▼ 项目 (3)      │  # 贵州铜矿A项目                     │
│    铜矿A ← 选中   │  ## 基本信息                         │
│    锂矿B          │  - 位置：贵州                        │
│    金矿C          │  ...                                 │
│  ▶ 决策 (0)      │                                      │
│  ▶ 文档 (1)      │  ┌─────────────────────────────┐     │
│                   │  │ [删除]           [编辑]      │     │
│                   │  └─────────────────────────────┘     │
└──────────────────┴──────────────────────────────────────┘
```

### 右侧两种模式

**查看模式（默认）：**
- react-markdown + remark-gfm 渲染 markdown 内容
- 底部操作栏：左侧「删除」灰色按钮，右侧「编辑」按钮

**编辑模式（点编辑后）：**
- textarea（monospace，全高），显示原始 markdown 文本
- 底部操作栏：左侧「删除」，右侧「取消」+「保存」
- 「保存」只在内容有变化时激活

### 删除确认

点「删除」→ 按钮就地变成红色「确认删除？」+ 灰色「取消」，3 秒内不点确认自动恢复。不弹模态框。

### 分组规则

| 分组 | key 匹配规则 |
|------|-------------|
| 用户画像 | `/user_profile.md`, `/instructions.md` |
| 项目 | `/projects/` 前缀 |
| 决策 | `/decisions/` 前缀 |
| 文档 | `/documents/` 前缀 |
| 其他 | 以上都不匹配 |

### 空状态

- 未选中文件：右侧显示 FileText 图标 + "选择一个记忆文件查看"
- 列表为空：显示 "暂无记忆文件"

### 后端新增 API

```
PUT    /api/memory/{key}   body: { content: string }  → { ok: true }
DELETE /api/memory/{key}                               → { ok: true }
```

### 改动文件

- `frontend/src/components/MemoryPanel.tsx`：完全重写
- `frontend/src/lib/api.ts`：新增 `updateMemory`, `deleteMemory`
- `frontend/src/types.ts`：如需新类型
- `src/api/routes.py`：新增 PUT/DELETE 两个端点

---

## 三、共享依赖

已有 react-markdown + remark-gfm，无需安装新包。
lucide-react 已有 Paperclip, CheckCircle2, AlertCircle 等图标。

## 四、测试计划

- Playwright 自动化测试前端 UI
- 启动后端 (port 8000) + 前端 dev server (port 5173)
- 截图验证 UI 渲染效果
