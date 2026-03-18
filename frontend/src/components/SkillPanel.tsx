import { useState, useEffect, useRef } from "react";
import {
  X, Plus, Trash2, Save, Loader2, Wand2, FileText, FolderOpen,
  ChevronDown, ChevronRight, Pencil, XCircle, FilePlus, ExternalLink,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  listSkills, getSkill, updateSkill, deleteSkill,
  listSkillFiles, readSkillFile, writeSkillFile, deleteSkillFile,
  revealSkillsFolder,
} from "@/lib/api";
import type { SkillSummary, SkillFile } from "@/lib/api";

interface SkillPanelProps {
  open: boolean;
  onClose: () => void;
}

export default function SkillPanel({ open, onClose }: SkillPanelProps) {
  const [skills, setSkills] = useState<SkillSummary[]>([]);
  const [loading, setLoading] = useState(false);

  // 当前展开的 skill
  const [expandedSkill, setExpandedSkill] = useState<string | null>(null);
  const [skillFiles, setSkillFiles] = useState<SkillFile[]>([]);

  // 右侧：当前选中的文件
  const [selectedSkill, setSelectedSkill] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState("");
  const [fileLoading, setFileLoading] = useState(false);
  const [isBinary, setIsBinary] = useState(false);

  // 编辑模式
  const [mode, setMode] = useState<"view" | "edit">("view");
  const [editContent, setEditContent] = useState("");
  const [saving, setSaving] = useState(false);

  // 删除确认
  const [confirmDelete, setConfirmDelete] = useState<"skill" | "file" | null>(null);
  const deleteTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 新建 skill 对话框
  const [showNewSkill, setShowNewSkill] = useState(false);
  const [newSkillName, setNewSkillName] = useState("");
  const [newSkillDesc, setNewSkillDesc] = useState("");
  const [creating, setCreating] = useState(false);
  const newSkillInputRef = useRef<HTMLInputElement>(null);

  // 新建文件
  const [showNewFile, setShowNewFile] = useState(false);
  const [newFileName, setNewFileName] = useState("");
  const newFileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setExpandedSkill(null);
    setSelectedSkill(null);
    setSelectedFile(null);
    setMode("view");
    setConfirmDelete(null);
    setShowNewSkill(false);
    setShowNewFile(false);
    loadSkills();
  }, [open]);

  async function loadSkills() {
    setLoading(true);
    try {
      const { skills: list } = await listSkills();
      setSkills(list);
    } catch { /* */ }
    setLoading(false);
  }

  async function toggleSkill(dirName: string) {
    if (expandedSkill === dirName) {
      setExpandedSkill(null);
      setSkillFiles([]);
      return;
    }
    setExpandedSkill(dirName);
    try {
      const { files } = await listSkillFiles(dirName);
      setSkillFiles(files);
    } catch {
      setSkillFiles([]);
    }
  }

  async function selectFile(skillDir: string, filePath: string) {
    setSelectedSkill(skillDir);
    setSelectedFile(filePath);
    setMode("view");
    setConfirmDelete(null);
    setIsBinary(false);
    setFileLoading(true);
    try {
      const res = await readSkillFile(skillDir, filePath);
      setFileContent(res.content);
      setIsBinary(!!res.binary);
    } catch {
      setFileContent("加载失败");
    }
    setFileLoading(false);
  }

  function enterEdit() {
    setEditContent(fileContent);
    setMode("edit");
    setConfirmDelete(null);
  }

  function cancelEdit() {
    setMode("view");
  }

  async function handleSaveFile() {
    if (!selectedSkill || !selectedFile || editContent === fileContent) return;
    setSaving(true);
    try {
      await writeSkillFile(selectedSkill, selectedFile, editContent);
      setFileContent(editContent);
      setMode("view");
    } catch { /* */ }
    setSaving(false);
  }

  function startDelete(type: "skill" | "file") {
    setConfirmDelete(type);
    if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current);
    deleteTimerRef.current = setTimeout(() => setConfirmDelete(null), 3000);
  }

  function cancelDelete() {
    setConfirmDelete(null);
    if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current);
  }

  async function handleDeleteSkill() {
    if (!expandedSkill) return;
    try {
      await deleteSkill(expandedSkill);
      setSkills(prev => prev.filter(s => s.dir_name !== expandedSkill));
      if (selectedSkill === expandedSkill) {
        setSelectedSkill(null);
        setSelectedFile(null);
        setFileContent("");
      }
      setExpandedSkill(null);
      setSkillFiles([]);
      setConfirmDelete(null);
    } catch { /* */ }
  }

  async function handleDeleteFile() {
    if (!selectedSkill || !selectedFile) return;
    try {
      await deleteSkillFile(selectedSkill, selectedFile);
      setSkillFiles(prev => prev.filter(f => f.path !== selectedFile));
      setSelectedFile(null);
      setFileContent("");
      setMode("view");
      setConfirmDelete(null);
    } catch { /* */ }
  }

  async function handleCreateSkill() {
    const dirName = newSkillName.trim().toLowerCase().replace(/[^a-z0-9_-]/g, "-").replace(/-+/g, "-");
    if (!dirName) return;
    setCreating(true);
    try {
      await updateSkill(dirName, newSkillName.trim(), newSkillDesc.trim(), "");
      await loadSkills();
      setShowNewSkill(false);
      setNewSkillName("");
      setNewSkillDesc("");
      // 自动展开新建的 skill
      setExpandedSkill(dirName);
      const { files } = await listSkillFiles(dirName);
      setSkillFiles(files);
      // 自动选中 SKILL.md
      selectFile(dirName, "SKILL.md");
    } catch { /* */ }
    setCreating(false);
  }

  async function handleCreateFile() {
    if (!expandedSkill || !newFileName.trim()) return;
    const filePath = newFileName.trim();
    try {
      await writeSkillFile(expandedSkill, filePath, "");
      const { files } = await listSkillFiles(expandedSkill);
      setSkillFiles(files);
      setShowNewFile(false);
      setNewFileName("");
      selectFile(expandedSkill, filePath);
    } catch { /* */ }
  }

  if (!open) return null;

  const hasChanges = mode === "edit" && editContent !== fileContent;

  return (
    <div className="fixed inset-0 z-50 flex animate-fade-in">
      <div className="flex-1 bg-black/5 backdrop-blur-[2px]" onClick={onClose} />

      <div className="w-[720px] max-w-[90vw] bg-sand-50 border-l border-sand-200/60 flex flex-col
                      shadow-[-8px_0_24px_rgba(0,0,0,0.06)] animate-slide-right">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3.5 border-b border-sand-200/60">
          <span className="text-[0.8125rem] font-semibold text-sand-700">技能管理</span>
          <div className="flex items-center gap-1">
            <button onClick={() => revealSkillsFolder().catch(() => {})}
              className="p-1.5 rounded-lg text-sand-400 hover:text-sand-600 hover:bg-sand-200/50 transition-colors"
              title="在文件管理器中打开">
              <ExternalLink size={14} />
            </button>
            <button onClick={onClose}
              className="p-1.5 rounded-lg text-sand-400 hover:text-sand-600 hover:bg-sand-200/50 transition-colors">
              <X size={15} />
            </button>
          </div>
        </div>

        {/* Body — 双栏 */}
        <div className="flex-1 flex min-h-0">
          {/* 左侧目录 260px */}
          <div className="w-[260px] border-r border-sand-200/40 overflow-y-auto flex flex-col">
            {/* 新建按钮 */}
            <div className="px-3 pt-2.5 pb-1.5">
              <button onClick={() => { setShowNewSkill(true); setTimeout(() => newSkillInputRef.current?.focus(), 50); }}
                className="flex items-center gap-1.5 w-full px-2.5 py-1.5 rounded-lg text-xs
                           border border-sand-200/80 text-sand-600
                           hover:bg-white hover:border-sand-300/80 transition-all">
                <Plus size={13} strokeWidth={2} />
                新建技能
              </button>
            </div>

            {/* 新建 skill 表单 */}
            {showNewSkill && (
              <div className="mx-3 mb-2 p-2.5 rounded-lg bg-white border border-sand-200/60 space-y-2">
                <input ref={newSkillInputRef} value={newSkillName}
                  onChange={e => setNewSkillName(e.target.value)}
                  placeholder="技能名称（英文，如 pdf）"
                  className="w-full text-xs px-2 py-1.5 rounded border border-sand-200/60
                             focus:outline-none focus:ring-1 focus:ring-sand-300/60"
                  onKeyDown={e => { if (e.key === "Enter") handleCreateSkill(); if (e.key === "Escape") setShowNewSkill(false); }}
                />
                <input value={newSkillDesc} onChange={e => setNewSkillDesc(e.target.value)}
                  placeholder="描述（可选）"
                  className="w-full text-xs px-2 py-1.5 rounded border border-sand-200/60
                             focus:outline-none focus:ring-1 focus:ring-sand-300/60"
                  onKeyDown={e => { if (e.key === "Enter") handleCreateSkill(); if (e.key === "Escape") setShowNewSkill(false); }}
                />
                <div className="flex gap-1.5">
                  <button onClick={handleCreateSkill} disabled={creating || !newSkillName.trim()}
                    className="flex-1 text-xs py-1 rounded bg-sand-800 text-white hover:bg-sand-900
                               disabled:bg-sand-300 transition-colors">
                    {creating ? "创建中..." : "创建"}
                  </button>
                  <button onClick={() => setShowNewSkill(false)}
                    className="text-xs px-2 py-1 rounded text-sand-500 hover:bg-sand-100 transition-colors">
                    取消
                  </button>
                </div>
              </div>
            )}

            {/* Skill 列表 */}
            {loading ? (
              <div className="flex items-center justify-center py-12 text-sand-400">
                <Loader2 size={16} className="animate-spin mr-2" />
                <span className="text-xs">加载中</span>
              </div>
            ) : skills.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-sand-400">
                <Wand2 size={24} className="mb-2 opacity-40" />
                <span className="text-xs">暂无技能</span>
              </div>
            ) : (
              <div className="py-1 flex-1">
                {skills.map(s => {
                  const isExpanded = expandedSkill === s.dir_name;
                  return (
                    <div key={s.dir_name}>
                      {/* Skill 文件夹头 */}
                      <button onClick={() => toggleSkill(s.dir_name)}
                        className={`flex items-center gap-2 w-full px-3 py-2 text-left transition-colors
                                   text-[0.8125rem] group
                                   ${isExpanded ? "bg-white/60 text-sand-800" : "text-sand-600 hover:bg-white/40"}`}>
                        {isExpanded
                          ? <ChevronDown size={12} className="text-sand-400 shrink-0" />
                          : <ChevronRight size={12} className="text-sand-400 shrink-0" />}
                        <FolderOpen size={13} className="text-sand-400 shrink-0" />
                        <span className="truncate flex-1">{s.name}</span>
                      </button>

                      {/* 展开后的文件列表 */}
                      {isExpanded && (
                        <div>
                          {skillFiles.map(f => (
                            <button key={f.path}
                              onClick={() => selectFile(s.dir_name, f.path)}
                              className={`flex items-center gap-2 w-full pl-9 pr-3 py-1.5 text-left
                                         transition-colors text-[0.8125rem]
                                         ${selectedSkill === s.dir_name && selectedFile === f.path
                                           ? "bg-white text-sand-900 shadow-[0_1px_2px_rgba(0,0,0,0.04)]"
                                           : "text-sand-500 hover:bg-white/60 hover:text-sand-700"}`}>
                              <FileText size={12} className="shrink-0 opacity-50" />
                              <span className="truncate">{f.path}</span>
                              <span className="text-2xs text-sand-400 shrink-0 ml-auto">
                                {f.size > 1024 ? `${(f.size / 1024).toFixed(0)}K` : `${f.size}B`}
                              </span>
                            </button>
                          ))}
                          {/* 新建文件按钮 */}
                          {showNewFile ? (
                            <div className="pl-9 pr-3 py-1 flex items-center gap-1">
                              <input ref={newFileInputRef} value={newFileName}
                                onChange={e => setNewFileName(e.target.value)}
                                placeholder="文件名"
                                className="flex-1 text-xs px-1.5 py-1 rounded border border-sand-200/60
                                           focus:outline-none focus:ring-1 focus:ring-sand-300/60"
                                onKeyDown={e => { if (e.key === "Enter") handleCreateFile(); if (e.key === "Escape") { setShowNewFile(false); setNewFileName(""); } }}
                                autoFocus
                              />
                              <button onClick={handleCreateFile}
                                className="text-2xs px-1.5 py-0.5 rounded bg-sand-700 text-white hover:bg-sand-800">
                                确定
                              </button>
                            </div>
                          ) : (
                            <button onClick={() => { setShowNewFile(true); setNewFileName(""); setTimeout(() => newFileInputRef.current?.focus(), 50); }}
                              className="flex items-center gap-2 w-full pl-9 pr-3 py-1.5 text-left
                                         text-2xs text-sand-400 hover:text-sand-600 transition-colors">
                              <FilePlus size={11} />
                              新建文件
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* 右侧内容 */}
          <div className="flex-1 flex flex-col min-w-0">
            {selectedFile === null ? (
              <div className="flex-1 flex flex-col items-center justify-center text-sand-400">
                <Wand2 size={32} className="mb-3 opacity-30" />
                <span className="text-sm">选择一个技能文件查看</span>
                <span className="text-2xs mt-1 text-sand-300">技能映射到 Agent 的 /skills/ 虚拟路径</span>
              </div>
            ) : fileLoading ? (
              <div className="flex-1 flex items-center justify-center text-sand-400">
                <Loader2 size={18} className="animate-spin mr-2" />
                加载中
              </div>
            ) : (
              <>
                {/* 文件路径标题 */}
                <div className="px-4 py-2.5 border-b border-sand-200/40 flex items-center gap-1.5
                               text-[0.8125rem] font-medium text-sand-600 shrink-0">
                  <FileText size={13} className="opacity-50 shrink-0" />
                  <span className="truncate">/skills/{selectedSkill}/{selectedFile}</span>
                </div>

                {/* 内容区 */}
                <div className="flex-1 overflow-y-auto p-4">
                  {mode === "view" ? (
                    isBinary ? (
                      <p className="text-sand-400 text-sm">(二进制文件，无法预览)</p>
                    ) : selectedFile?.endsWith(".md") ? (
                      <div className="prose max-w-none">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {fileContent || "(空)"}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <pre className="text-[0.8125rem] text-sand-800 font-mono whitespace-pre-wrap leading-relaxed">
                        {fileContent || "(空)"}
                      </pre>
                    )
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
                    {confirmDelete === "file" ? (
                      <>
                        <button onClick={handleDeleteFile}
                          className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs
                                     bg-red-50 text-red-600 hover:bg-red-100 transition-colors">
                          <Trash2 size={12} /> 确认删除文件？
                        </button>
                        <button onClick={cancelDelete}
                          className="text-xs text-sand-400 hover:text-sand-600 transition-colors">取消</button>
                      </>
                    ) : confirmDelete === "skill" ? (
                      <>
                        <button onClick={handleDeleteSkill}
                          className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs
                                     bg-red-50 text-red-600 hover:bg-red-100 transition-colors">
                          <Trash2 size={12} /> 确认删除整个技能？
                        </button>
                        <button onClick={cancelDelete}
                          className="text-xs text-sand-400 hover:text-sand-600 transition-colors">取消</button>
                      </>
                    ) : (
                      <div className="flex items-center gap-1">
                        <button onClick={() => startDelete("file")}
                          className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs
                                     text-sand-400 hover:text-red-500 hover:bg-red-50/50 transition-colors">
                          <Trash2 size={12} /> 删除文件
                        </button>
                        {expandedSkill && (
                          <button onClick={() => startDelete("skill")}
                            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs
                                       text-sand-400 hover:text-red-500 hover:bg-red-50/50 transition-colors">
                            <Trash2 size={12} /> 删除技能
                          </button>
                        )}
                      </div>
                    )}
                  </div>

                  {/* 右侧：编辑/保存 */}
                  <div className="flex items-center gap-2">
                    {mode === "view" ? (
                      !isBinary && (
                        <button onClick={enterEdit}
                          className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs
                                     text-sand-600 bg-white border border-sand-200/60
                                     hover:bg-sand-100 transition-colors">
                          <Pencil size={12} /> 编辑
                        </button>
                      )
                    ) : (
                      <>
                        <button onClick={cancelEdit}
                          className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs
                                     text-sand-500 hover:text-sand-700 transition-colors">
                          <XCircle size={12} /> 取消
                        </button>
                        <button onClick={handleSaveFile}
                          disabled={!hasChanges || saving}
                          className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs transition-colors
                                     ${hasChanges
                                       ? "bg-sand-800 text-white hover:bg-sand-900"
                                       : "bg-sand-200 text-sand-400 cursor-default"}`}>
                          {saving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
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
