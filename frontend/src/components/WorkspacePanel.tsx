import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { FolderOpen, RefreshCw, FileText, Trash2, X, FolderInput, ChevronRight, ChevronDown, FolderSearch, ExternalLink, Maximize2, Folder } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import katex from "katex";
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

/** 文件树节点 */
interface TreeNode {
  name: string;
  path: string; // 完整相对路径
  isDir: boolean;
  file?: WorkspaceFile;
  children: TreeNode[];
}

/** 将扁平文件列表构建为树结构 */
function buildTree(files: WorkspaceFile[]): TreeNode[] {
  const root: TreeNode = { name: "", path: "", isDir: true, children: [] };
  for (const f of files) {
    const parts = f.path.split("/");
    let cur = root;
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const isLast = i === parts.length - 1;
      if (isLast) {
        cur.children.push({ name: part, path: f.path, isDir: false, file: f, children: [] });
      } else {
        let dir = cur.children.find((c) => c.isDir && c.name === part);
        if (!dir) {
          dir = { name: part, path: parts.slice(0, i + 1).join("/"), isDir: true, children: [] };
          cur.children.push(dir);
        }
        cur = dir;
      }
    }
  }
  // 排序：目录在前，文件在后，各自按名称排序
  function sortTree(nodes: TreeNode[]) {
    nodes.sort((a, b) => {
      if (a.isDir !== b.isDir) return a.isDir ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    for (const n of nodes) if (n.isDir) sortTree(n.children);
  }
  sortTree(root.children);
  return root.children;
}

interface WorkspacePanelProps {
  open: boolean;
  onClose: () => void;
  threadId?: string;
}

export default function WorkspacePanel({ open, onClose, threadId }: WorkspacePanelProps) {
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
  const [collapsedDirs, setCollapsedDirs] = useState<Set<string>>(new Set());
  const containerRef = useRef<HTMLDivElement>(null);
  const pathInputRef = useRef<HTMLInputElement>(null);

  const tree = useMemo(() => buildTree(files), [files]);

  function toggleDir(dirPath: string) {
    setCollapsedDirs((prev) => {
      const next = new Set(prev);
      if (next.has(dirPath)) next.delete(dirPath);
      else next.add(dirPath);
      return next;
    });
  }

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
      const data = await setWorkspace(pathInput.trim(), threadId);
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
      const data = await pickWorkspaceFolder(threadId);
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

  function formatSize(bytes: number) {
    if (bytes < 1024) return `${bytes}B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
  }

  /** 简易 markdown → HTML（内联，不依赖外部库） */
  function simpleMarkdownToHtml(md: string): string {
    let html = md;
    // 代码块 ```...``` （先提取保护，避免内部被其他规则误处理）
    const codeBlocks: string[] = [];
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_m, _lang, code) => {
      const idx = codeBlocks.length;
      codeBlocks.push(`<pre><code>${code.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")}</code></pre>`);
      return `\x00CB${idx}\x00`;
    });
    // 公式：$$...$$ (display) 和 $...$ (inline)，用 KaTeX 预渲染
    html = html.replace(/\$\$([\s\S]+?)\$\$/g, (_m, tex) => {
      try { return katex.renderToString(tex.trim(), { displayMode: true, throwOnError: false }); }
      catch { return `<div class="katex-error">$$${tex}$$</div>`; }
    });
    html = html.replace(/\$([^\$\n]+?)\$/g, (_m, tex) => {
      try { return katex.renderToString(tex.trim(), { displayMode: false, throwOnError: false }); }
      catch { return `<span class="katex-error">$${tex}$</span>`; }
    });
    // 行内代码
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    // 表格
    html = html.replace(/((?:^\|.+\|$\n?)+)/gm, (table) => {
      const rows = table.trim().split("\n").filter(r => r.trim());
      if (rows.length < 2) return table;
      const isSep = (r: string) => /^\|[\s\-:|]+\|$/.test(r.trim());
      let out = '<table>';
      let inHead = true;
      for (const row of rows) {
        if (isSep(row)) { inHead = false; continue; }
        const cells = row.split("|").slice(1, -1).map(c => c.trim());
        const tag = inHead ? "th" : "td";
        out += "<tr>" + cells.map(c => `<${tag}>${c}</${tag}>`).join("") + "</tr>";
        if (inHead) inHead = false;
      }
      return out + '</table>';
    });
    // 标题
    html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>');
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
    // 粗体、斜体
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    // 链接
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
    // 无序列表
    html = html.replace(/^[-*] (.+)$/gm, '<li>$1</li>');
    html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');
    // 有序列表
    html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
    // 水平线
    html = html.replace(/^---+$/gm, '<hr/>');
    // 段落（连续非空行）
    html = html.replace(/\n{2,}/g, '</p><p>');
    html = '<p>' + html + '</p>';
    // 清理空段落
    html = html.replace(/<p>\s*<\/p>/g, '');
    html = html.replace(/<p>\s*(<h[1-4]>)/g, '$1');
    html = html.replace(/(<\/h[1-4]>)\s*<\/p>/g, '$1');
    html = html.replace(/<p>\s*(<ul>)/g, '$1');
    html = html.replace(/(<\/ul>)\s*<\/p>/g, '$1');
    html = html.replace(/<p>\s*(<table>)/g, '$1');
    html = html.replace(/(<\/table>)\s*<\/p>/g, '$1');
    html = html.replace(/<p>\s*(<pre>)/g, '$1');
    html = html.replace(/(<\/pre>)\s*<\/p>/g, '$1');
    html = html.replace(/<p>\s*(<hr\/>)/g, '$1');
    // 恢复代码块
    html = html.replace(/\x00CB(\d+)\x00/g, (_m, idx) => codeBlocks[Number(idx)]);
    return html;
  }

  /** 在新窗口中预览文件 */
  function openInNewWindow() {
    if (!selectedFile) return;
    const ext = getExt(selectedFile);
    const isImage = IMAGE_EXTS.has(ext);
    const fileName = selectedFile.split("/").pop() || selectedFile;

    if (isImage) {
      const imgUrl = workspaceRawUrl(selectedFile);
      const win = window.open("", "_blank", "width=800,height=600");
      if (!win) return;
      win.document.write(`<!DOCTYPE html><html><head><title>${fileName}</title>
        <style>body{margin:0;display:flex;align-items:center;justify-content:center;min-height:100vh;background:#f5f5f0;}
        img{max-width:95vw;max-height:95vh;object-fit:contain;}</style></head>
        <body><img src="${imgUrl}" alt="${fileName}"/></body></html>`);
      win.document.close();
      return;
    }

    if (!fileContent) return;
    const win = window.open("", "_blank", "width=800,height=600");
    if (!win) return;

    const isMd = MD_EXTS.has(ext);
    if (isMd) {
      // 从当前页面提取 KaTeX CSS（已通过 import 注入到 <head>）
      const katexCss = Array.from(document.styleSheets)
        .filter(s => { try { return s.cssRules && Array.from(s.cssRules).some(r => r.cssText.includes(".katex")); } catch { return false; } })
        .map(s => Array.from(s.cssRules).map(r => r.cssText).join("\n"))
        .join("\n");

      const rendered = simpleMarkdownToHtml(fileContent);
      win.document.write(`<!DOCTYPE html><html><head><title>${fileName}</title>
        <meta charset="utf-8"/>
        <style>${katexCss}</style>
        <style>
          body{max-width:800px;margin:40px auto;padding:0 20px;font-family:-apple-system,system-ui,"Segoe UI",sans-serif;color:#333;line-height:1.7;background:#fafaf5;}
          h1{font-size:1.6em;border-bottom:1px solid #ddd;padding-bottom:0.3em;}
          h2{font-size:1.3em;border-bottom:1px solid #eee;padding-bottom:0.2em;}
          h3{font-size:1.1em;} h4{font-size:1em;}
          code{background:#f0ede6;padding:2px 5px;border-radius:3px;font-size:0.9em;font-family:Consolas,monospace;}
          pre{background:#f0ede6;padding:14px;border-radius:6px;overflow-x:auto;}
          pre code{background:none;padding:0;}
          table{border-collapse:collapse;margin:1em 0;width:100%;}
          th,td{border:1px solid #ddd;padding:8px 12px;text-align:left;}
          th{background:#f5f5f0;font-weight:600;}
          a{color:#2563eb;text-decoration:none;} a:hover{text-decoration:underline;}
          ul{padding-left:1.5em;} li{margin:0.3em 0;}
          hr{border:none;border-top:1px solid #ddd;margin:1.5em 0;}
          strong{font-weight:600;}
        </style></head>
        <body>${rendered}</body></html>`);
    } else {
      const escaped = fileContent.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
      win.document.write(`<!DOCTYPE html><html><head><title>${fileName}</title>
        <meta charset="utf-8"/>
        <style>body{margin:20px;font-family:Consolas,monospace;font-size:13px;color:#333;background:#fafaf5;}
        pre{white-space:pre-wrap;line-height:1.5;}</style></head>
        <body><pre>${escaped}</pre></body></html>`);
    }
    win.document.close();
  }

  /** 递归渲染文件树节点 */
  function renderTreeNodes(nodes: TreeNode[], depth: number = 0): React.ReactNode[] {
    const result: React.ReactNode[] = [];
    for (const node of nodes) {
      if (node.isDir) {
        const collapsed = collapsedDirs.has(node.path);
        result.push(
          <div key={`dir-${node.path}`}>
            <div
              className="flex items-center gap-1.5 px-2 py-1 rounded-lg cursor-pointer
                         text-sand-500 hover:bg-sand-100 transition-colors text-xs"
              style={{ paddingLeft: `${depth * 12 + 8}px` }}
              onClick={() => toggleDir(node.path)}
            >
              {collapsed
                ? <ChevronRight size={11} className="shrink-0 text-sand-400" />
                : <ChevronDown size={11} className="shrink-0 text-sand-400" />
              }
              <Folder size={12} className="shrink-0 text-sand-400" />
              <span className="font-mono truncate">{node.name}</span>
            </div>
            {!collapsed && renderTreeNodes(node.children, depth + 1)}
          </div>
        );
      } else {
        const f = node.file!;
        result.push(
          <div
            key={f.path}
            className={`flex items-center gap-2 py-1.5 rounded-lg cursor-pointer group
                        transition-colors text-xs
                        ${selectedFile === f.path
                          ? "bg-accent/10 text-accent"
                          : "text-sand-600 hover:bg-sand-100"
                        }`}
            style={{ paddingLeft: `${depth * 12 + 8}px`, paddingRight: "8px" }}
            onClick={() => handleSelectFile(f.path)}
          >
            <FileText size={12} className="shrink-0 opacity-60" />
            <span className="truncate flex-1 min-w-0 font-mono">{node.name}</span>
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
        );
      }
    }
    return result;
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
              renderTreeNodes(tree)
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
              <div className="flex items-center gap-1 ml-2 shrink-0">
                <button
                  onClick={openInNewWindow}
                  className="p-0.5 text-sand-300 hover:text-accent transition-colors"
                  title="在新窗口中预览"
                >
                  <Maximize2 size={12} />
                </button>
                <button
                  onClick={() => { setSelectedFile(null); setFileContent(null); }}
                  className="p-0.5 text-sand-300 hover:text-sand-500"
                >
                  <X size={12} />
                </button>
              </div>
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
