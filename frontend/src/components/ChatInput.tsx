import { useState, type KeyboardEvent, type ReactNode, useRef, useEffect } from "react";
import { ArrowUp, Square, Paperclip, Loader2, FileText, Image, X } from "lucide-react";

export interface Attachment {
  name: string;
  type: "pdf" | "doc" | "md" | "image" | "excel";
  pages?: number;
  path?: string;
  image_id?: string;
  summary?: string;
}

interface ChatInputProps {
  onSend: (message: string, attachments?: Attachment[]) => void;
  onStop: () => void;
  isStreaming: boolean;
  disabled?: boolean;
  modelSelector?: ReactNode;
  onUploadPdfs?: (files: File[]) => void;
  uploadingCount?: number;
  attachments?: Attachment[];
  onRemoveAttachment?: (index: number) => void;
}

const MAX_ATTACHMENTS = 100;
const MAX_UPLOAD_BATCH = 100;

export default function ChatInput({ onSend, onStop, isStreaming, disabled, modelSelector, onUploadPdfs, uploadingCount = 0, attachments = [], onRemoveAttachment }: ChatInputProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 180) + "px";
  }, [input]);

  // Focus on mount
  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  function handleSend() {
    const text = input.trim();
    if ((!text && attachments.length === 0) || disabled) return;
    onSend(text, attachments.length > 0 ? attachments : undefined);
    setInput("");
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (isStreaming) return;
      handleSend();
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0 || !onUploadPdfs) return;
    const remaining = Math.min(MAX_UPLOAD_BATCH, MAX_ATTACHMENTS - attachments.length);
    if (remaining <= 0) return;
    const selected = Array.from(fileList).slice(0, remaining);
    onUploadPdfs(selected);
    e.target.value = "";
  }

  const isUploading = uploadingCount > 0;
  const hasContent = input.trim().length > 0 || attachments.length > 0;
  const canAttachMore = attachments.length < MAX_ATTACHMENTS && !isUploading;

  return (
    <div className="px-6 pb-3 pt-1.5 shrink-0">
      <div className="max-w-3xl mx-auto">
        <div className="relative bg-white rounded-2xl shadow-[0_1px_6px_rgba(0,0,0,0.06),0_0_0_1px_rgba(0,0,0,0.03)]
                        transition-shadow duration-200 focus-within:shadow-[0_2px_12px_rgba(0,0,0,0.08),0_0_0_1px_rgba(200,149,108,0.3)]">
          {/* Attachment chips + uploading indicators */}
          {(attachments.length > 0 || isUploading) && (
            <div className="flex flex-wrap gap-1.5 px-3.5 pt-3 pb-0">
              {attachments.map((att, i) => (
                <div
                  key={i}
                  className="flex items-center gap-1.5 pl-2.5 pr-1.5 py-1 rounded-lg
                             bg-sand-100 border border-sand-200/60 text-[0.8125rem] text-sand-700
                             animate-fade-in"
                >
                  {att.type === "image" ? (
                    <Image size={13} className="text-sand-400 shrink-0" />
                  ) : (
                    <FileText size={13} className="text-sand-400 shrink-0" />
                  )}
                  <span className="truncate max-w-[200px]">{att.name}</span>
                  {att.pages != null && (
                    <span className="text-2xs text-sand-400">{att.pages}页</span>
                  )}
                  {onRemoveAttachment && (
                    <button
                      onClick={() => onRemoveAttachment(i)}
                      className="p-0.5 rounded text-sand-400 hover:text-sand-600 hover:bg-sand-200/50
                                 transition-colors shrink-0"
                    >
                      <X size={12} />
                    </button>
                  )}
                </div>
              ))}
              {isUploading && (
                <div className="flex items-center gap-1.5 pl-2.5 pr-2.5 py-1 rounded-lg
                               bg-sand-50 border border-sand-200/40 text-[0.8125rem] text-sand-500
                               animate-fade-in">
                  <Loader2 size={13} className="animate-spin shrink-0" />
                  <span>解析中 {uploadingCount} 个文件...</span>
                </div>
              )}
            </div>
          )}

          <textarea
            ref={textareaRef}
            className="w-full bg-transparent text-sand-900 placeholder-sand-400
                       resize-none px-4 pt-3 pb-1 rounded-2xl
                       focus:outline-none text-[0.9375rem] leading-relaxed
                       min-h-[44px] max-h-[180px]"
            placeholder="给 Arcstone-econ 发消息..."
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
          />

          {/* Bottom bar */}
          <div className="px-2.5 pb-2.5 pt-1 flex items-center justify-between">
            {/* Model selector + PDF upload (left) */}
            <div className="flex items-center gap-1.5">
              {modelSelector}
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.doc,.docx,.md,.xlsx,.xls,.jpg,.jpeg,.png,.webp"
                multiple
                className="hidden"
                onChange={handleFileChange}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={!canAttachMore}
                className={`flex items-center justify-center w-7 h-7 rounded-lg transition-colors
                  ${isUploading ? "text-sand-400" :
                    canAttachMore ? "text-sand-400 hover:text-sand-600 hover:bg-sand-200/50" :
                    "text-sand-300 cursor-default"}`}
                title={isUploading ? "上传中..." : `上传文件（PDF/Word/MD/图片/Excel，每次最多 ${MAX_UPLOAD_BATCH} 个）`}
              >
                {isUploading ? <Loader2 size={15} className="animate-spin" /> : <Paperclip size={15} />}
              </button>
            </div>

            {/* Send / Stop (right) */}
            <div className="flex items-center gap-2">
              {isStreaming ? (
                <button
                  onClick={onStop}
                  className="flex items-center justify-center w-8 h-8 rounded-lg
                             bg-sand-800 hover:bg-sand-900 transition-colors"
                  title="停止生成"
                >
                  <Square size={14} className="text-white" />
                </button>
              ) : (
                <button
                  onClick={handleSend}
                  disabled={!hasContent || disabled}
                  className={`flex items-center justify-center w-8 h-8 rounded-lg
                             transition-all duration-150
                             ${hasContent
                               ? "bg-sand-800 hover:bg-sand-900 text-white"
                               : "bg-sand-200 text-sand-400 cursor-default"
                             }`}
                  title="发送"
                >
                  <ArrowUp size={16} strokeWidth={2.5} />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
