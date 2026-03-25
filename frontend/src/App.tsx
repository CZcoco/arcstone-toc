import { useState, useEffect, useRef, useCallback, lazy, Suspense } from "react";
import { useChat } from "@/hooks/useChat";
import { useAuth } from "@/hooks/useAuth";
import { useTopup } from "@/hooks/useTopup";
import { createSession, getSessionHistory, setWorkspace, uploadPdfs, uploadImage, uploadExcel } from "@/lib/api";
import type { TemplateCard } from "@/lib/api";
import Sidebar from "@/components/Sidebar";
import ChatMessage from "@/components/ChatMessage";
import ChatInput from "@/components/ChatInput";
import type { Attachment } from "@/components/ChatInput";
import ModelSelector from "@/components/ModelSelector";
import WelcomeScreen from "@/components/WelcomeScreen";
import RightPanel from "@/components/RightPanel";
const AuthScreen = lazy(() => import("@/components/AuthScreen"));
const OnboardingModal = lazy(() => import("@/components/OnboardingModal"));

const STORAGE_KEY = "arcstone-econ-model";
const MAX_ATTACHMENTS = 100;

export default function App() {
  const { user, loading: authLoading, start, logout, refreshBalance } = useAuth();
  const { openTopup } = useTopup(refreshBalance);
  const [threadId, setThreadId] = useState(() => crypto.randomUUID());
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(() => {
    const saved = localStorage.getItem("econ-agent-right-panel-collapsed");
    return saved === "true"; // 默认展开
  });
  const [showOnboarding, setShowOnboarding] = useState(() => !localStorage.getItem("econ-agent-onboarding-done"));
  const [modelRefreshKey] = useState(0);
  const [model, setModel] = useState(() => localStorage.getItem(STORAGE_KEY) || "deepseek-chat");
  const { messages, isStreaming, sendMessage, resendMessage, stopStreaming, loadHistory, clearMessages } =
    useChat(threadId);
  const [modeTemplates, setModeTemplates] = useState<TemplateCard[] | undefined>();
  const [uploadingCount, setUploadingCount] = useState(0);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const userScrolledUpRef = useRef(false);

  const handleModeChange = useCallback((_modeId: string, templates?: TemplateCard[]) => {
    setModeTemplates(templates);
  }, []);

  // 持久化模型选择
  const handleModelChange = useCallback((m: string) => {
    setModel(m);
    if (m) {
      localStorage.setItem(STORAGE_KEY, m);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  // 检测用户是否主动上滚：距底部超过 80px 就认为用户在看历史
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    function onScroll() {
      const { scrollTop, scrollHeight, clientHeight } = el!;
      userScrolledUpRef.current = scrollHeight - scrollTop - clientHeight > 80;
    }
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  // 只在用户没有上滚时自动跟随底部（仅在流式结束时平滑滚动）
  useEffect(() => {
    if (userScrolledUpRef.current || !scrollRef.current) return;
    const el = scrollRef.current;
    // 流式中不强制滚动，让内容自然增长
    if (!isStreaming) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, [messages, isStreaming]);

  // 流式结束后刷新余额 + 工作区文件列表
  const prevStreamingRef = useRef(false);
  const [wsRefreshKey, setWsRefreshKey] = useState(0);
  useEffect(() => {
    if (prevStreamingRef.current && !isStreaming) {
      refreshBalance();
      setWsRefreshKey(k => k + 1);
    }
    prevStreamingRef.current = isStreaming;
  }, [isStreaming, refreshBalance]);

  // 用户发新消息时，重置滚动状态，强制回到底部
  const handleSend = useCallback(
    (content: string, msgAttachments?: Attachment[]) => {
      userScrolledUpRef.current = false;
      const atts = msgAttachments || [];

      // PDF/DOC/MD 已存入 memories，拼路径提示
      const pathLines = atts
        .filter(a => a.type !== "image" && a.type !== "excel")
        .map(a => `[上传文件] ${a.name}（${a.pages ?? "?"}页），已保存到 ${a.path ?? "/memories/documents/"}`);

      // Excel：告知磁盘路径，agent 用 run_python + pandas 读取
      const excelLines = atts
        .filter(a => a.type === "excel" && a.path)
        .map(a => `[上传Excel] ${a.name}，磁盘路径：${a.path}，可用 run_python + pandas 读取`);

      const fileSummaries = [...pathLines, ...excelLines];
      const imageIds = atts.filter(a => a.type === "image" && a.image_id).map(a => a.image_id!);

      // 构建附件元信息，用于持久化到 checkpoint（显示文件卡片）
      const attachmentMetas = atts.map(a => ({ name: a.name, type: a.type, path: a.path }));

      sendMessage(content, model, imageIds, fileSummaries, attachmentMetas);
      setAttachments([]);
    },
    [sendMessage, model, refreshBalance]
  );

  const handleResend = useCallback(
    (messageId: string, newContent: string) => {
      userScrolledUpRef.current = false;
      resendMessage(messageId, newContent, model);
    },
    [resendMessage, model]
  );

  const handleUploadPdfs = useCallback(async (files: File[]) => {
    const remaining = Math.min(MAX_ATTACHMENTS, MAX_ATTACHMENTS - attachments.length);
    const toUpload = files.slice(0, remaining);
    if (toUpload.length === 0) return;

    // 按类型分组
    const pdfFiles = toUpload.filter(f => /\.(pdf|doc|docx|md)$/i.test(f.name));
    const imageFiles = toUpload.filter(f => /\.(jpg|jpeg|png|webp)$/i.test(f.name));
    const excelFiles = toUpload.filter(f => /\.(xlsx|xls)$/i.test(f.name));

    setUploadingCount(toUpload.length);
    try {
      // PDF/DOC/MD → 现有批量上传端点
      if (pdfFiles.length > 0) {
        const { results } = await uploadPdfs(pdfFiles);
        for (const r of results) {
          if (r.ok) {
            const isMd = r.name?.toLowerCase().endsWith(".md");
            setAttachments(prev => [...prev, {
              name: r.name,
              type: isMd ? "md" : (r.name?.toLowerCase().endsWith(".pdf") ? "pdf" : "doc"),
              pages: r.pages,
              path: r.path,
            }]);
          }
        }
      }
      // 图片 → /upload/image
      for (const f of imageFiles) {
        const r = await uploadImage(f);
        if (r.ok && r.image_id) {
          setAttachments(prev => [...prev, { name: f.name, type: "image", image_id: r.image_id }]);
        }
      }
      // Excel → /upload/excel（保存到磁盘，返回路径）
      for (const f of excelFiles) {
        const r = await uploadExcel(f);
        if (r.ok && r.path) {
          setAttachments(prev => [...prev, { name: f.name, type: "excel", path: r.path }]);
        }
      }
    } catch {
      // 网络错误，静默处理
    }
    setUploadingCount(0);
  }, [attachments.length]);

  const handleRemoveAttachment = useCallback((index: number) => {
    setAttachments(prev => prev.filter((_, i) => i !== index));
  }, []);

  const handleNewSession = useCallback(async () => {
    try {
      const { thread_id } = await createSession();
      clearMessages();
      setThreadId(thread_id as ReturnType<typeof crypto.randomUUID>);
      setAttachments([]);
    } catch {
      clearMessages();
      setThreadId(crypto.randomUUID());
      setAttachments([]);
    }
  }, [clearMessages]);

  const handleSelectSession = useCallback(
    async (tid: string) => {
      if (tid === threadId) return;
      clearMessages();
      setThreadId(tid as ReturnType<typeof crypto.randomUUID>);
      setAttachments([]);
      try {
        const { messages: history, workspace_path } = await getSessionHistory(tid);
        loadHistory(history);
        // 如果该会话绑定了工作区，自动切换
        if (workspace_path) {
          setWorkspace(workspace_path, tid).catch(() => {});
        }
      } catch {
        // ignore
      }
    },
    [threadId, clearMessages, loadHistory]
  );

  const handleDeleteSession = useCallback(
    (tid: string) => {
      if (tid === threadId) {
        clearMessages();
        setThreadId(crypto.randomUUID());
      }
    },
    [threadId, clearMessages]
  );

  // Auth gate
  if (authLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-sand-100">
        <div className="text-sm text-sand-400">加载中...</div>
      </div>
    );
  }
  if (!user) {
    return (
      <Suspense fallback={null}>
        <AuthScreen onStart={start} />
      </Suspense>
    );
  }

  return (
    <div className="flex h-screen bg-sand-100">
      <Sidebar
        currentThreadId={threadId}
        onNewSession={handleNewSession}
        onSelectSession={handleSelectSession}
        onDeleteSession={handleDeleteSession}
        user={user}
        onLogout={logout}
        onTopup={openTopup}
        onRefreshBalance={refreshBalance}
        onModeChange={handleModeChange}
      />

      {/* Main chat area */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Messages */}
        <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto">
          {messages.length === 0 ? (
            <WelcomeScreen onSendMessage={(msg) => handleSend(msg)} username={user?.username} templates={modeTemplates} />
          ) : (
            <div className="w-full max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
              {messages.map((msg) => (
                <ChatMessage
                  key={msg.id}
                  message={msg}
                  onResend={handleResend}
                  isStreaming={isStreaming}
                />
              ))}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {/* Input area */}
        <ChatInput
          onSend={handleSend}
          onStop={stopStreaming}
          isStreaming={isStreaming}
          onUploadPdfs={handleUploadPdfs}
          uploadingCount={uploadingCount}
          attachments={attachments}
          onRemoveAttachment={handleRemoveAttachment}
          modelSelector={
            <ModelSelector
              key={modelRefreshKey}
              value={model}
              onChange={handleModelChange}
              disabled={isStreaming}
              refreshKey={modelRefreshKey}
            />
          }
        />
      </main>

      <RightPanel
        refreshKey={wsRefreshKey}
        collapsed={rightPanelCollapsed}
        onToggle={() => setRightPanelCollapsed(prev => {
          const next = !prev;
          localStorage.setItem("econ-agent-right-panel-collapsed", String(next));
          return next;
        })}
        threadId={threadId}
      />

      <Suspense>
        {showOnboarding && (
          <OnboardingModal
            open={showOnboarding}
            onClose={() => setShowOnboarding(false)}
          />
        )}
      </Suspense>
    </div>
  );
}
