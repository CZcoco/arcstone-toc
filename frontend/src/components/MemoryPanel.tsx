import { useState, useEffect, useRef, useMemo } from "react";
import {
  X, FileText, Loader2, ChevronDown, ChevronRight,
  User, FolderOpen, Scale, File, Pencil, Trash2, Save, XCircle, Plus, Check,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { MemoryItem } from "@/types";
import { listMemory, getMemory, updateMemory, deleteMemory, renameMemory } from "@/lib/api";

// --- 分组逻辑 ---

type GroupKey = "profile" | "projects" | "decisions" | "documents" | "other";

function categorize(key: string): GroupKey {
  if (key === "/user_profile.md" || key === "/instructions.md" || key === "/index.md") return "profile";
  if (key.startsWith("/projects/")) return "projects";
  if (key.startsWith("/decisions/")) return "decisions";
  if (key.startsWith("/documents/")) return "documents";
  return "other";
}

const GROUP_ORDER: GroupKey[] = ["profile", "projects", "decisions", "documents", "other"];

const GROUP_CONFIG: Record<GroupKey, { label: string; Icon: typeof User }> = {
  profile:   { label: "用户画像", Icon: User },
  projects:  { label: "项目", Icon: FolderOpen },
  decisions: { label: "决策", Icon: Scale },
  documents: { label: "文档", Icon: FileText },
  other:     { label: "其他", Icon: File },
};

const GROUP_PREFIX: Record<GroupKey, string> = {
  profile: "/",
  projects: "/projects/",
  decisions: "/decisions/",
  documents: "/documents/",
  other: "/",
};

function displayName(key: string): string {
  const parts = key.split("/");
  return parts[parts.length - 1].replace(/\.md$/, "");
}

// --- 组件 ---

interface MemoryPanelProps {
  open: boolean;
  onClose: () => void;
}

export default function MemoryPanel({ open, onClose }: MemoryPanelProps) {
  const [items, setItems] = useState<MemoryItem[]>([]);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);

  // 编辑模式
  const [mode, setMode] = useState<"view" | "edit">("view");
  const [editContent, setEditContent] = useState("");
  const [saving, setSaving] = useState(false);

  // 删除确认
  const [confirmDelete, setConfirmDelete] = useState(false);
  const deleteTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 重命名
  const [renaming, setRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState("");
  const renameInputRef = useRef<HTMLInputElement>(null);

  // 新建文件（按分组）
  const [newFileGroup, setNewFileGroup] = useState<GroupKey | null>(null);
  const [newFilePath, setNewFilePath] = useState("");
  const [creating, setCreating] = useState(false);
  const newFileInputRef = useRef<HTMLInputElement>(null);

  // 折叠状态
  const [collapsed, setCollapsed] = useState<Record<GroupKey, boolean>>({
    profile: false, projects: false, decisions: false, documents: false, other: true,
  });

  // 分组数据
  const grouped = useMemo(() => {
    const map: Record<GroupKey, MemoryItem[]> = {
      profile: [], projects: [], decisions: [], documents: [], other: [],
    };
    for (const item of items) {
      if (item.key === "/index.md") continue; // 不展示 index.md
      map[categorize(item.key)].push(item);
    }
    return map;
  }, [items]);

  useEffect(() => {
    if (open) {
      loadItems();
      setSelectedKey(null);
      setContent("");
      setMode("view");
      setConfirmDelete(false);
    }
  }, [open]);

  async function loadItems() {
    try {
      const { items: list } = await listMemory();
      setItems(list);
    } catch {
      setItems([]);
    }
  }

  async function selectItem(key: string) {
    setSelectedKey(key);
    setMode("view");
    setConfirmDelete(false);
    setRenaming(false);
    setLoading(true);
    try {
      const { content: c } = await getMemory(key);
      setContent(c);
    } catch {
      setContent("加载失败");
    }
    setLoading(false);
  }

  function enterEdit() {
    setEditContent(content);
    setMode("edit");
    setConfirmDelete(false);
  }

  function cancelEdit() {
    setMode("view");
  }

  async function handleSave() {
    if (!selectedKey || editContent === content) return;
    setSaving(true);
    try {
      await updateMemory(selectedKey, editContent);
      setContent(editContent);
      setMode("view");
    } catch {
      // 保存失败静默处理
    }
    setSaving(false);
  }

  function startDelete() {
    setConfirmDelete(true);
    if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current);
    deleteTimerRef.current = setTimeout(() => setConfirmDelete(false), 3000);
  }

  function cancelDelete() {
    setConfirmDelete(false);
    if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current);
  }

  async function handleDelete() {
    if (!selectedKey) return;
    try {
      await deleteMemory(selectedKey);
      setItems(prev => prev.filter(i => i.key !== selectedKey));
      setSelectedKey(null);
      setContent("");
      setMode("view");
      setConfirmDelete(false);
    } catch {
      // 删除失败静默处理
    }
  }

  function startRename() {
    if (!selectedKey) return;
    setRenameValue(displayName(selectedKey));
    setRenaming(true);
    setTimeout(() => renameInputRef.current?.select(), 50);
  }

  function cancelRename() {
    setRenaming(false);
  }

  async function handleRename() {
    if (!selectedKey || !renameValue.trim()) {
      setRenaming(false);
      return;
    }
    const newName = renameValue.trim();
    if (newName === displayName(selectedKey)) {
      setRenaming(false);
      return;
    }
    try {
      const res = await renameMemory(selectedKey, newName);
      if (res.ok && res.new_key) {
        // 更新 items 列表和 selectedKey
        setItems(prev => prev.map(i =>
          i.key === selectedKey ? { ...i, key: res.new_key! } : i
        ));
        setSelectedKey(res.new_key);
      }
    } catch {
      // 重命名失败静默处理
    }
    setRenaming(false);
  }

  function toggleGroup(g: GroupKey) {
    setCollapsed(prev => ({ ...prev, [g]: !prev[g] }));
  }

  async function handleCreateFile() {
    if (!newFilePath.trim() || !newFileGroup) return;
    setCreating(true);
    let name = newFilePath.trim();
    if (!name.endsWith(".md")) name += ".md";
    const key = GROUP_PREFIX[newFileGroup] + name;
    try {
      await updateMemory(key, "");
      await loadItems();
      setNewFileGroup(null);
      setNewFilePath("");
      selectItem(key);
    } catch {
      // 静默处理
    }
    setCreating(false);
  }

  if (!open) return null;

  const hasChanges = mode === "edit" && editContent !== content;

  return (
    <div className="fixed inset-0 z-50 flex animate-fade-in">
      {/* Backdrop */}
      <div className="flex-1 bg-black/5 backdrop-blur-[2px]" onClick={onClose} />

      {/* Panel — 720px 双栏 */}
      <div className="w-[720px] max-w-[90vw] bg-sand-50 border-l border-sand-200/60 flex flex-col
                      shadow-[-8px_0_24px_rgba(0,0,0,0.06)] animate-slide-right">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3.5 border-b border-sand-200/60">
          <span className="text-[0.8125rem] font-semibold text-sand-700">
            记忆管理
          </span>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-sand-400 hover:text-sand-600 hover:bg-sand-200/50 transition-colors"
          >
            <X size={15} />
          </button>
        </div>

        {/* Body — 双栏 */}
        <div className="flex-1 flex min-h-0">
          {/* 左侧列表 260px */}
          <div className="w-[260px] border-r border-sand-200/40 overflow-y-auto">
            {items.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-48 text-sand-400">
                <FileText size={24} className="mb-2 opacity-40" />
                <span className="text-sm">暂无记忆文件</span>
              </div>
            ) : (
              <div className="py-1">
                {GROUP_ORDER.map(g => {
                  const group = grouped[g];
                  if (group.length === 0) return null;
                  const { label, Icon } = GROUP_CONFIG[g];
                  const isCollapsed = collapsed[g];
                  return (
                    <div key={g}>
                      {/* 分组头 */}
                      <button
                        onClick={() => toggleGroup(g)}
                        className="flex items-center gap-2 w-full px-3 py-2 text-left
                                   text-[0.75rem] font-medium text-sand-500 uppercase tracking-wider
                                   hover:bg-sand-200/30 transition-colors"
                      >
                        {isCollapsed
                          ? <ChevronRight size={12} className="text-sand-400" />
                          : <ChevronDown size={12} className="text-sand-400" />}
                        <Icon size={13} className="text-sand-400" />
                        {label}
                        <span className="text-sand-400 font-normal ml-auto text-2xs">
                          {group.length}
                        </span>
                      </button>

                      {/* 文件列表 */}
                      {!isCollapsed && group.map(item => (
                        <button
                          key={item.key}
                          data-testid="memory-item"
                          onClick={() => selectItem(item.key)}
                          className={`flex items-center gap-2 w-full pl-8 pr-3 py-1.5 text-left
                                     transition-colors text-[0.8125rem]
                                     ${selectedKey === item.key
                                       ? "bg-white text-sand-900 shadow-[0_1px_2px_rgba(0,0,0,0.04)]"
                                       : "text-sand-600 hover:bg-white/60 hover:text-sand-800"}`}
                        >
                          <span className="truncate">{displayName(item.key)}</span>
                          {item.updated_at && (
                            <span className="text-2xs text-sand-400 shrink-0 ml-auto">
                              {item.updated_at.slice(5, 10)}
                            </span>
                          )}
                        </button>
                      ))}
                      {/* 分组内新建文件 */}
                      {!isCollapsed && (
                        newFileGroup === g ? (
                          <div className="flex items-center gap-1 pl-8 pr-3 py-1.5">
                            <input
                              ref={newFileInputRef}
                              className="flex-1 min-w-0 bg-white border border-sand-300/60 rounded px-1.5 py-0.5
                                         text-[0.8125rem] text-sand-800 focus:outline-none focus:ring-1 focus:ring-sand-400/60"
                              placeholder="文件名"
                              value={newFilePath}
                              onChange={e => setNewFilePath(e.target.value)}
                              onKeyDown={e => {
                                if (e.key === "Enter") handleCreateFile();
                                if (e.key === "Escape") { setNewFileGroup(null); setNewFilePath(""); }
                              }}
                            />
                            <button onClick={handleCreateFile} disabled={creating || !newFilePath.trim()}
                              className="p-0.5 rounded text-sand-600 hover:text-sand-800 disabled:opacity-40">
                              <Check size={13} />
                            </button>
                            <button onClick={() => { setNewFileGroup(null); setNewFilePath(""); }}
                              className="p-0.5 rounded text-sand-400 hover:text-sand-600">
                              <X size={13} />
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => { setNewFileGroup(g); setNewFilePath(""); setTimeout(() => newFileInputRef.current?.focus(), 50); }}
                            className="flex items-center gap-1.5 pl-8 pr-3 py-1.5 w-full text-left
                                       text-[0.8125rem] text-sand-400 hover:text-sand-600 transition-colors"
                          >
                            <Plus size={12} />
                            新建文件
                          </button>
                        )
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* 右侧内容 460px */}
          <div className="flex-1 flex flex-col min-w-0">
            {selectedKey === null ? (
              /* 空状态 */
              <div className="flex-1 flex flex-col items-center justify-center text-sand-400">
                <FileText size={32} className="mb-3 opacity-30" />
                <span className="text-sm">选择一个记忆文件查看</span>
              </div>
            ) : loading ? (
              <div className="flex-1 flex items-center justify-center text-sand-400">
                <Loader2 size={18} className="animate-spin mr-2" />
                加载中
              </div>
            ) : (
              <>
                {/* 文件路径标题 — 点击文件名可重命名 */}
                <div className="px-4 py-2.5 border-b border-sand-200/40 flex items-center gap-1.5
                               text-[0.8125rem] font-medium text-sand-600 shrink-0">
                  <FileText size={13} className="opacity-50 shrink-0" />
                  {renaming ? (
                    <input
                      ref={renameInputRef}
                      className="flex-1 min-w-0 bg-white border border-sand-300/60 rounded px-1.5 py-0.5
                                 text-[0.8125rem] text-sand-800 focus:outline-none focus:ring-1 focus:ring-sand-400/60"
                      value={renameValue}
                      onChange={e => setRenameValue(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === "Enter") handleRename();
                        if (e.key === "Escape") cancelRename();
                      }}
                      onBlur={handleRename}
                      autoFocus
                    />
                  ) : (
                    <span
                      className="truncate cursor-pointer hover:text-sand-800 transition-colors"
                      onClick={startRename}
                      title="点击重命名"
                    >
                      /memories{selectedKey}
                    </span>
                  )}
                </div>

                {/* 内容区 */}
                <div className="flex-1 overflow-y-auto p-4">
                  {mode === "view" ? (
                    <div className="prose max-w-none">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {content || "(空)"}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <textarea
                      className="w-full h-full min-h-[300px] bg-white border border-sand-200/60
                                 rounded-xl p-4 text-[0.8125rem] text-sand-800 font-mono
                                 leading-relaxed resize-none focus:outline-none
                                 focus:ring-1 focus:ring-sand-300/60"
                      value={editContent}
                      onChange={e => setEditContent(e.target.value)}
                      autoFocus
                    />
                  )}
                </div>

                {/* 底部操作栏 */}
                <div className="px-4 py-2.5 border-t border-sand-200/40 flex items-center justify-between shrink-0">
                  {/* 左侧：删除 */}
                  <div className="flex items-center gap-2">
                    {confirmDelete ? (
                      <>
                        <button
                          onClick={handleDelete}
                          className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs
                                     bg-red-50 text-red-600 hover:bg-red-100 transition-colors"
                        >
                          <Trash2 size={12} />
                          确认删除？
                        </button>
                        <button
                          onClick={cancelDelete}
                          className="text-xs text-sand-400 hover:text-sand-600 transition-colors"
                        >
                          取消
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={startDelete}
                        className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs
                                   text-sand-400 hover:text-red-500 hover:bg-red-50/50 transition-colors"
                      >
                        <Trash2 size={12} />
                        删除
                      </button>
                    )}
                  </div>

                  {/* 右侧：编辑/保存/取消 */}
                  <div className="flex items-center gap-2">
                    {mode === "view" ? (
                      <button
                        onClick={enterEdit}
                        className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs
                                   text-sand-600 bg-white border border-sand-200/60
                                   hover:bg-sand-100 transition-colors"
                      >
                        <Pencil size={12} />
                        编辑
                      </button>
                    ) : (
                      <>
                        <button
                          onClick={cancelEdit}
                          className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs
                                     text-sand-500 hover:text-sand-700 transition-colors"
                        >
                          <XCircle size={12} />
                          取消
                        </button>
                        <button
                          onClick={handleSave}
                          disabled={!hasChanges || saving}
                          className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs
                                     transition-colors
                                     ${hasChanges
                                       ? "bg-sand-800 text-white hover:bg-sand-900"
                                       : "bg-sand-200 text-sand-400 cursor-default"}`}
                        >
                          {saving
                            ? <Loader2 size={12} className="animate-spin" />
                            : <Save size={12} />}
                          保存
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
