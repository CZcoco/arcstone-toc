import { memo, useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { Pencil, Check, X, FileSpreadsheet, FileText, Image, FileCode } from "lucide-react";
import type { Message } from "@/types";
import ToolCallCard from "./ToolCallCard";
import ThinkingIndicator from "./ThinkingIndicator";

interface ChatMessageProps {
  message: Message;
  onResend?: (messageId: string, newContent: string) => void;
  isStreaming?: boolean;
}

function ChatMessage({ message, onResend, isStreaming: globalStreaming }: ChatMessageProps) {
  const isUser = message.role === "user";
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (editing && textareaRef.current) {
      textareaRef.current.focus();
      // 光标移到末尾
      const len = textareaRef.current.value.length;
      textareaRef.current.setSelectionRange(len, len);
      // 自适应高度
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 240) + "px";
    }
  }, [editing]);

  function startEdit() {
    setEditValue(message.content);
    setEditing(true);
  }

  function cancelEdit() {
    setEditing(false);
    setEditValue("");
  }

  function submitEdit() {
    const trimmed = editValue.trim();
    if (!trimmed || !onResend) return;
    setEditing(false);
    setEditValue("");
    onResend(message.id, trimmed);
  }

  function handleTextareaChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setEditValue(e.target.value);
    // 自适应高度
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 240) + "px";
  }

  const fileAttachments = message.attachments?.length ? message.attachments : [];

  if (isUser) {
    return (
      <div className="mb-6 animate-slide-up group">
        <div className="flex justify-end items-start gap-1.5">
          {/* 编辑按钮 — hover 时显示 */}
          {!editing && onResend && !globalStreaming && (
            <button
              onClick={startEdit}
              className="mt-2.5 p-1.5 rounded-lg text-sand-300 opacity-0 group-hover:opacity-100
                         hover:text-sand-600 hover:bg-sand-200/50
                         transition-all duration-150 shrink-0"
              title="编辑并重发"
            >
              <Pencil size={13} />
            </button>
          )}

          {editing ? (
            <div className="max-w-[85%] w-full flex flex-col gap-2">
              <textarea
                ref={textareaRef}
                className="w-full bg-white rounded-2xl rounded-br-md px-4 py-3
                           shadow-[0_1px_3px_rgba(0,0,0,0.04)] text-[0.9375rem] leading-relaxed
                           text-sand-900 resize-none
                           focus:outline-none focus:shadow-[0_2px_12px_rgba(0,0,0,0.08),0_0_0_1px_rgba(200,149,108,0.3)]
                           min-h-[52px] max-h-[240px] transition-shadow duration-200"
                value={editValue}
                onChange={handleTextareaChange}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    submitEdit();
                  }
                  if (e.key === "Escape") cancelEdit();
                }}
              />
              <div className="flex justify-end gap-1.5">
                <button
                  onClick={cancelEdit}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs
                             text-sand-500 hover:text-sand-700 hover:bg-sand-200/50
                             transition-colors"
                >
                  <X size={12} />
                  取消
                </button>
                <button
                  onClick={submitEdit}
                  disabled={!editValue.trim()}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs
                             bg-sand-800 text-white hover:bg-sand-900
                             disabled:opacity-40 disabled:cursor-default
                             transition-colors"
                >
                  <Check size={12} />
                  发送
                </button>
              </div>
            </div>
          ) : (
            <div className="max-w-[85%] flex flex-col items-end gap-1.5">
              {/* 文件附件卡片 */}
              {fileAttachments.length > 0 && (
                <div className="flex flex-wrap justify-end gap-1.5">
                  {fileAttachments.map((att, i) => (
                    <div key={i} className="flex items-center gap-2 bg-white rounded-xl px-3 py-2
                                            shadow-[0_1px_3px_rgba(0,0,0,0.04)] border border-sand-100">
                      {att.type === "excel" ? (
                        <FileSpreadsheet size={16} className="text-emerald-600 shrink-0" />
                      ) : att.type === "image" ? (
                        <Image size={16} className="text-purple-500 shrink-0" />
                      ) : att.type === "md" ? (
                        <FileCode size={16} className="text-sand-500 shrink-0" />
                      ) : (
                        <FileText size={16} className="text-blue-500 shrink-0" />
                      )}
                      <span className="text-xs text-sand-600 max-w-[180px] truncate">{att.name}</span>
                    </div>
                  ))}
                </div>
              )}
              {/* 文本内容 */}
              <div className="bg-white rounded-2xl rounded-br-md px-4 py-3
                              shadow-[0_1px_3px_rgba(0,0,0,0.04)] text-[0.9375rem] leading-relaxed
                              text-sand-900 whitespace-pre-wrap break-words">
                {message.content}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  const segments = message.segments;
  const hasSegments = segments && segments.length > 0;

  // 是否有正在运行的工具调用（用于显示 thinking）
  const hasRunningTools = hasSegments && segments.some(
    (s) => s.type === "tool_call" && s.toolCall.status !== "done"
  );
  // 是否还没有任何文字内容
  const hasNoText = !hasSegments || !segments.some((s) => s.type === "text" && s.content);

  return (
    <div className="mb-6 animate-slide-up">
      {/* 按顺序渲染 segments */}
      {hasSegments && segments.map((seg, i) => {
        if (seg.type === "tool_call") {
          return <ToolCallCard key={seg.toolCall.id || i} toolCall={seg.toolCall} />;
        }
        if (seg.type === "text" && seg.content) {
          return (
            <div key={`text-${i}`} className="prose">
              <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
                {seg.content}
              </ReactMarkdown>
            </div>
          );
        }
        return null;
      })}

      {/* 没有 segments 但有 content（fallback，兼容老数据） */}
      {!hasSegments && message.content && (
        <div className="prose">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        </div>
      )}

      {/* Thinking indicator：流式中、有运行中的工具、还没开始出文字 */}
      {message.isStreaming && hasRunningTools && hasNoText && <ThinkingIndicator />}

      {/* Streaming cursor */}
      {message.isStreaming && (
        <span className="inline-block w-[3px] h-[18px] bg-accent rounded-full animate-pulse-soft ml-0.5 align-text-bottom translate-y-[2px]" />
      )}
    </div>
  );
}

export default memo(ChatMessage);
