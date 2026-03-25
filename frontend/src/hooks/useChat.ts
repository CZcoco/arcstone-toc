import { useState, useCallback, useRef } from "react";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { BASE_URL, cancelChat } from "@/lib/api";
import type { Message, Segment, ToolCall, AttachmentMeta } from "@/types";

let msgIdCounter = 0;
function nextId() {
  return `msg-${++msgIdCounter}-${Date.now()}`;
}

export function useChat(threadId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const currentAiIdRef = useRef<string | null>(null);

  // 从历史消息构建 segments（历史中 assistant → tool 交替出现）
  const loadHistory = useCallback(
    (history: Array<{ role: string; content: string; tool_calls?: any[]; name?: string; tool_call_id?: string; attachments?: AttachmentMeta[] }>) => {
      const msgs: Message[] = [];
      let pendingSegments: Segment[] = [];
      let pendingToolCalls: Map<string, ToolCall> = new Map();
      let currentAiMsgId: string | null = null;

      function flushAssistant() {
        if (currentAiMsgId && pendingSegments.length > 0) {
          const fullText = pendingSegments
            .filter((s) => s.type === "text")
            .map((s) => (s as any).content)
            .join("");
          msgs.push({
            id: currentAiMsgId,
            role: "assistant",
            content: fullText,
            segments: [...pendingSegments],
          });
        }
        pendingSegments = [];
        pendingToolCalls = new Map();
        currentAiMsgId = null;
      }

      for (const raw of history) {
        if (raw.role === "user") {
          flushAssistant();
          const userMsg: Message = { id: nextId(), role: "user", content: raw.content };
          if (raw.attachments?.length) userMsg.attachments = raw.attachments;
          msgs.push(userMsg);
        } else if (raw.role === "assistant") {
          if (!currentAiMsgId) currentAiMsgId = nextId();

          if (raw.content) {
            pendingSegments.push({ type: "text", content: raw.content });
          }

          if (raw.tool_calls && raw.tool_calls.length > 0) {
            for (const tc of raw.tool_calls) {
              const toolCall: ToolCall = {
                id: tc.id,
                name: tc.name,
                args: tc.args,
                status: "done",
              };
              pendingToolCalls.set(tc.id, toolCall);
              pendingSegments.push({ type: "tool_call", toolCall });
            }
          } else if (!raw.tool_calls || raw.tool_calls.length === 0) {
            flushAssistant();
          }
        } else if (raw.role === "tool") {
          const tc = pendingToolCalls.get(raw.tool_call_id || "");
          if (tc) {
            tc.result = raw.content;
            tc.status = "done";
          }
        }
      }
      flushAssistant();
      setMessages(msgs);
    },
    []
  );

  function updateAiMessage(aiId: string, patch: Partial<Message>) {
    setMessages((prev) =>
      prev.map((m) => (m.id === aiId ? { ...m, ...patch } : m))
    );
  }

  /**
   * 内部 SSE 流式处理：连接指定 URL，追加 AI 消息并流式更新
   * @param url - 后端 SSE 端点
   * @param body - POST body
   * @param priorMessages - 在 AI 消息之前的消息列表
   */
  function streamResponse(
    url: string,
    body: Record<string, unknown>,
    priorMessages: Message[],
  ) {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    if (currentAiIdRef.current) {
      const prevId = currentAiIdRef.current;
      setMessages((prev) =>
        prev.map((m) => (m.id === prevId && m.isStreaming ? { ...m, isStreaming: false } : m))
      );
    }

    const aiId = nextId();
    const aiMsg: Message = { id: aiId, role: "assistant", content: "", segments: [], isStreaming: true };
    currentAiIdRef.current = aiId;

    setMessages([...priorMessages, aiMsg]);
    setIsStreaming(true);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    const segments: Segment[] = [];
    const toolCallMap = new Map<string, ToolCall>();
    let textAccumulating = false;

    let rafId: number | null = null;
    function syncToUI() {
      if (rafId !== null) return;
      rafId = requestAnimationFrame(() => {
        rafId = null;
        const fullText = segments
          .filter((s) => s.type === "text")
          .map((s) => (s as any).content)
          .join("");
        updateAiMessage(aiId, { content: fullText, segments: [...segments] });
      });
    }
    function flushUI() {
      if (rafId !== null) {
        cancelAnimationFrame(rafId);
        rafId = null;
      }
      const fullText = segments
        .filter((s) => s.type === "text")
        .map((s) => (s as any).content)
        .join("");
      updateAiMessage(aiId, { content: fullText, segments: [...segments] });
    }

    /** 流式中断时，把所有还在 running 的工具调用标记为中断 */
    function markToolCallsAborted() {
      for (const tc of toolCallMap.values()) {
        if (tc.status === "running") {
          tc.status = "done";
          tc.result = tc.result || "(已中断)";
        }
      }
    }

    (async () => {
      try {
        await fetchEventSource(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: ctrl.signal,

          onmessage(ev) {
            let data: any;
            try {
              data = JSON.parse(ev.data);
            } catch {
              return;
            }

            switch (ev.event) {
              case "text_chunk": {
                if (textAccumulating && segments.length > 0) {
                  const last = segments[segments.length - 1];
                  if (last.type === "text") {
                    last.content += data.content;
                  }
                } else {
                  segments.push({ type: "text", content: data.content });
                  textAccumulating = true;
                }
                syncToUI();
                break;
              }
              case "tool_call": {
                textAccumulating = false;
                const tc: ToolCall = {
                  id: data.id,
                  name: data.name,
                  args: data.args,
                  status: "running",
                };
                toolCallMap.set(data.id, tc);
                segments.push({ type: "tool_call", toolCall: tc });
                syncToUI();
                break;
              }
              case "tool_result": {
                const tc = toolCallMap.get(data.id);
                if (tc) {
                  tc.result = data.content;
                  tc.status = "done";
                }
                syncToUI();
                break;
              }
              case "thinking":
                textAccumulating = false;
                break;
              case "done": {
                flushUI();
                const fullText = segments
                  .filter((s) => s.type === "text")
                  .map((s) => (s as any).content)
                  .join("");
                updateAiMessage(aiId, {
                  content: fullText,
                  segments: [...segments],
                  isStreaming: false,
                });
                setIsStreaming(false);
                currentAiIdRef.current = null;
                abortRef.current = null;
                break;
              }
              case "error": {
                markToolCallsAborted();
                const fullText = segments
                  .filter((s) => s.type === "text")
                  .map((s) => (s as any).content)
                  .join("");
                updateAiMessage(aiId, {
                  content: fullText || `错误: ${data.message}`,
                  segments: [...segments],
                  isStreaming: false,
                });
                setIsStreaming(false);
                currentAiIdRef.current = null;
                abortRef.current = null;
                break;
              }
            }
          },

          onclose() {
            if (currentAiIdRef.current === aiId) {
              markToolCallsAborted();
              flushUI();
              updateAiMessage(aiId, { isStreaming: false });
              setIsStreaming(false);
              currentAiIdRef.current = null;
              abortRef.current = null;
            }
          },

          onerror(err) {
            markToolCallsAborted();
            flushUI();
            const patch: Partial<Message> = { isStreaming: false };
            if (segments.length === 0) patch.content = "连接中断";
            updateAiMessage(aiId, patch);
            setIsStreaming(false);
            currentAiIdRef.current = null;
            abortRef.current = null;
            throw err;
          },

          openWhenHidden: true,
        });
      } catch (e: any) {
        markToolCallsAborted();
        if (e.name === "AbortError") {
          flushUI();
          updateAiMessage(aiId, { isStreaming: false });
        } else if (currentAiIdRef.current === aiId) {
          const patch: Partial<Message> = { isStreaming: false };
          if (segments.length === 0) patch.content = "连接失败，请检查后端服务是否启动。";
          updateAiMessage(aiId, patch);
        }
        setIsStreaming(false);
        currentAiIdRef.current = null;
        abortRef.current = null;
      }
    })();
  }

  const sendMessage = useCallback(
    (content: string, model?: string, imageIds?: string[], fileSummaries?: string[], attachments?: AttachmentMeta[]) => {
      const userMsg: Message = { id: nextId(), role: "user", content };
      if (attachments?.length) userMsg.attachments = attachments;
      const priorMessages = [...messages, userMsg];

      streamResponse(
        `${BASE_URL}/chat/stream`,
        {
          message: content,
          thread_id: threadId,
          model: model || "claude-sonnet",
          image_ids: imageIds || [],
          file_summaries: fileSummaries || [],
          attachments: attachments || [],
        },
        priorMessages,
      );
    },
    [threadId, messages]
  );

  const resendMessage = useCallback(
    (messageId: string, newContent: string, model?: string) => {
      // 找到被编辑的消息在 messages 中的位置
      const msgIndex = messages.findIndex((m) => m.id === messageId);
      if (msgIndex === -1) return;

      // 计算这是第几条用户消息（0-based）
      let userMsgIndex = 0;
      for (let i = 0; i < msgIndex; i++) {
        if (messages[i].role === "user") userMsgIndex++;
      }

      // 截断到该消息之前，添加编辑后的新用户消息
      const truncated = messages.slice(0, msgIndex);
      const newUserMsg: Message = { id: nextId(), role: "user", content: newContent };
      const priorMessages = [...truncated, newUserMsg];

      streamResponse(
        `${BASE_URL}/chat/resend`,
        { message: newContent, thread_id: threadId, message_index: userMsgIndex, model: model || "deepseek" },
        priorMessages,
      );
    },
    [threadId, messages]
  );

  const stopStreaming = useCallback(() => {
    cancelChat(threadId).catch(() => {});
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    if (currentAiIdRef.current) {
      const id = currentAiIdRef.current;
      setMessages((prev) =>
        prev.map((m) => (m.id === id ? { ...m, isStreaming: false } : m))
      );
      currentAiIdRef.current = null;
    }
    setIsStreaming(false);
  }, [threadId]);

  const clearMessages = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    currentAiIdRef.current = null;
    setIsStreaming(false);
    setMessages([]);
  }, []);

  const addMessage = useCallback((msg: Message) => {
    setMessages(prev => [...prev, msg]);
  }, []);

  return { messages, isStreaming, sendMessage, resendMessage, stopStreaming, loadHistory, clearMessages, addMessage };
}
