// --- SSE 事件类型 ---

export interface TextChunkEvent {
  type: "text_chunk";
  content: string;
}

export interface ToolCallEvent {
  type: "tool_call";
  id: string;
  name: string;
  args: Record<string, unknown>;
}

export interface ToolResultEvent {
  type: "tool_result";
  id: string;
  name: string;
  content: string;
}

export interface ThinkingEvent {
  type: "thinking";
}

export interface DoneEvent {
  type: "done";
}

export interface ErrorEvent {
  type: "error";
  message: string;
}

export type SSEEvent =
  | TextChunkEvent
  | ToolCallEvent
  | ToolResultEvent
  | ThinkingEvent
  | DoneEvent
  | ErrorEvent;

// --- 消息内容段 ---

export interface TextSegment {
  type: "text";
  content: string;
}

export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
  result?: string;
  status: "pending" | "running" | "done";
}

export interface ToolCallSegment {
  type: "tool_call";
  toolCall: ToolCall;
}

export type Segment = TextSegment | ToolCallSegment;

// --- 附件元信息 ---

export interface AttachmentMeta {
  name: string;
  type: "pdf" | "doc" | "md" | "image" | "excel";
  path?: string;
}

// --- 消息模型 ---

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;           // 用户消息的纯文本，或 AI 消息的完整文本（用于历史加载）
  segments?: Segment[];      // AI 消息按到达顺序排列的内容段
  isStreaming?: boolean;
  attachments?: AttachmentMeta[];  // 用户消息的文件附件
}

// --- 会话 ---

export interface Session {
  thread_id: string;
  title: string;
  preview: string;
  workspace_path?: string;
}

// --- 记忆 ---

export interface MemoryItem {
  key: string;
  updated_at: string;
}
