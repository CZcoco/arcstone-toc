import { useState, useEffect, useRef, useCallback } from "react";
import {
  X, Upload, Loader2, Trash2, ChevronDown, ChevronRight, Plus,
  FileText, CheckCircle2, XCircle, Clock, Settings2, Database,
} from "lucide-react";
import type { KBDocument, KBConfig } from "@/types";
import {
  listKBDocuments, uploadToKB, getKBUploadStatus, deleteKBDocuments,
  setKBRagConfig,
} from "@/lib/api";

const KB_STORAGE_KEY = "arcstone-econ-kb-configs";
const KB_ACTIVE_KEY = "arcstone-econ-kb-active";

function loadKBConfigs(): KBConfig[] {
  try {
    const raw = localStorage.getItem(KB_STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return [];
}

function saveKBConfigs(configs: KBConfig[]) {
  localStorage.setItem(KB_STORAGE_KEY, JSON.stringify(configs));
}

function loadActiveKBId(): string {
  return localStorage.getItem(KB_ACTIVE_KEY) || "";
}

function saveActiveKBId(id: string) {
  localStorage.setItem(KB_ACTIVE_KEY, id);
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function StatusBadge({ status }: { status: string }) {
  const upper = status.toUpperCase();
  if (upper === "ACTIVE" || upper === "FINISH" || upper === "SUCCEED") {
    return (
      <span className="inline-flex items-center gap-1 text-2xs px-1.5 py-0.5 rounded-full bg-green-50 text-green-600">
        <CheckCircle2 size={10} />
        已就绪
      </span>
    );
  }
  if (upper.includes("FAIL") || upper === "ERROR") {
    return (
      <span className="inline-flex items-center gap-1 text-2xs px-1.5 py-0.5 rounded-full bg-red-50 text-red-600">
        <XCircle size={10} />
        失败
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-2xs px-1.5 py-0.5 rounded-full bg-amber-50 text-amber-600">
      <Clock size={10} />
      处理中
    </span>
  );
}

const ACCEPT_TYPES = ".pdf,.docx,.doc,.txt,.md,.pptx,.ppt,.xlsx,.xls,.html,.png,.jpg,.jpeg,.bmp,.gif";

interface UploadJob {
  jobId: string;
  filename: string;
  status: string;
  progress: string;
  error: string | null;
}

interface KnowledgeBasePanelProps {
  open: boolean;
  onClose: () => void;
}

export default function KnowledgeBasePanel({ open, onClose }: KnowledgeBasePanelProps) {
  // KB configs
  const [kbConfigs, setKBConfigs] = useState<KBConfig[]>(loadKBConfigs);
  const [activeKBId, setActiveKBId] = useState<string>(loadActiveKBId);
  const [showKBDropdown, setShowKBDropdown] = useState(false);
  const [showAddKB, setShowAddKB] = useState(false);
  const [newKBId, setNewKBId] = useState("");
  const [newKBName, setNewKBName] = useState("");
  const [newKBDesc, setNewKBDesc] = useState("");

  // Documents
  const [documents, setDocuments] = useState<KBDocument[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);

  // Upload
  const [uploadJobs, setUploadJobs] = useState<UploadJob[]>([]);
  const pollTimers = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());

  const [showAdvanced, setShowAdvanced] = useState(false);
  const [chunkSize, setChunkSize] = useState<string>("");
  const [overlapSize, setOverlapSize] = useState<string>("");

  // Delete
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const deleteTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const activeKB = kbConfigs.find((k) => k.index_id === activeKBId) || null;

  // Sync RAG config to backend whenever kbConfigs changes
  const syncRagConfig = useCallback((configs: KBConfig[]) => {
    setKBRagConfig(configs).catch(() => { /* ignore */ });
  }, []);

  // Load documents for active KB
  const loadDocuments = useCallback(async (p = 1) => {
    if (!activeKBId) {
      setDocuments([]);
      setTotalCount(0);
      return;
    }
    setLoading(true);
    try {
      const data = await listKBDocuments(p, 20, activeKBId);
      setDocuments(data.documents);
      setTotalCount(data.total_count);
      setPage(p);
    } catch {
      setDocuments([]);
      setTotalCount(0);
    }
    setLoading(false);
  }, [activeKBId]);

  useEffect(() => {
    if (open) {
      const configs = loadKBConfigs();
      setKBConfigs(configs);
      const active = loadActiveKBId();
      setActiveKBId(active);
      setUploadJobs([]);
      setConfirmDeleteId(null);
      setShowAddKB(false);
      setShowKBDropdown(false);
      syncRagConfig(configs);
    }
    return () => {
      pollTimers.current.forEach((t) => clearInterval(t));
      pollTimers.current.clear();
    };
  }, [open, syncRagConfig]);

  // Reload documents when activeKBId changes
  useEffect(() => {
    if (open && activeKBId) {
      loadDocuments(1);
    } else {
      setDocuments([]);
      setTotalCount(0);
    }
  }, [open, activeKBId, loadDocuments]);

  // Add KB
  function handleAddKB() {
    const id = newKBId.trim();
    const name = newKBName.trim() || id;
    if (!id) return;
    if (kbConfigs.some((k) => k.index_id === id)) {
      setShowAddKB(false);
      setActiveKBId(id);
      saveActiveKBId(id);
      return;
    }
    const newConfig: KBConfig = { index_id: id, name, description: newKBDesc.trim() };
    const updated = [...kbConfigs, newConfig];
    setKBConfigs(updated);
    saveKBConfigs(updated);
    setActiveKBId(id);
    saveActiveKBId(id);
    syncRagConfig(updated);
    setShowAddKB(false);
    setNewKBId("");
    setNewKBName("");
    setNewKBDesc("");
  }

  // Remove KB
  function handleRemoveKB(indexId: string) {
    const updated = kbConfigs.filter((k) => k.index_id !== indexId);
    setKBConfigs(updated);
    saveKBConfigs(updated);
    if (activeKBId === indexId) {
      const next = updated[0]?.index_id || "";
      setActiveKBId(next);
      saveActiveKBId(next);
    }
    syncRagConfig(updated);
  }

  // Switch KB
  function handleSwitchKB(indexId: string) {
    setActiveKBId(indexId);
    saveActiveKBId(indexId);
    setShowKBDropdown(false);
    setPage(1);
  }

  // Upload
  async function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const fileList = Array.from(files);
    e.target.value = "";

    if (!activeKBId) return;

    for (const file of fileList) {
      try {
        const cs = chunkSize ? parseInt(chunkSize) : undefined;
        const os = overlapSize ? parseInt(overlapSize) : undefined;
        const resp = await uploadToKB(file, activeKBId, cs, os);

        const job: UploadJob = {
          jobId: resp.job_id,
          filename: resp.filename,
          status: resp.status,
          progress: "正在上传...",
          error: null,
        };
        setUploadJobs((prev) => [...prev, job]);

        const timer = setInterval(async () => {
          try {
            const st = await getKBUploadStatus(resp.job_id);
            setUploadJobs((prev) =>
              prev.map((j) =>
                j.jobId === resp.job_id
                  ? { ...j, status: st.status, progress: st.progress, error: st.error }
                  : j
              )
            );
            if (st.status === "completed" || st.status === "failed") {
              clearInterval(timer);
              pollTimers.current.delete(resp.job_id);
              if (st.status === "completed") {
                loadDocuments(page);
              }
            }
          } catch {
            // poll error, keep retrying
          }
        }, 3000);
        pollTimers.current.set(resp.job_id, timer);
      } catch {
        setUploadJobs((prev) => [
          ...prev,
          { jobId: crypto.randomUUID(), filename: file.name, status: "failed", progress: "", error: "上传请求失败" },
        ]);
      }
    }
  }

  // Delete document
  function startDelete(docId: string) {
    setConfirmDeleteId(docId);
    if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current);
    deleteTimerRef.current = setTimeout(() => setConfirmDeleteId(null), 3000);
  }

  async function handleDelete(docId: string) {
    setConfirmDeleteId(null);
    try {
      await deleteKBDocuments([docId], activeKBId);
      loadDocuments(page);
    } catch {
      // silent
    }
  }

  if (!open) return null;

  const hasMore = totalCount > page * 20;

  return (
    <div className="fixed inset-0 z-50 flex animate-fade-in">
      <div className="flex-1 bg-black/5 backdrop-blur-[2px]" onClick={onClose} />

      <div className="w-[720px] max-w-[90vw] bg-sand-50 border-l border-sand-200/60 flex flex-col
                      shadow-[-8px_0_24px_rgba(0,0,0,0.06)] animate-slide-right">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3.5 border-b border-sand-200/60">
          <span className="text-[0.8125rem] font-semibold text-sand-700">
            知识库管理
          </span>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-sand-400 hover:text-sand-600 hover:bg-sand-200/50 transition-colors"
          >
            <X size={15} />
          </button>
        </div>

        {/* KB Selector */}
        <div className="px-4 py-2.5 border-b border-sand-200/40 bg-sand-100/30">
          <div className="relative">
            <button
              onClick={() => setShowKBDropdown(!showKBDropdown)}
              className="flex items-center gap-2 w-full px-3 py-2 rounded-lg border border-sand-200/60
                         bg-white text-[0.8125rem] text-sand-700 hover:border-sand-300/80 transition-colors"
            >
              <Database size={14} className="text-sand-400 shrink-0" />
              {activeKB ? (
                <span className="truncate flex-1 text-left">
                  {activeKB.name}
                  <span className="text-sand-400 ml-1.5 text-2xs">{activeKB.index_id}</span>
                </span>
              ) : (
                <span className="text-sand-400 flex-1 text-left">选择知识库...</span>
              )}
              <ChevronDown size={14} className="text-sand-400 shrink-0" />
            </button>

            {showKBDropdown && (
              <div className="absolute top-full left-0 right-0 mt-1 z-10 bg-white rounded-xl border border-sand-200/60
                              shadow-[0_4px_16px_rgba(0,0,0,0.08)] py-1 max-h-64 overflow-y-auto">
                {kbConfigs.map((kb) => (
                  <div
                    key={kb.index_id}
                    className={`flex items-center gap-2 px-3 py-2 text-[0.8125rem] cursor-pointer
                                transition-colors group
                                ${kb.index_id === activeKBId ? "bg-sand-100 text-sand-800" : "text-sand-600 hover:bg-sand-50"}`}
                    onClick={() => handleSwitchKB(kb.index_id)}
                  >
                    <span className="flex-1 min-w-0">
                      <span className="truncate block">{kb.name}</span>
                      <span className="text-2xs text-sand-400 block truncate">{kb.index_id}</span>
                      {kb.description && (
                        <span className="text-2xs text-sand-400 block truncate">{kb.description}</span>
                      )}
                    </span>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleRemoveKB(kb.index_id); }}
                      className="p-1 rounded text-sand-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all shrink-0"
                      title="移除"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                ))}
                {kbConfigs.length > 0 && <div className="border-t border-sand-200/40 my-1" />}
                <button
                  onClick={() => { setShowAddKB(true); setShowKBDropdown(false); }}
                  className="flex items-center gap-2 w-full px-3 py-2 text-[0.8125rem]
                             text-sand-500 hover:bg-sand-50 transition-colors"
                >
                  <Plus size={14} />
                  添加知识库
                </button>
              </div>
            )}
          </div>

          {/* Add KB form */}
          {showAddKB && (
            <div className="mt-2 p-3 rounded-lg border border-sand-200/60 bg-white space-y-2">
              <input
                placeholder="知识库 ID（必填）"
                value={newKBId}
                onChange={(e) => setNewKBId(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded border border-sand-200/60 text-xs bg-sand-50
                           focus:outline-none focus:ring-1 focus:ring-sand-300/60"
                autoFocus
              />
              <input
                placeholder="名称（选填，默认用 ID）"
                value={newKBName}
                onChange={(e) => setNewKBName(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded border border-sand-200/60 text-xs bg-sand-50
                           focus:outline-none focus:ring-1 focus:ring-sand-300/60"
              />
              <input
                placeholder="描述（选填）"
                value={newKBDesc}
                onChange={(e) => setNewKBDesc(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded border border-sand-200/60 text-xs bg-sand-50
                           focus:outline-none focus:ring-1 focus:ring-sand-300/60"
              />
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => setShowAddKB(false)}
                  className="px-3 py-1.5 rounded-lg text-xs text-sand-500 hover:text-sand-700 transition-colors"
                >
                  取消
                </button>
                <button
                  onClick={handleAddKB}
                  disabled={!newKBId.trim()}
                  className="px-3 py-1.5 rounded-lg text-xs bg-sand-800 text-white hover:bg-sand-900
                             disabled:bg-sand-300 disabled:cursor-default transition-colors"
                >
                  添加
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Toolbar */}
        {activeKB && (
          <div className="px-4 py-3 border-b border-sand-200/40 flex items-center gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPT_TYPES}
              multiple
              className="hidden"
              onChange={handleFileSelect}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs
                         bg-sand-800 text-white hover:bg-sand-900 transition-colors"
            >
              <Upload size={13} />
              上传文件
            </button>
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs
                         text-sand-500 hover:text-sand-700 hover:bg-sand-200/50 transition-colors"
            >
              <Settings2 size={13} />
              高级设置
              {showAdvanced ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            </button>
            <div className="ml-auto text-2xs text-sand-400">
              共 {totalCount} 个文件
            </div>
          </div>
        )}

        {/* Advanced settings */}
        {activeKB && showAdvanced && (
          <div className="px-4 py-2.5 border-b border-sand-200/40 flex items-center gap-4 bg-sand-100/50">
            <label className="flex items-center gap-1.5 text-xs text-sand-600">
              分块大小
              <input
                type="number"
                placeholder="默认"
                value={chunkSize}
                onChange={(e) => setChunkSize(e.target.value)}
                className="w-20 px-2 py-1 rounded border border-sand-200/60 text-xs bg-white
                           focus:outline-none focus:ring-1 focus:ring-sand-300/60"
              />
            </label>
            <label className="flex items-center gap-1.5 text-xs text-sand-600">
              重叠大小
              <input
                type="number"
                placeholder="默认"
                value={overlapSize}
                onChange={(e) => setOverlapSize(e.target.value)}
                className="w-20 px-2 py-1 rounded border border-sand-200/60 text-xs bg-white
                           focus:outline-none focus:ring-1 focus:ring-sand-300/60"
              />
            </label>
          </div>
        )}

        {/* Upload progress */}
        {uploadJobs.length > 0 && (
          <div className="px-4 py-2.5 border-b border-sand-200/40 space-y-1.5">
            {uploadJobs.map((job) => (
              <div key={job.jobId} className="flex items-center gap-2 text-xs py-1">
                {job.status === "failed" ? (
                  <XCircle size={13} className="text-red-500 shrink-0" />
                ) : job.status === "completed" ? (
                  <CheckCircle2 size={13} className="text-green-500 shrink-0" />
                ) : (
                  <Loader2 size={13} className="text-amber-500 animate-spin shrink-0" />
                )}
                <span className="truncate text-sand-700 min-w-0 flex-1">{job.filename}</span>
                <span className={`shrink-0 ${
                  job.status === "failed" ? "text-red-500" :
                  job.status === "completed" ? "text-green-600" : "text-amber-600"
                }`}>
                  {job.error || job.progress}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Document list */}
        <div className="flex-1 overflow-y-auto">
          {!activeKB ? (
            <div className="flex flex-col items-center justify-center h-48 text-sand-400">
              <Database size={24} className="mb-2 opacity-40" />
              <span className="text-sm">请先添加并选择一个知识库</span>
            </div>
          ) : loading ? (
            <div className="flex items-center justify-center h-48 text-sand-400">
              <Loader2 size={18} className="animate-spin mr-2" />
              加载中
            </div>
          ) : documents.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-sand-400">
              <FileText size={24} className="mb-2 opacity-40" />
              <span className="text-sm">该知识库暂无文件</span>
              <span className="text-2xs mt-1">点击上方按钮上传文件</span>
            </div>
          ) : (
            <div>
              <div className="flex items-center px-4 py-2 text-2xs font-medium text-sand-500 uppercase tracking-wider
                              border-b border-sand-200/40 bg-sand-100/30 sticky top-0">
                <span className="flex-1 min-w-0">文件名</span>
                <span className="w-20 text-right">大小</span>
                <span className="w-16 text-center">状态</span>
                <span className="w-16 text-right">操作</span>
              </div>
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center px-4 py-2.5 hover:bg-white/60 transition-colors
                             border-b border-sand-200/20 group"
                >
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <FileText size={14} className="text-sand-400 shrink-0" />
                    <span className="truncate text-[0.8125rem] text-sand-700">{doc.name}</span>
                  </div>
                  <span className="w-20 text-right text-2xs text-sand-400">{formatSize(doc.size)}</span>
                  <span className="w-16 flex justify-center"><StatusBadge status={doc.status} /></span>
                  <span className="w-16 flex justify-end">
                    {confirmDeleteId === doc.id ? (
                      <button
                        onClick={() => handleDelete(doc.id)}
                        className="text-2xs text-red-600 hover:text-red-700 transition-colors"
                      >
                        确认?
                      </button>
                    ) : (
                      <button
                        onClick={() => startDelete(doc.id)}
                        className="p-1 rounded text-sand-300 hover:text-red-500
                                   opacity-0 group-hover:opacity-100 transition-all"
                        title="删除"
                      >
                        <Trash2 size={13} />
                      </button>
                    )}
                  </span>
                </div>
              ))}
              <div className="flex items-center justify-center gap-3 py-3">
                {page > 1 && (
                  <button
                    onClick={() => loadDocuments(page - 1)}
                    className="text-xs text-sand-500 hover:text-sand-700 transition-colors"
                  >
                    上一页
                  </button>
                )}
                <span className="text-2xs text-sand-400">第 {page} 页</span>
                {hasMore && (
                  <button
                    onClick={() => loadDocuments(page + 1)}
                    className="text-xs text-sand-500 hover:text-sand-700 transition-colors"
                  >
                    下一页
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
