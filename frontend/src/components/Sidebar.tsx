import { useState, useEffect, useRef } from "react";
import { Plus, MessageSquare, BookOpen, Database, PanelLeftClose, PanelLeftOpen, Pencil, Trash2, ScrollText, Wand2, Settings2, FolderOpen, LogOut, User, ExternalLink } from "lucide-react";
import type { Session } from "@/types";
import { listSessions, renameSession, deleteSession } from "@/lib/api";

function stripMarkdown(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/\*(.+?)\*/g, "$1")
    .replace(/__(.+?)__/g, "$1")
    .replace(/_(.+?)_/g, "$1")
    .replace(/~~(.+?)~~/g, "$1")
    .replace(/`(.+?)`/g, "$1")
    .replace(/#{1,6}\s+/g, "")
    .replace(/!\[.*?\]\(.*?\)/g, "")
    .replace(/\[(.+?)\]\(.*?\)/g, "$1")
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/^\s*\d+\.\s+/gm, "")
    .replace(/>\s?/g, "")
    .replace(/\n+/g, " ")
    .trim();
}

interface SidebarProps {
  currentThreadId: string;
  onNewSession: () => void;
  onSelectSession: (threadId: string) => void;
  onDeleteSession: (threadId: string) => void;
  onOpenMemory: () => void;
  onOpenKB: () => void;
  onOpenSkills: () => void;
  onOpenSystemPrompt: () => void;
  onOpenSettings: () => void;
  onOpenWorkspace: () => void;
  user?: { username: string; quota: number; used_quota: number; group: string } | null;
  onLogout?: () => void;
}

interface ContextMenu {
  x: number;
  y: number;
  threadId: string;
}

export default function Sidebar({
  currentThreadId,
  onNewSession,
  onSelectSession,
  onDeleteSession,
  onOpenMemory,
  onOpenKB,
  onOpenSkills,
  onOpenSystemPrompt,
  onOpenSettings,
  onOpenWorkspace,
  user,
  onLogout,
}: SidebarProps) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const [contextMenu, setContextMenu] = useState<ContextMenu | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const editRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadSessions();
  }, [currentThreadId]);

  // 点击任意位置关闭右键菜单
  useEffect(() => {
    if (!contextMenu) return;
    const close = () => setContextMenu(null);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, [contextMenu]);

  // 进入编辑模式时自动 focus
  useEffect(() => {
    if (editingId) {
      editRef.current?.focus();
      editRef.current?.select();
    }
  }, [editingId]);

  async function loadSessions() {
    try {
      const { sessions: list } = await listSessions();
      setSessions(list);
    } catch {
      // backend not running
    }
  }

  function getDisplayName(s: Session): string {
    if (s.title) return s.title;
    if (s.preview) return stripMarkdown(s.preview);
    return s.thread_id.slice(0, 8) + "...";
  }

  function handleContextMenu(e: React.MouseEvent, threadId: string) {
    e.preventDefault();
    setContextMenu({ x: e.clientX, y: e.clientY, threadId });
  }

  function startRename(threadId: string) {
    const session = sessions.find((s) => s.thread_id === threadId);
    setEditingId(threadId);
    setEditValue(session ? getDisplayName(session) : "");
    setContextMenu(null);
  }

  async function commitRename() {
    if (!editingId) return;
    const title = editValue.trim();
    if (title) {
      try {
        await renameSession(editingId, title);
        setSessions((prev) =>
          prev.map((s) => (s.thread_id === editingId ? { ...s, title } : s))
        );
      } catch (e) {
        console.error("rename failed:", e);
      }
    }
    setEditingId(null);
  }

  async function handleDelete(threadId: string) {
    setContextMenu(null);
    try {
      await deleteSession(threadId);
      setSessions((prev) => prev.filter((s) => s.thread_id !== threadId));
      onDeleteSession(threadId);
    } catch (e) {
      console.error("delete failed:", e);
    }
  }

  // Collapsed state
  if (collapsed) {
    return (
      <div className="w-12 bg-sand-50 border-r border-sand-200/60 flex flex-col items-center py-3 gap-1 shrink-0">
        <button
          onClick={() => setCollapsed(false)}
          className="p-2 rounded-lg text-sand-400 hover:text-sand-600 hover:bg-sand-200/50 transition-colors"
          title="展开侧边栏"
        >
          <PanelLeftOpen size={16} />
        </button>
        <button
          onClick={onNewSession}
          className="p-2 rounded-lg text-sand-400 hover:text-sand-600 hover:bg-sand-200/50 transition-colors"
          title="新建会话"
        >
          <Plus size={16} />
        </button>
        <div className="flex-1" />
        <button
          onClick={onOpenSystemPrompt}
          className="p-2 rounded-lg text-sand-400 hover:text-sand-600 hover:bg-sand-200/50 transition-colors"
          title="系统提示词"
        >
          <ScrollText size={16} />
        </button>
        <button
          onClick={onOpenKB}
          className="p-2 rounded-lg text-sand-400 hover:text-sand-600 hover:bg-sand-200/50 transition-colors"
          title="知识库"
        >
          <Database size={16} />
        </button>
        <button
          onClick={onOpenSkills}
          className="p-2 rounded-lg text-sand-400 hover:text-sand-600 hover:bg-sand-200/50 transition-colors"
          title="技能"
        >
          <Wand2 size={16} />
        </button>
        <button
          onClick={onOpenMemory}
          className="p-2 rounded-lg text-sand-400 hover:text-sand-600 hover:bg-sand-200/50 transition-colors"
          title="记忆"
        >
          <BookOpen size={16} />
        </button>
        <button
          onClick={onOpenWorkspace}
          className="p-2 rounded-lg text-sand-400 hover:text-sand-600 hover:bg-sand-200/50 transition-colors"
          title="工作区"
        >
          <FolderOpen size={16} />
        </button>
        <button
          onClick={onOpenSettings}
          className="p-2 rounded-lg text-sand-400 hover:text-sand-600 hover:bg-sand-200/50 transition-colors"
          title="设置"
        >
          <Settings2 size={16} />
        </button>
        {user && (
          <button
            onClick={onLogout}
            className="p-2 rounded-lg text-sand-400 hover:text-red-500 hover:bg-red-50 transition-colors"
            title={`${user.username} - 退出登录`}
          >
            <LogOut size={16} />
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="w-60 bg-sand-50 border-r border-sand-200/60 flex flex-col shrink-0 animate-slide-right">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-3">
        <span className="text-[0.8125rem] font-semibold text-sand-700 tracking-tight pl-1">
          Arcstone-econ
        </span>
        <button
          onClick={() => setCollapsed(true)}
          className="p-1.5 rounded-lg text-sand-400 hover:text-sand-600 hover:bg-sand-200/50 transition-colors"
        >
          <PanelLeftClose size={15} />
        </button>
      </div>

      {/* New session */}
      <div className="px-2.5 pb-2">
        <button
          onClick={onNewSession}
          className="flex items-center gap-2 w-full px-3 py-2 text-[0.8125rem]
                     rounded-xl border border-sand-200/80 text-sand-600
                     hover:bg-white hover:border-sand-300/80 hover:shadow-[0_1px_3px_rgba(0,0,0,0.04)]
                     transition-all duration-150"
        >
          <Plus size={14} strokeWidth={2} />
          新建会话
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto px-2 py-1">
        {sessions.length === 0 && (
          <p className="text-2xs text-sand-400 text-center mt-8 px-4 leading-relaxed">
            暂无历史会话
          </p>
        )}
        {sessions.map((s) => {
          const isActive = s.thread_id === currentThreadId;
          const isEditing = editingId === s.thread_id;

          return (
            <div
              key={s.thread_id}
              className={`flex items-center gap-2 w-full px-2.5 py-2 text-[0.8125rem] rounded-xl
                          text-left transition-all duration-100 mb-0.5 group
                          ${isActive
                            ? "bg-white text-sand-800 shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
                            : "text-sand-500 hover:bg-white/60 hover:text-sand-700"
                          }`}
              onClick={() => !isEditing && onSelectSession(s.thread_id)}
              onContextMenu={(e) => handleContextMenu(e, s.thread_id)}
              role="button"
              tabIndex={0}
            >
              <MessageSquare size={13} className="shrink-0 opacity-50" />

              {isEditing ? (
                <input
                  ref={editRef}
                  className="flex-1 min-w-0 bg-transparent outline-none border-b border-accent
                             text-sand-800 text-[0.8125rem] py-0 leading-snug"
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onBlur={commitRename}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") commitRename();
                    if (e.key === "Escape") setEditingId(null);
                  }}
                  onClick={(e) => e.stopPropagation()}
                />
              ) : (
                <span className="truncate leading-snug flex-1 min-w-0">
                  {getDisplayName(s)}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Bottom: system prompt + knowledge base + skills + memory + settings */}
      <div className="px-2.5 py-2.5 border-t border-sand-200/60">
        <button
          onClick={onOpenSystemPrompt}
          className="flex items-center gap-2 w-full px-3 py-2 text-[0.8125rem] rounded-xl
                     text-sand-500 hover:bg-white/60 hover:text-sand-700 transition-colors"
        >
          <ScrollText size={14} className="opacity-60" />
          系统提示词
        </button>
        <button
          onClick={onOpenKB}
          className="flex items-center gap-2 w-full px-3 py-2 text-[0.8125rem] rounded-xl
                     text-sand-500 hover:bg-white/60 hover:text-sand-700 transition-colors"
        >
          <Database size={14} className="opacity-60" />
          知识库
        </button>
        <button
          onClick={onOpenSkills}
          className="flex items-center gap-2 w-full px-3 py-2 text-[0.8125rem] rounded-xl
                     text-sand-500 hover:bg-white/60 hover:text-sand-700 transition-colors"
        >
          <Wand2 size={14} className="opacity-60" />
          技能
        </button>
        <button
          onClick={onOpenMemory}
          className="flex items-center gap-2 w-full px-3 py-2 text-[0.8125rem] rounded-xl
                     text-sand-500 hover:bg-white/60 hover:text-sand-700 transition-colors"
        >
          <BookOpen size={14} className="opacity-60" />
          记忆
        </button>
        <button
          onClick={onOpenWorkspace}
          className="flex items-center gap-2 w-full px-3 py-2 text-[0.8125rem] rounded-xl
                     text-sand-500 hover:bg-white/60 hover:text-sand-700 transition-colors"
        >
          <FolderOpen size={14} className="opacity-60" />
          工作区
        </button>
        <button
          onClick={onOpenSettings}
          className="flex items-center gap-2 w-full px-3 py-2 text-[0.8125rem] rounded-xl
                     text-sand-500 hover:bg-white/60 hover:text-sand-700 transition-colors"
        >
          <Settings2 size={14} className="opacity-60" />
          设置
        </button>
      </div>

      {/* User info */}
      {user && (
        <div className="px-3 py-2.5 border-t border-sand-200/60">
          <div className="flex items-center gap-2 mb-1.5">
            <User size={13} className="text-sand-400 shrink-0" />
            <span className="text-[0.8125rem] text-sand-700 font-medium truncate">{user.username}</span>
          </div>
          <div className="text-[0.6875rem] text-sand-400 ml-5 mb-2">
            余额: {((user.quota - user.used_quota) / 500000).toFixed(1)}万 tokens
          </div>
          <div className="flex items-center gap-2 ml-5">
            <button
              onClick={() => {
                const url = (localStorage.getItem("econ-agent-new-api-url") || "http://43.128.44.82:3000").replace(/\/v1$/, "");
                window.open(`${url}/topup`, "_blank");
              }}
              className="flex items-center gap-1 text-[0.6875rem] text-[#c8956c] hover:text-[#b8855c] transition-colors"
            >
              <ExternalLink size={10} />
              充值
            </button>
            <button
              onClick={onLogout}
              className="text-[0.6875rem] text-sand-400 hover:text-red-500 transition-colors"
            >
              退出
            </button>
          </div>
        </div>
      )}

      {/* Context menu */}
      {contextMenu && (
        <div
          className="fixed z-50 bg-white rounded-xl shadow-[0_4px_16px_rgba(0,0,0,0.1),0_0_0_1px_rgba(0,0,0,0.04)]
                     py-1 min-w-[140px] animate-fade-in"
          style={{ left: contextMenu.x, top: contextMenu.y }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            className="flex items-center gap-2.5 w-full px-3.5 py-2 text-[0.8125rem]
                       text-sand-700 hover:bg-sand-50 transition-colors"
            onClick={() => startRename(contextMenu.threadId)}
          >
            <Pencil size={13} className="text-sand-400" />
            重命名
          </button>
          <button
            className="flex items-center gap-2.5 w-full px-3.5 py-2 text-[0.8125rem]
                       text-red-600 hover:bg-red-50 transition-colors"
            onClick={() => handleDelete(contextMenu.threadId)}
          >
            <Trash2 size={13} />
            删除
          </button>
        </div>
      )}
    </div>
  );
}
