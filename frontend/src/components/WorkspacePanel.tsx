import { useState, useEffect, useRef, useCallback } from "react";
import { FolderOpen, RefreshCw, FileText, Trash2, X, FolderInput, ChevronRight, FolderSearch, ExternalLink } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import {
  getWorkspace,
  setWorkspace,
  readWorkspaceFile,
  deleteWorkspaceFile,
  pickWorkspaceFolder,
  revealInExplorer,
  workspaceRawUrl,
  type WorkspaceFile,
} from "@/lib/api";

const IMAGE_EXTS = new Set([".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"]);
const MD_EXTS = new Set([".md", ".markdown"]);

function getExt(path: string) {
  const dot = path.lastIndexOf(".");
  return dot >= 0 ? path.slice(dot).toLowerCase() : "";
}

interface WorkspacePanelProps {
  open: boolean;
  onClose: () => void;
}

export default function WorkspacePanel({ open, onClose }: WorkspacePanelProps) {
  const [workspacePath, setWorkspacePath] = useState("");
  const [files, setFiles] = useState<WorkspaceFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [pathInput, setPathInput] = useState("");
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [picking, setPicking] = useState(false);
  const [splitRatio, setSplitRatio] = useState(0.4); // 文件列表占比（0.2~0.8）
  const containerRef = useRef<HTMLDivElement>(null);
  const pathInputRef = useRef<HTMLInputElement>(null);

  const handleDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const container = containerRef.current;
    if (!container) return;

    const onMove = (ev: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      const ratio = (ev.clientX - rect.left) / rect.width;
      setSplitRatio(Math.min(0.8, Math.max(0.2, ratio)));
    };
    const onUp = () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, []);

  useEffect(() => {
    if (open) load();
  }, [open]);

  useEffect(() => {
    if (editing) pathInputRef.current?.focus();
  }, [editing]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await getWorkspace();
      setWorkspacePath(data.path);
      setPathInput(data.path);
      setFiles(data.files);
    } catch (e: any) {
      setError(e?.message || "无法连接后端");
    }
    setLoading(false);
  }

  async function handleSetPath() {
    if (!pathInput.trim()) return;
    setSaving(true);
    try {
      const data = await setWorkspace(pathInput.trim());
      setWorkspacePath(data.path);
      setPathInput(data.path);
      setEditing(false);
      setSelectedFile(null);
      setFileContent(null);
      await load();
    } catch (e: any) {
      alert(e?.message || "切换失败");
    }
    setSaving(false);
  }

  async function handlePick() {
    setPicking(true);
    try {
      const data = await pickWorkspaceFolder();
      if (data.path) {
        setWorkspacePath(data.path);
        setPathInput(data.path);
        setEditing(false);
        setSelectedFile(null);
        setFileContent(null);
        await load();
      }
    } catch (e: any) {
      alert(e?.message || "选择失败");
    }
    setPicking(false);
  }

  async function handleReveal(filePath?: string, e?: React.MouseEvent) {
    e?.stopPropagation();
    try {
      await revealInExplorer(filePath);
    } catch {
      // 静默失败
    }
  }

  async function handleSelectFile(filePath: string) {
    if (selectedFile === filePath) {
      setSelectedFile(null);
      setFileContent(null);
      return;
    }
    setSelectedFile(filePath);
    const ext = getExt(filePath);
    // 图片不需要读文本内容
    if (IMAGE_EXTS.has(ext)) {
      setFileContent(null);
      setFileLoading(false);
      return;
    }
    setFileLoading(true);
    try {
      const data = await readWorkspaceFile(filePath);
      setFileContent(data.binary ? "(二进制文件，无法预览)" : data.content);
    } catch {
      setFileContent("(读取失败)");
    }
    setFileLoading(false);
  }

  async function handleDelete(filePath: string, e: React.MouseEvent) {
    e.stopPropagation();
    if (!confirm(`删除文件 ${filePath}？`)) return;
    try {
      await deleteWorkspaceFile(filePath);
      if (selectedFile === filePath) {
        setSelectedFile(null);
        setFileContent(null);
      }
      await load();
    } catch {
      alert("删除失败");
    }
  }

  // 把文件列表按目录分组，用于显示分隔线
  function getDir(filePath: string) {
    const idx = filePath.lastIndexOf("/");
    return idx >= 0 ? filePath.slice(0, idx) : "";
  }

  function formatSize(bytes: number) {
    if (bytes < 1024) return `${bytes}B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
  }

  function renderPreview() {
    if (!selectedFile) return null;
    const ext = getExt(selectedFile);

    if (IMAGE_EXTS.has(ext)) {
      return (
        <div className="flex items-center justify-center h-full p-4">
          <img
            src={workspaceRawUrl(selectedFile)}
            alt={selectedFile}
            className="max-w-full max-h-full object-contain rounded"
          />
        </div>
      );
    }

    if (MD_EXTS.has(ext) && fileContent && fileContent !== "(二进制文件，无法预览)") {
      return (
        <div className="prose prose-sm max-w-none text-sand-700 p-1">
          <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
            {fileContent}
          </ReactMarkdown>
        </div>
      );
    }

    return (
      <pre className="text-xs text-sand-700 whitespace-pre-wrap font-mono leading-relaxed">
        {fileContent}
      </pre>
    );
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex animate-fade-in">
      <div className="flex-1 bg-black/5 backdrop-blur-[2px]" onClick={onClose} />
      <div className="w-[680px] max-w-[90vw] bg-sand-50 border-l border-sand-200/60 flex flex-col
                      shadow-[-8px_0_24px_rgba(0,0,0,0.06)] animate-slide-right">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-sand-200/60 shrink-0">
        <div className="flex items-center gap-2">
          <FolderOpen size={15} className="text-sand-500" />
          <span className="text-[0.8125rem] font-semibold text-sand-700">工作区</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={load}
            className="p-1.5 rounded-lg text-sand-400 hover:text-sand-600 hover:bg-sand-100 transition-colors"
            title="刷新"
          >
            <RefreshCw size={13} />
          </button>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-sand-400 hover:text-sand-600 hover:bg-sand-100 transition-colors"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Path bar */}
      <div className="px-4 py-2.5 border-b border-sand-200/60 shrink-0">
        {editing ? (
          <div className="flex items-center gap-2">
            <input
              ref={pathInputRef}
              value={pathInput}
              onChange={(e) => setPathInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSetPath();
                if (e.key === "Escape") { setEditing(false); setPathInput(workspacePath); }
              }}
              className="flex-1 min-w-0 text-xs px-2 py-1.5 rounded-lg border border-sand-300
                         bg-white text-sand-700 outline-none focus:border-accent font-mono"
              placeholder="输入目录路径，如 D:/projects/my-mine"
            />
            <button
              onClick={handlePick}
              disabled={picking}
              className="p-1.5 rounded-lg text-sand-400 hover:text-accent hover:bg-sand-100
                         disabled:opacity-50 transition-colors shrink-0"
              title="浏览..."
            >
              <FolderSearch size={14} />
            </button>
            <button
              onClick={handleSetPath}
              disabled={saving}
              className="px-3 py-1.5 text-xs rounded-lg bg-accent text-white
                         hover:bg-accent/90 disabled:opacity-50 transition-colors shrink-0"
            >
              {saving ? "…" : "确定"}
            </button>
            <button
              onClick={() => { setEditing(false); setPathInput(workspacePath); }}
              className="px-2 py-1.5 text-xs rounded-lg text-sand-500 hover:bg-sand-100 transition-colors shrink-0"
            >
              取消
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <button
              onClick={() => setEditing(true)}
              className="flex items-center gap-2 flex-1 min-w-0 text-left group"
              title="点击切换工作区目录"
            >
              <FolderInput size={12} className="text-sand-400 shrink-0" />
              <span className="text-xs text-sand-500 font-mono truncate flex-1 min-w-0">
                {workspacePath || "未设置"}
              </span>
              <ChevronRight size={11} className="text-sand-300 group-hover:text-sand-500 shrink-0 transition-colors" />
            </button>
            <button
              onClick={handlePick}
              disabled={picking}
              className="p-1 rounded-lg text-sand-300 hover:text-accent hover:bg-sand-100
                         disabled:opacity-50 transition-colors shrink-0"
              title="浏览..."
            >
              <FolderSearch size={13} />
            </button>
            <button
              onClick={() => handleReveal()}
              className="p-1 rounded-lg text-sand-300 hover:text-accent hover:bg-sand-100
                         transition-colors shrink-0"
              title="在文件管理器中打开"
            >
              <ExternalLink size={12} />
            </button>
          </div>
        )}
      </div>

      {/* Main: file list + file preview */}
      <div ref={containerRef} className="flex flex-1 min-h-0">
        {/* File list */}
        <div
          className="flex flex-col min-h-0 border-r border-sand-200/60"
          style={{ width: selectedFile ? `${splitRatio * 100}%` : "100%" }}
        >
          <div className="flex-1 overflow-y-auto px-2 py-2">
            {loading ? (
              <p className="text-xs text-sand-400 text-center mt-8">加载中...</p>
            ) : error ? (
              <div className="text-center mt-12 px-4">
                <p className="text-xs text-red-500 leading-relaxed">{error}</p>
                <p className="text-2xs text-sand-400 mt-2">请确认后端已重启</p>
              </div>
            ) : files.length === 0 ? (
              <div className="text-center mt-12 px-4">
                <FolderOpen size={28} className="text-sand-300 mx-auto mb-3" />
                <p className="text-xs text-sand-400 leading-relaxed">工作区为空</p>
                <p className="text-2xs text-sand-300 mt-1">Agent 生成的报告和文件会出现在这里</p>
              </div>
            ) : (
              (() => {
                let lastDir = "__none__";
                return files.map((f) => {
                  const dir = getDir(f.path);
                  const showDir = dir !== lastDir;
                  lastDir = dir;
                  const fileName = f.path.slice(dir ? dir.length + 1 : 0);
                  return (
                    <div key={f.path}>
                      {showDir && dir && (
                        <div className="px-2 py-1 mt-1 text-2xs text-sand-400 font-mono">
                          {dir}/
                        </div>
                      )}
                      <div
                        className={`flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-pointer group
                                    transition-colors text-xs
                                    ${selectedFile === f.path
                                      ? "bg-accent/10 text-accent"
                                      : "text-sand-600 hover:bg-sand-100"
                                    }`}
                        onClick={() => handleSelectFile(f.path)}
                      >
                        <FileText size={12} className="shrink-0 opacity-60" />
                        <span className="truncate flex-1 min-w-0 font-mono">{fileName}</span>
                        <span className="text-2xs text-sand-400 shrink-0 opacity-0 group-hover:opacity-100">
                          {formatSize(f.size)}
                        </span>
                        <button
                          onClick={(e) => handleReveal(f.path, e)}
                          className="shrink-0 p-0.5 rounded text-sand-300 hover:text-accent
                                     opacity-0 group-hover:opacity-100 transition-all"
                          title="在文件管理器中定位"
                        >
                          <ExternalLink size={11} />
                        </button>
                        <button
                          onClick={(e) => handleDelete(f.path, e)}
                          className="shrink-0 p-0.5 rounded text-sand-300 hover:text-red-500
                                     opacity-0 group-hover:opacity-100 transition-all"
                          title="删除"
                        >
                          <Trash2 size={11} />
                        </button>
                      </div>
                    </div>
                  );
                });
              })()
            )}
          </div>
        </div>

        {/* File preview */}
        {selectedFile && (
          <>
            {/* Drag handle */}
            <div
              onMouseDown={handleDragStart}
              className="w-1 shrink-0 cursor-col-resize bg-sand-200/60 hover:bg-accent/30
                         active:bg-accent/50 transition-colors"
            />
            <div className="flex flex-col min-h-0" style={{ width: `${(1 - splitRatio) * 100}%` }}>
            <div className="flex items-center justify-between px-3 py-2 border-b border-sand-200/60 shrink-0">
              <span className="text-2xs text-sand-500 font-mono truncate flex-1 min-w-0">
                {selectedFile}
              </span>
              <button
                onClick={() => { setSelectedFile(null); setFileContent(null); }}
                className="ml-2 p-0.5 text-sand-300 hover:text-sand-500 shrink-0"
              >
                <X size={12} />
              </button>
            </div>
            <div className="flex-1 overflow-auto p-3">
              {fileLoading ? (
                <p className="text-xs text-sand-400">加载中...</p>
              ) : (
                renderPreview()
              )}
            </div>
            </div>
          </>
        )}
      </div>
      </div>
    </div>
  );
}
