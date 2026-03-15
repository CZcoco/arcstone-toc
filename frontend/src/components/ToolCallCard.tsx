import { useState } from "react";
import { ChevronDown, ChevronRight, Search, Globe, Calculator, Loader2 } from "lucide-react";
import type { ToolCall } from "@/types";

const TOOL_CONFIG: Record<string, { label: string; icon: typeof Search }> = {
  bailian_rag: { label: "知识库检索", icon: Search },
  web_search: { label: "网络搜索", icon: Globe },
  calculate_irr: { label: "财务计算", icon: Calculator },
};

interface ToolCallCardProps {
  toolCall: ToolCall;
}

export default function ToolCallCard({ toolCall }: ToolCallCardProps) {
  const [expanded, setExpanded] = useState(false);

  const config = TOOL_CONFIG[toolCall.name] || { label: toolCall.name, icon: Search };
  const Icon = config.icon;
  const isDone = toolCall.status === "done";

  return (
    <div className="rounded-xl border border-sand-200 bg-white/60 overflow-hidden animate-fade-in my-2">
      <button
        className="flex items-center gap-2.5 w-full px-3.5 py-2.5 text-left
                   hover:bg-sand-50/80 transition-colors group"
        onClick={() => setExpanded(!expanded)}
      >
        {/* Status dot */}
        {isDone ? (
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />
        ) : (
          <Loader2 size={12} className="text-accent shrink-0 animate-spin" />
        )}

        <Icon size={13} className="text-sand-500 shrink-0" />

        <span className="text-[0.8125rem] font-medium text-sand-700">
          {config.label}
        </span>

        <span className="text-2xs text-sand-400 ml-auto mr-1">
          {isDone ? "" : "执行中"}
        </span>

        {expanded ? (
          <ChevronDown size={13} className="text-sand-400 group-hover:text-sand-600 transition-colors" />
        ) : (
          <ChevronRight size={13} className="text-sand-400 group-hover:text-sand-600 transition-colors" />
        )}
      </button>

      {expanded && (
        <div className="border-t border-sand-200/80 px-3.5 py-3 space-y-3 animate-fade-in">
          <div>
            <div className="text-2xs font-medium text-sand-400 uppercase tracking-wider mb-1.5">
              参数
            </div>
            <pre className="text-xs text-sand-700 whitespace-pre-wrap break-all bg-sand-50 rounded-lg p-2.5 font-mono leading-relaxed">
              {JSON.stringify(toolCall.args, null, 2)}
            </pre>
          </div>
          {toolCall.result && (
            <div>
              <div className="text-2xs font-medium text-sand-400 uppercase tracking-wider mb-1.5">
                返回结果
              </div>
              <pre className="text-xs text-sand-700 whitespace-pre-wrap break-all bg-sand-50 rounded-lg p-2.5 font-mono
                              max-h-48 overflow-y-auto leading-relaxed">
                {toolCall.result.length > 2000
                  ? toolCall.result.slice(0, 2000) + "\n..."
                  : toolCall.result}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
