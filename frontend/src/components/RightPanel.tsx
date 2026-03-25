import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import {
  FolderOpen, FileText, Trash2, ChevronRight, ChevronDown,
  RefreshCw, ExternalLink, Folder, BookOpen, User, FolderSearch,
  Scale, File, Pencil, Save, XCircle, Plus, Check, PanelRightClose,
  PanelRightOpen, Loader2, Image as ImageIcon, FolderInput, Maximize2,
  FileSpreadsheet, FileType,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import {
  getWorkspace, setWorkspace, readWorkspaceFile, deleteWorkspaceFile,
  revealInExplorer, workspaceRawUrl, pickWorkspaceFolder, renameWorkspaceFile,
  listMemory, getMemory, updateMemory, deleteMemory,
  type WorkspaceFile,
} from "@/lib/api";
import type { MemoryItem } from "@/types";

// ======================== 工具函数 ========================

const IMAGE_EXTS = new Set([".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"]);
const MD_EXTS = new Set([".md", ".markdown"]);
const OFFICE_EXTS = new Set([".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"]);
const EXCEL_EXTS = new Set([".xls", ".xlsx"]);
const WORD_EXTS = new Set([".doc", ".docx"]);
const PDF_EXTS = new Set([".pdf"]);
function getExt(p: string) { const d = p.lastIndexOf("."); return d >= 0 ? p.slice(d).toLowerCase() : ""; }

interface TreeNode {
  name: string; path: string; isDir: boolean;
  file?: WorkspaceFile; children: TreeNode[];
}

function buildTree(files: WorkspaceFile[]): TreeNode[] {
  const root: TreeNode = { name: "", path: "", isDir: true, children: [] };
  for (const f of files) {
    const parts = f.path.split("/");
    let cur = root;
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      if (i === parts.length - 1) {
        cur.children.push({ name: part, path: f.path, isDir: false, file: f, children: [] });
      } else {
        let dir = cur.children.find(c => c.isDir && c.name === part);
        if (!dir) {
          dir = { name: part, path: parts.slice(0, i + 1).join("/"), isDir: true, children: [] };
          cur.children.push(dir);
        }
        cur = dir;
      }
    }
  }
  function sortTree(nodes: TreeNode[]) {
    nodes.sort((a, b) => {
      if (a.isDir !== b.isDir) return a.isDir ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    nodes.forEach(n => { if (n.isDir) sortTree(n.children); });
  }
  sortTree(root.children);
  return root.children;
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

// 记忆分组
type GroupKey = "profile" | "projects" | "decisions" | "documents" | "other";
function categorize(key: string): GroupKey {
  if (key === "/user_profile.md" || key === "/instructions.md" || key === "/index.md") return "profile";
  if (key.startsWith("/projects/")) return "projects";
  if (key.startsWith("/decisions/")) return "decisions";
  if (key.startsWith("/documents/")) return "documents";
  return "other";
}
const GROUP_ORDER: GroupKey[] = ["profile", "projects", "decisions", "documents", "other"];
const GROUP_META: Record<GroupKey, { label: string; icon: typeof User }> = {
  profile: { label: "用户画像", icon: User },
  projects: { label: "项目", icon: FolderOpen },
  decisions: { label: "决策", icon: Scale },
  documents: { label: "文档", icon: FileText },
  other: { label: "其他", icon: File },
};
// 英文文件名 → 中文显示名
const DISPLAY_NAMES: Record<string, string> = {
  "user_profile": "用户画像",
  "instructions": "使用说明",
  "index": "记忆索引",
};
function displayName(key: string) {
  const raw = key.split("/").pop()?.replace(/\.md$/, "") || key;
  return DISPLAY_NAMES[raw] || raw;
}

// ======================== 主组件 ========================

type Tab = "workspace" | "memory";

interface RightPanelProps {
  collapsed: boolean;
  onToggle: () => void;
  threadId: string;
  refreshKey?: number;
}

const RIGHT_WIDTH_KEY = "econ-agent-right-panel-width";
const RIGHT_DEFAULT_W = 340;
const RIGHT_MIN_W = 240;
const RIGHT_MAX_W = 600;

export default function RightPanel({ collapsed, onToggle, threadId, refreshKey }: RightPanelProps) {
  const [tab, setTab] = useState<Tab>("workspace");
  const [width, setWidth] = useState(() => {
    const saved = localStorage.getItem(RIGHT_WIDTH_KEY);
    return saved ? Math.max(RIGHT_MIN_W, Math.min(RIGHT_MAX_W, Number(saved))) : RIGHT_DEFAULT_W;
  });

  const handleDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = width;
    const onMove = (ev: MouseEvent) => {
      // 向左拖 = 变宽（因为是右侧面板）
      const newW = Math.max(RIGHT_MIN_W, Math.min(RIGHT_MAX_W, startW + (startX - ev.clientX)));
      setWidth(newW);
    };
    const onUp = () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      localStorage.setItem(RIGHT_WIDTH_KEY, String(width));
    };
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, [width]);

  // 拖拽结束时保存
  useEffect(() => {
    localStorage.setItem(RIGHT_WIDTH_KEY, String(width));
  }, [width]);

  if (collapsed) {
    return (
      <div className="w-10 bg-sand-50/80 border-l border-sand-200/60 flex flex-col items-center py-3 gap-1 shrink-0">
        <button onClick={onToggle} className="p-2 rounded-lg text-sand-400 hover:text-sand-600 hover:bg-sand-200/50 transition-colors" title="展开面板">
          <PanelRightOpen size={15} />
        </button>
        <div className="flex-1" />
        <button onClick={() => { setTab("workspace"); onToggle(); }} className="p-2 rounded-lg text-sand-400 hover:text-sand-600 hover:bg-sand-200/50 transition-colors" title="工作区文件">
          <FolderOpen size={15} />
        </button>
        <button onClick={() => { setTab("memory"); onToggle(); }} className="p-2 rounded-lg text-sand-400 hover:text-sand-600 hover:bg-sand-200/50 transition-colors" title="AI 记忆">
          <BookOpen size={15} />
        </button>
      </div>
    );
  }

  return (
    <div className="flex shrink-0" style={{ width }}>
      {/* 拖拽手柄 */}
      <div
        onMouseDown={handleDragStart}
        className="w-1 cursor-col-resize hover:bg-[#c8956c]/20 active:bg-[#c8956c]/30 transition-colors shrink-0"
      />
      <div className="flex-1 min-w-0 bg-sand-50/80 border-l border-sand-200/60 flex flex-col">
      {/* Header: tabs + collapse */}
      <div className="flex items-center border-b border-sand-200/60 px-1 shrink-0">
        <button
          onClick={() => setTab("workspace")}
          className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-[0.75rem] font-medium transition-colors border-b-2 ${
            tab === "workspace"
              ? "text-[#c8956c] border-[#c8956c]"
              : "text-sand-400 border-transparent hover:text-sand-600"
          }`}
        >
          <FolderOpen size={13} />
          文件
        </button>
        <button
          onClick={() => setTab("memory")}
          className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-[0.75rem] font-medium transition-colors border-b-2 ${
            tab === "memory"
              ? "text-[#c8956c] border-[#c8956c]"
              : "text-sand-400 border-transparent hover:text-sand-600"
          }`}
        >
          <BookOpen size={13} />
          记忆
        </button>
        <button onClick={onToggle} className="p-1.5 rounded-lg text-sand-400 hover:text-sand-600 hover:bg-sand-200/50 transition-colors mx-1" title="收起面板">
          <PanelRightClose size={14} />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {tab === "workspace" ? (
          <WorkspaceTab threadId={threadId} refreshKey={refreshKey} />
        ) : (
          <MemoryTab />
        )}
      </div>
      </div>
    </div>
  );
}

// ======================== 新窗口预览 ========================

function openInNewWindow(filePath: string, content: string) {
  const ext = getExt(filePath);
  const fileName = filePath.split("/").pop() || filePath;

  if (IMAGE_EXTS.has(ext)) {
    const imgUrl = workspaceRawUrl(filePath);
    const win = window.open("", "_blank", "width=800,height=600");
    if (!win) return;
    win.document.write(`<!DOCTYPE html><html><head><title>${fileName}</title>
      <style>body{margin:0;display:flex;align-items:center;justify-content:center;min-height:100vh;background:#faf9f7;}
      img{max-width:95vw;max-height:95vh;object-fit:contain;border-radius:8px;}</style></head>
      <body><img src="${imgUrl}" alt="${fileName}"/></body></html>`);
    win.document.close();
    return;
  }

  if (!content) return;
  const win = window.open("", "_blank", "width=800,height=600");
  if (!win) return;

  if (MD_EXTS.has(ext)) {
    // 用 CDN 的 marked + KaTeX 在新窗口里渲染，保证公式正确
    const escaped = content.replace(/\\/g, "\\\\").replace(/`/g, "\\`").replace(/\$/g, "\\$");
    win.document.write(`<!DOCTYPE html><html><head><title>${fileName}</title>
      <meta charset="utf-8"/>
      <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap"/>
      <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css"/>
      <script src="https://cdn.jsdelivr.net/npm/marked@15.0.4/marked.min.js"><\/script>
      <script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"><\/script>
      <style>
        html,body{height:auto;overflow-y:auto;}
        body{max-width:800px;margin:40px auto;padding:0 20px;font-family:"DM Sans","Noto Sans SC",system-ui,sans-serif;color:#5a5347;line-height:1.7;background:#faf9f7;font-size:15px;}
        h1{font-size:1.5em;border-bottom:1px solid #ebe7e0;padding-bottom:0.3em;color:#4a453c;}
        h2{font-size:1.25em;border-bottom:1px solid #ebe7e0;padding-bottom:0.2em;color:#4a453c;}
        h3{font-size:1.1em;color:#5a5347;} h4{font-size:1em;}
        code{background:#f5f3ef;padding:2px 5px;border-radius:4px;font-size:0.875em;font-family:"JetBrains Mono",Consolas,monospace;color:#6e6556;}
        pre{background:#f5f3ef;padding:14px;border-radius:8px;overflow-x:auto;border:1px solid #ebe7e0;}
        pre code{background:none;padding:0;}
        table{border-collapse:collapse;margin:1em 0;width:100%;}
        th,td{border:1px solid #ebe7e0;padding:8px 12px;text-align:left;}
        th{background:#f5f3ef;font-weight:600;color:#5a5347;}
        a{color:#c8956c;text-decoration:none;} a:hover{text-decoration:underline;color:#a07450;}
        ul,ol{padding-left:1.5em;} li{margin:0.3em 0;}
        hr{border:none;border-top:1px solid #ebe7e0;margin:1.5em 0;}
        strong{font-weight:600;color:#4a453c;}
        .katex-display{margin:1em 0;overflow:hidden;}
        .katex{font-size:1em;}
      </style></head>
      <body><div id="content"></div>
      <script>
        var raw = \`${escaped}\`;
        // 先处理公式：$$...$$ 和 $...$
        var placeholders = [];
        raw = raw.replace(/\\$\\$([\\s\\S]+?)\\$\\$/g, function(m, tex) {
          var i = placeholders.length;
          try { placeholders.push(katex.renderToString(tex.trim(), {displayMode:true,throwOnError:false})); }
          catch(e) { placeholders.push('<div style="color:red">' + tex + '</div>'); }
          return '%%KATEX' + i + '%%';
        });
        raw = raw.replace(/\\$([^\\$\\n]+?)\\$/g, function(m, tex) {
          var i = placeholders.length;
          try { placeholders.push(katex.renderToString(tex.trim(), {displayMode:false,throwOnError:false})); }
          catch(e) { placeholders.push('<span style="color:red">' + tex + '</span>'); }
          return '%%KATEX' + i + '%%';
        });
        var html = marked.parse(raw);
        for (var i = 0; i < placeholders.length; i++) {
          html = html.replace('%%KATEX' + i + '%%', placeholders[i]);
        }
        document.getElementById('content').innerHTML = html;
      <\/script></body></html>`);
  } else {
    const escaped = content.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    win.document.write(`<!DOCTYPE html><html><head><title>${fileName}</title>
      <meta charset="utf-8"/>
      <style>body{margin:40px auto;max-width:800px;padding:0 20px;font-family:"JetBrains Mono",Consolas,monospace;font-size:13px;color:#5a5347;background:#faf9f7;}
      pre{white-space:pre-wrap;line-height:1.6;}</style></head>
      <body><pre>${escaped}</pre></body></html>`);
  }
  win.document.close();
}

// ======================== 工作区 Tab ========================

function WorkspaceTab({ threadId, refreshKey }: { threadId: string; refreshKey?: number }) {
  const [workspacePath, setWorkspacePath] = useState("");
  const [files, setFiles] = useState<WorkspaceFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [preview, setPreview] = useState<string>("");
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set());
  const [editingPath, setEditingPath] = useState(false);
  const [pathInput, setPathInput] = useState("");
  const [renamingFile, setRenamingFile] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const pathRef = useRef<HTMLInputElement>(null);
  const renameRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getWorkspace();
      setFiles(data.files || []);
      setWorkspacePath(data.path || "");
      setPathInput(data.path || "");
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);
  // 外部触发刷新（如流式结束后）
  useEffect(() => { if (refreshKey) load(); }, [refreshKey]);
  useEffect(() => { if (editingPath) pathRef.current?.focus(); }, [editingPath]);

  const tree = useMemo(() => buildTree(files), [files]);

  const handleSelect = useCallback(async (path: string) => {
    setSelected(path);
    setRenamingFile(null);
    const ext = getExt(path);
    if (IMAGE_EXTS.has(ext) || OFFICE_EXTS.has(ext)) { setPreview(""); return; }
    try {
      const data = await readWorkspaceFile(path);
      setPreview(data.content || "");
    } catch { setPreview("读取失败"); }
  }, []);

  const handleDelete = useCallback(async (path: string) => {
    if (!confirm(`删除 ${path}？`)) return;
    try {
      await deleteWorkspaceFile(path);
      setFiles(prev => prev.filter(f => f.path !== path));
      if (selected === path) { setSelected(null); setPreview(""); }
    } catch { /* ignore */ }
  }, [selected]);

  const toggleDir = useCallback((path: string) => {
    setExpandedDirs(prev => {
      const next = new Set(prev);
      next.has(path) ? next.delete(path) : next.add(path);
      return next;
    });
  }, []);

  const handleSetPath = useCallback(async () => {
    if (!pathInput.trim()) return;
    try {
      await setWorkspace(pathInput.trim(), threadId);
      setEditingPath(false);
      load();
    } catch { /* ignore */ }
  }, [pathInput, threadId, load]);

  const handlePick = useCallback(async () => {
    try {
      const data = await pickWorkspaceFolder(threadId);
      if (data.path) { setSelected(null); setPreview(""); load(); }
    } catch { /* ignore */ }
  }, [threadId, load]);

  const startRename = useCallback((path: string) => {
    setRenamingFile(path);
    setRenameValue(path.split("/").pop() || "");
    setTimeout(() => renameRef.current?.focus(), 50);
  }, []);

  const handleRename = useCallback(async () => {
    if (!renamingFile || !renameValue.trim()) { setRenamingFile(null); return; }
    try {
      const result = await renameWorkspaceFile(renamingFile, renameValue.trim());
      if (result.ok) {
        if (selected === renamingFile) setSelected(result.new_path);
        load();
      }
    } catch { /* ignore */ }
    setRenamingFile(null);
  }, [renamingFile, renameValue, selected, load]);

  const selectedExt = selected ? getExt(selected) : "";

  return (
    <div className="flex flex-col h-full">
      {/* 工作区路径 */}
      <div className="px-2 py-1.5 border-b border-sand-200/40">
        {editingPath ? (
          <div className="flex items-center gap-1">
            <input
              ref={pathRef}
              value={pathInput}
              onChange={e => setPathInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") handleSetPath(); if (e.key === "Escape") setEditingPath(false); }}
              className="flex-1 text-[0.625rem] text-sand-600 bg-white rounded px-1.5 py-0.5 border border-sand-200 focus:outline-none focus:border-[#c8956c]/50 font-mono"
            />
            <button onClick={handleSetPath} className="p-0.5 text-emerald-500 hover:text-emerald-600"><Check size={11} /></button>
            <button onClick={() => setEditingPath(false)} className="p-0.5 text-sand-400 hover:text-sand-600"><XCircle size={11} /></button>
          </div>
        ) : (
          <div className="flex items-center gap-1">
            <button onClick={() => setEditingPath(true)} className="flex-1 text-[0.625rem] text-sand-500 truncate text-left hover:text-sand-700 transition-colors font-mono" title={workspacePath}>
              {workspacePath || "未设置"}
            </button>
            <button onClick={handlePick} className="p-0.5 rounded text-sand-400 hover:text-sand-600 transition-colors" title="选择文件夹">
              <FolderInput size={11} />
            </button>
            <button onClick={() => revealInExplorer()} className="p-0.5 rounded text-sand-400 hover:text-sand-600 transition-colors" title="打开文件夹">
              <ExternalLink size={11} />
            </button>
          </div>
        )}
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-1 px-2 py-1 border-b border-sand-200/40">
        <button onClick={load} className="p-1 rounded text-sand-400 hover:text-sand-600 transition-colors" title="刷新">
          <RefreshCw size={11} className={loading ? "animate-spin" : ""} />
        </button>
        {selected && (
          <>
            <button onClick={() => revealInExplorer(selected)} className="p-1 rounded text-sand-400 hover:text-sand-600 transition-colors" title="在文件管理器中显示">
              <ExternalLink size={11} />
            </button>
            <button onClick={() => openInNewWindow(selected, preview)} className="p-1 rounded text-sand-400 hover:text-sand-600 transition-colors" title="新窗口预览">
              <Maximize2 size={11} />
            </button>
            <button onClick={() => handleDelete(selected)} className="p-1 rounded text-sand-400 hover:text-red-500 transition-colors" title="删除">
              <Trash2 size={11} />
            </button>
          </>
        )}
        <span className="ml-auto text-[0.5625rem] text-sand-400">{files.length} 文件</span>
      </div>

      {/* File list or preview */}
      {selected ? (
        <div className="flex-1 min-h-0 flex flex-col">
          <button
            onClick={() => { setSelected(null); setPreview(""); }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[0.6875rem] text-[#c8956c] hover:bg-sand-100/80 transition-colors border-b border-sand-200/40"
          >
            <ChevronRight size={10} className="rotate-180" />
            {selected.split("/").pop()}
          </button>
          <div className="flex-1 min-h-0 overflow-auto px-3 py-2">
            {IMAGE_EXTS.has(selectedExt) ? (
              <img
                src={workspaceRawUrl(selected)}
                alt={selected}
                className="max-w-full rounded-lg shadow-sm cursor-pointer"
                onClick={() => window.open(workspaceRawUrl(selected), "_blank")}
              />
            ) : PDF_EXTS.has(selectedExt) ? (
              <iframe
                src={workspaceRawUrl(selected)}
                className="w-full h-full rounded-lg border border-sand-200/60"
                title={selected}
              />
            ) : OFFICE_EXTS.has(selectedExt) ? (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-sand-500">
                {fileIcon(selectedExt)}
                <span className="text-[0.75rem]">{selected.split("/").pop()}</span>
                <button
                  onClick={() => revealInExplorer(selected)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-[0.75rem] rounded-lg bg-sand-100 hover:bg-sand-200/80 text-sand-600 transition-colors"
                >
                  <ExternalLink size={12} />
                  在文件管理器中打开
                </button>
              </div>
            ) : MD_EXTS.has(selectedExt) ? (
              <div className="prose prose-sm max-w-none text-sand-700">
                <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
                  {preview}
                </ReactMarkdown>
              </div>
            ) : (
              <pre className="text-[0.625rem] text-sand-600 whitespace-pre-wrap break-all font-mono leading-relaxed">{preview}</pre>
            )}
          </div>
        </div>
      ) : (
        <div className="flex-1 min-h-0 overflow-y-auto">
          {files.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-sand-400">
              <FolderSearch size={24} className="mb-2 opacity-40" />
              <span className="text-[0.75rem]">暂无文件</span>
            </div>
          ) : (
            <div className="py-1">
              {tree.map(node => (
                <FileTreeNode
                  key={node.path}
                  node={node}
                  depth={0}
                  expanded={expandedDirs}
                  onToggle={toggleDir}
                  onSelect={handleSelect}
                  onReveal={(p) => revealInExplorer(p)}
                  onDelete={handleDelete}
                  onRename={startRename}
                />
              ))}
              {/* 内联重命名输入框 */}
              {renamingFile && (
                <div className="flex items-center gap-1 px-3 py-1 bg-sand-100/80 border-y border-sand-200/40">
                  <input
                    ref={renameRef}
                    value={renameValue}
                    onChange={e => setRenameValue(e.target.value)}
                    onKeyDown={e => { if (e.key === "Enter") handleRename(); if (e.key === "Escape") setRenamingFile(null); }}
                    onBlur={handleRename}
                    className="flex-1 text-[0.6875rem] bg-white rounded px-1.5 py-0.5 border border-sand-200 focus:outline-none focus:border-[#c8956c]/50 font-mono"
                  />
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function fileIcon(ext: string) {
  if (IMAGE_EXTS.has(ext)) return <ImageIcon size={11} className="text-purple-400 shrink-0" />;
  if (EXCEL_EXTS.has(ext)) return <FileSpreadsheet size={11} className="text-emerald-500 shrink-0" />;
  if (WORD_EXTS.has(ext)) return <FileType size={11} className="text-blue-500 shrink-0" />;
  if (PDF_EXTS.has(ext)) return <FileText size={11} className="text-red-400 shrink-0" />;
  return <FileText size={11} className="text-sand-400 shrink-0" />;
}

function FileTreeNode({ node, depth, expanded, onToggle, onSelect, onReveal, onDelete, onRename }: {
  node: TreeNode; depth: number;
  expanded: Set<string>;
  onToggle: (path: string) => void;
  onSelect: (path: string) => void;
  onReveal: (path: string) => void;
  onDelete: (path: string) => void;
  onRename: (path: string) => void;
}) {
  const isOpen = expanded.has(node.path);
  const pl = 8 + depth * 14;
  const ext = getExt(node.name);

  if (node.isDir) {
    return (
      <>
        <button
          onClick={() => onToggle(node.path)}
          className="flex items-center gap-1.5 w-full py-1 text-[0.6875rem] text-sand-600 hover:bg-sand-100/80 transition-colors"
          style={{ paddingLeft: pl }}
        >
          {isOpen ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          <Folder size={12} className="text-sand-400" />
          <span className="truncate">{node.name}</span>
        </button>
        {isOpen && node.children.map(child => (
          <FileTreeNode key={child.path} node={child} depth={depth + 1} expanded={expanded} onToggle={onToggle} onSelect={onSelect} onReveal={onReveal} onDelete={onDelete} onRename={onRename} />
        ))}
      </>
    );
  }

  return (
    <div
      className="flex items-center gap-1 w-full py-1 text-[0.6875rem] text-sand-600 hover:bg-sand-100/80 transition-colors group cursor-pointer"
      style={{ paddingLeft: pl + 14, paddingRight: 4 }}
      onClick={() => onSelect(node.path)}
    >
      {fileIcon(ext)}
      <span className="truncate flex-1 min-w-0 text-left">{node.name}</span>
      {/* hover 操作按钮 */}
      <span className="hidden group-hover:flex items-center gap-0.5 shrink-0">
        <button onClick={e => { e.stopPropagation(); onReveal(node.path); }} className="p-0.5 rounded text-sand-300 hover:text-sand-600" title="定位文件">
          <ExternalLink size={10} />
        </button>
        <button onClick={e => { e.stopPropagation(); onRename(node.path); }} className="p-0.5 rounded text-sand-300 hover:text-sand-600" title="重命名">
          <Pencil size={10} />
        </button>
        <button onClick={e => { e.stopPropagation(); onDelete(node.path); }} className="p-0.5 rounded text-sand-300 hover:text-red-500" title="删除">
          <Trash2 size={10} />
        </button>
      </span>
      {/* 非 hover 时显示大小 */}
      {node.file && (
        <span className="text-[0.5rem] text-sand-300 shrink-0 group-hover:hidden">{formatSize(node.file.size)}</span>
      )}
    </div>
  );
}

// ======================== 记忆 Tab ========================

function MemoryTab() {
  const [items, setItems] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const [expandedGroups, setExpandedGroups] = useState<Set<GroupKey>>(new Set(GROUP_ORDER));

  useEffect(() => {
    listMemory().then(({ items: list }) => {
      setItems(list);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const grouped = useMemo(() => {
    const map: Record<GroupKey, MemoryItem[]> = { profile: [], projects: [], decisions: [], documents: [], other: [] };
    items.forEach(it => map[categorize(it.key)].push(it));
    return map;
  }, [items]);

  const handleSelect = useCallback(async (key: string) => {
    setSelected(key);
    setEditing(false);
    try {
      const data = await getMemory(key);
      setContent(data.content || "");
    } catch {
      setContent("读取失败");
    }
  }, []);

  const handleSave = useCallback(async () => {
    if (!selected) return;
    try {
      await updateMemory(selected, editValue);
      setContent(editValue);
      setEditing(false);
    } catch { /* ignore */ }
  }, [selected, editValue]);

  const handleDelete = useCallback(async (key: string) => {
    try {
      await deleteMemory(key);
      setItems(prev => prev.filter(it => it.key !== key));
      if (selected === key) { setSelected(null); setContent(""); }
    } catch { /* ignore */ }
  }, [selected]);

  const toggleGroup = useCallback((g: GroupKey) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      next.has(g) ? next.delete(g) : next.add(g);
      return next;
    });
  }, []);

  if (loading) {
    return <div className="flex items-center justify-center h-full"><Loader2 size={16} className="animate-spin text-sand-400" /></div>;
  }

  // 详情视图
  if (selected) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center gap-1 px-2 py-1.5 border-b border-sand-200/40">
          <button onClick={() => { setSelected(null); setEditing(false); }}
            className="flex items-center gap-1 text-[0.75rem] text-[#c8956c] hover:text-[#b8855c] transition-colors">
            <ChevronRight size={11} className="rotate-180" />
            返回
          </button>
          <span className="ml-auto flex items-center gap-1">
            {editing ? (
              <>
                <button onClick={handleSave} className="p-1 rounded text-emerald-500 hover:bg-emerald-50 transition-colors" title="保存"><Save size={12} /></button>
                <button onClick={() => setEditing(false)} className="p-1 rounded text-sand-400 hover:text-sand-600 transition-colors" title="取消"><XCircle size={12} /></button>
              </>
            ) : (
              <>
                <button onClick={() => { setEditValue(content); setEditing(true); }} className="p-1 rounded text-sand-400 hover:text-sand-600 transition-colors" title="编辑"><Pencil size={12} /></button>
                <button onClick={() => handleDelete(selected)} className="p-1 rounded text-sand-400 hover:text-red-500 transition-colors" title="删除"><Trash2 size={12} /></button>
              </>
            )}
          </span>
        </div>
        <div className="px-2 py-1 border-b border-sand-200/30">
          <span className="text-[0.6875rem] text-sand-500 font-medium">{displayName(selected)}</span>
        </div>
        <div className="flex-1 min-h-0 overflow-auto px-3 py-2">
          {editing ? (
            <textarea
              value={editValue}
              onChange={e => setEditValue(e.target.value)}
              className="w-full h-full text-[0.75rem] text-sand-700 font-mono bg-transparent resize-none focus:outline-none leading-relaxed"
            />
          ) : (
            <div className="prose prose-sm max-w-none text-sand-700">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    );
  }

  // 列表视图
  return (
    <div className="flex-1 min-h-0 overflow-y-auto">
      {GROUP_ORDER.map(g => {
        const list = grouped[g];
        if (list.length === 0) return null;
        const { label, icon: GIcon } = GROUP_META[g];
        const isOpen = expandedGroups.has(g);
        return (
          <div key={g}>
            <button
              onClick={() => toggleGroup(g)}
              className="flex items-center gap-1.5 w-full px-3 py-1.5 text-[0.6875rem] font-medium text-sand-500 hover:bg-sand-100/60 transition-colors"
            >
              {isOpen ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
              <GIcon size={11} className="opacity-50" />
              <span>{label}</span>
              <span className="ml-auto text-[0.5625rem] text-sand-300">{list.length}</span>
            </button>
            {isOpen && list.map(it => (
              <button
                key={it.key}
                onClick={() => handleSelect(it.key)}
                className="flex items-center gap-1.5 w-full pl-8 pr-3 py-1.5 text-[0.6875rem] text-sand-600 hover:bg-sand-100/80 transition-colors"
              >
                <FileText size={10} className="text-sand-400 shrink-0" />
                <span className="truncate text-left">{displayName(it.key)}</span>
              </button>
            ))}
          </div>
        );
      })}
      {items.length === 0 && (
        <div className="flex flex-col items-center justify-center h-full text-sand-400">
          <BookOpen size={24} className="mb-2 opacity-40" />
          <span className="text-[0.75rem]">暂无记忆</span>
        </div>
      )}
    </div>
  );
}
