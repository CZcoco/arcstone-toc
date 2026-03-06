import { useState, useEffect, useRef } from "react";
import { X, Plus, Save, Loader2, Trash2, Check, Pencil, Copy, FileText, Shield } from "lucide-react";
import {
  listPromptVersions,
  createPromptVersion,
  updatePromptVersion,
  deletePromptVersion,
  activatePromptVersion,
  getSystemPrompt,
  type PromptVersion,
} from "@/lib/api";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function SystemPromptPanel({ open, onClose }: Props) {
  const [versions, setVersions] = useState<PromptVersion[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null); // null = 内置默认
  const [content, setContent] = useState("");
  const [originalContent, setOriginalContent] = useState("");
  const [editingName, setEditingName] = useState<string | null>(null);
  const [nameInput, setNameInput] = useState("");
  const [defaultContent, setDefaultContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const deleteTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const nameInputRef = useRef<HTMLInputElement>(null);
  const newNameRef = useRef<HTMLInputElement>(null);

  // 加载版本列表
  useEffect(() => {
    if (!open) return;
    setMessage(null);
    setCreating(false);
    setConfirmDelete(null);
    setLoading(true);
    Promise.all([listPromptVersions(), getSystemPrompt()])
      .then(([data, defaultData]) => {
        setVersions(data.versions);
        setActiveId(data.active_id);
        setDefaultContent(defaultData.content);
        // 默认选中激活版本，没有则选内置默认
        if (data.active_id) {
          setSelectedId(data.active_id);
          const v = data.versions.find((v) => v.id === data.active_id);
          if (v) {
            setContent(v.content);
            setOriginalContent(v.content);
          }
        } else {
          setSelectedId(null);
          setContent(defaultData.content);
          setOriginalContent(defaultData.content);
        }
      })
      .catch(() => setMessage({ type: "err", text: "加载失败" }))
      .finally(() => setLoading(false));
  }, [open]);

  // 清理定时器
  useEffect(() => () => { if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current); }, []);

  function selectVersion(id: string | null) {
    setSelectedId(id);
    setMessage(null);
    setEditingName(null);
    if (id === null) {
      setContent(defaultContent);
      setOriginalContent(defaultContent);
    } else {
      const v = versions.find((v) => v.id === id);
      if (v) {
        setContent(v.content);
        setOriginalContent(v.content);
      }
    }
  }

  async function handleSave() {
    if (selectedId === null) return; // 内置默认不可编辑
    setSaving(true);
    setMessage(null);
    try {
      const { version } = await updatePromptVersion(selectedId, { content });
      setOriginalContent(content);
      setVersions((prev) => prev.map((v) => (v.id === selectedId ? version : v)));
      setMessage({ type: "ok", text: "已保存" });
    } catch {
      setMessage({ type: "err", text: "保存失败" });
    }
    setSaving(false);
  }

  async function handleActivate(id: string | null) {
    setMessage(null);
    try {
      await activatePromptVersion(id ?? "default");
      setActiveId(id);
      setMessage({ type: "ok", text: "已切换，新会话将使用此提示词" });
    } catch {
      setMessage({ type: "err", text: "切换失败" });
    }
  }

  async function handleCreate() {
    const name = newName.trim();
    if (!name) return;
    setMessage(null);
    try {
      const { version } = await createPromptVersion(name);
      setVersions((prev) => [...prev, version]);
      setCreating(false);
      setNewName("");
      selectVersion(version.id);
    } catch {
      setMessage({ type: "err", text: "创建失败" });
    }
  }

  async function handleDelete(id: string) {
    setMessage(null);
    try {
      await deletePromptVersion(id);
      setVersions((prev) => prev.filter((v) => v.id !== id));
      setConfirmDelete(null);
      if (activeId === id) setActiveId(null);
      if (selectedId === id) selectVersion(null);
    } catch {
      setMessage({ type: "err", text: "删除失败" });
    }
  }

  function startConfirmDelete(id: string) {
    setConfirmDelete(id);
    if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current);
    deleteTimerRef.current = setTimeout(() => setConfirmDelete(null), 3000);
  }

  async function handleRename(id: string) {
    const name = nameInput.trim();
    if (!name) { setEditingName(null); return; }
    try {
      const { version } = await updatePromptVersion(id, { name });
      setVersions((prev) => prev.map((v) => (v.id === id ? version : v)));
      setEditingName(null);
    } catch {
      setMessage({ type: "err", text: "重命名失败" });
    }
  }

  async function handleDuplicate(id: string) {
    const src = versions.find((v) => v.id === id);
    if (!src) return;
    setMessage(null);
    try {
      const { version } = await createPromptVersion(src.name + " (副本)", src.content);
      setVersions((prev) => [...prev, version]);
      selectVersion(version.id);
    } catch {
      setMessage({ type: "err", text: "复制失败" });
    }
  }

  const hasChanges = content !== originalContent;
  const isDefault = selectedId === null;

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex animate-fade-in">
      <div className="flex-1 bg-black/5 backdrop-blur-[2px]" onClick={onClose} />

      <div className="w-[720px] max-w-[90vw] bg-sand-50 border-l border-sand-200/60 flex flex-col
                      shadow-[-8px_0_24px_rgba(0,0,0,0.06)] animate-slide-right">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3.5 border-b border-sand-200/60">
          <span className="text-[0.8125rem] font-semibold text-sand-700">系统提示词</span>
          <button onClick={onClose}
            className="p-1.5 rounded-lg text-sand-400 hover:text-sand-600 hover:bg-sand-200/50 transition-colors">
            <X size={15} />
          </button>
        </div>

        {loading ? (
          <div className="flex-1 flex items-center justify-center text-sand-400">
            <Loader2 size={18} className="animate-spin mr-2" />加载中
          </div>
        ) : (
          <div className="flex-1 flex min-h-0">
            {/* Left: version list */}
            <div className="w-[220px] border-r border-sand-200/60 flex flex-col">
              <div className="flex-1 overflow-y-auto py-2">
                {/* 内置默认 */}
                <button
                  onClick={() => selectVersion(null)}
                  className={`w-full text-left px-3 py-2 text-[0.8125rem] flex items-center gap-2 transition-colors
                    ${isDefault ? "bg-sand-200/50 text-sand-800" : "text-sand-600 hover:bg-sand-100"}`}
                >
                  <Shield size={12} className="opacity-40 shrink-0" />
                  <span className="flex-1 truncate">内置默认</span>
                  {activeId === null && (
                    <span className="text-2xs px-1.5 py-0.5 rounded-full bg-green-50 text-green-600 shrink-0">激活</span>
                  )}
                </button>

                {/* 自定义版本 */}
                {versions.map((v) => (
                  <div key={v.id}
                    className={`group flex items-center px-3 py-2 text-[0.8125rem] transition-colors cursor-pointer
                      ${selectedId === v.id ? "bg-sand-200/50 text-sand-800" : "text-sand-600 hover:bg-sand-100"}`}
                    onClick={() => selectVersion(v.id)}
                  >
                    <FileText size={12} className="opacity-40 mr-2 shrink-0" />
                    {editingName === v.id ? (
                      <input
                        ref={nameInputRef}
                        value={nameInput}
                        onChange={(e) => setNameInput(e.target.value)}
                        onBlur={() => handleRename(v.id)}
                        onKeyDown={(e) => { if (e.key === "Enter") handleRename(v.id); if (e.key === "Escape") setEditingName(null); }}
                        className="flex-1 min-w-0 bg-white border border-sand-300 rounded px-1.5 py-0.5 text-xs outline-none"
                        onClick={(e) => e.stopPropagation()}
                      />
                    ) : (
                      <span className="flex-1 truncate"
                        onDoubleClick={(e) => { e.stopPropagation(); setEditingName(v.id); setNameInput(v.name); setTimeout(() => nameInputRef.current?.focus(), 0); }}>
                        {v.name}
                      </span>
                    )}
                    {activeId === v.id && (
                      <span className="text-2xs px-1.5 py-0.5 rounded-full bg-green-50 text-green-600 shrink-0 ml-1">激活</span>
                    )}
                  </div>
                ))}

                {/* 新建 */}
                {creating ? (
                  <div className="px-3 py-2">
                    <input
                      ref={newNameRef}
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") handleCreate(); if (e.key === "Escape") setCreating(false); }}
                      onBlur={() => { if (!newName.trim()) setCreating(false); }}
                      placeholder="版本名称..."
                      className="w-full bg-white border border-sand-300 rounded px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-sand-400"
                      autoFocus
                    />
                  </div>
                ) : (
                  <button
                    onClick={() => { setCreating(true); setNewName(""); setTimeout(() => newNameRef.current?.focus(), 0); }}
                    className="w-full text-left px-3 py-2 text-xs text-sand-400 hover:text-sand-600 hover:bg-sand-100 transition-colors flex items-center gap-1.5"
                  >
                    <Plus size={12} />新建版本
                  </button>
                )}
              </div>
            </div>

            {/* Right: editor */}
            <div className="flex-1 flex flex-col min-w-0">
              {/* Toolbar */}
              <div className="px-4 py-2.5 border-b border-sand-200/40 flex items-center gap-2">
                {!isDefault && (
                  <>
                    <button onClick={handleSave} disabled={saving || !hasChanges}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs
                                 bg-sand-800 text-white hover:bg-sand-900
                                 disabled:bg-sand-300 disabled:cursor-default transition-colors">
                      {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
                      保存
                    </button>
                    <button onClick={() => handleDuplicate(selectedId!)}
                      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs text-sand-600 hover:bg-sand-200/50 transition-colors">
                      <Copy size={12} />复制
                    </button>
                    <button onClick={() => { setEditingName(selectedId); setNameInput(versions.find(v => v.id === selectedId)?.name || ""); setTimeout(() => nameInputRef.current?.focus(), 0); }}
                      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs text-sand-600 hover:bg-sand-200/50 transition-colors">
                      <Pencil size={12} />重命名
                    </button>
                  </>
                )}
                {/* 激活按钮 */}
                {(isDefault ? activeId !== null : activeId !== selectedId) && (
                  <button onClick={() => handleActivate(selectedId)}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs text-green-700 bg-green-50 hover:bg-green-100 transition-colors">
                    <Check size={12} />激活
                  </button>
                )}
                <div className="ml-auto flex items-center gap-2">
                  {message && (
                    <span className={`text-2xs ${message.type === "ok" ? "text-green-600" : "text-red-500"}`}>
                      {message.text}
                    </span>
                  )}
                  {!isDefault && (
                    confirmDelete === selectedId ? (
                      <button onClick={() => handleDelete(selectedId!)}
                        className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs text-red-600 bg-red-50 hover:bg-red-100 transition-colors">
                        <Trash2 size={12} />确认删除
                      </button>
                    ) : (
                      <button onClick={() => startConfirmDelete(selectedId!)}
                        className="p-1.5 rounded-lg text-sand-400 hover:text-red-500 hover:bg-red-50 transition-colors">
                        <Trash2 size={13} />
                      </button>
                    )
                  )}
                </div>
              </div>

              {/* Editor area */}
              <div className="flex-1 overflow-hidden p-4">
                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  readOnly={isDefault}
                  className={`w-full h-full resize-none rounded-lg border border-sand-200/60 bg-white
                             px-4 py-3 text-[0.8125rem] text-sand-800 leading-relaxed
                             focus:outline-none focus:ring-1 focus:ring-sand-300/60 font-mono
                             ${isDefault ? "bg-sand-50 text-sand-500" : ""}`}
                  placeholder="输入系统提示词..."
                  spellCheck={false}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
