import { useState } from "react";
import { ChevronDown, ChevronRight, Search, Globe, Calculator, ImagePlus, Loader2 } from "lucide-react";
import type { ToolCall } from "@/types";
import { BASE_URL } from "@/lib/api";

const TOOL_CONFIG: Record<string, { label: string; icon: typeof Search }> = {
  bailian_rag: { label: "知识库检索", icon: Search },
  web_search: { label: "网络搜索", icon: Globe },
  calculate_irr: { label: "财务计算", icon: Calculator },
  generate_image: { label: "生成图片", icon: ImagePlus },
};

/** 从工具结果中提取图片路径 */
function extractImageUrls(result: string): string[] {
  const urls: string[] = [];
  // 匹配 ![...](/workspace/...) 或 ![...](http...)
  const regex = /!\[.*?\]\((\/workspace\/[^\s)]+|https?:\/\/[^\s)]+)\)/g;
  let match;
  while ((match = regex.exec(result)) !== null) {
    urls.push(match[1]);
  }
  return urls;
}

function resolveImageSrc(src: string): string {
  const cleaned = src.replace(/\\/g, "");
  if (cleaned.startsWith("/workspace/")) {
    const rel = cleaned.slice("/workspace/".length);
    return `${BASE_URL}/workspace/raw/${rel.split("/").map(encodeURIComponent).join("/")}`;
  }
  return cleaned;
}

interface ToolCallCardProps {
  toolCall: ToolCall;
}

export default function ToolCallCard({ toolCall }: ToolCallCardProps) {
  const isImageTool = toolCall.name === "generate_image";
  const isDone = toolCall.status === "done";
  // 图片生成工具完成后自动展开
  const [expanded, setExpanded] = useState(isImageTool && isDone);

  const config = TOOL_CONFIG[toolCall.name] || { label: toolCall.name, icon: Search };
  const Icon = config.icon;

  // 提取图片
  const imageUrls = isDone && toolCall.result ? extractImageUrls(toolCall.result) : [];

  return (
    <div className="rounded-xl border border-sand-200 bg-white/60 overflow-hidden animate-fade-in my-2">
      <button
        className="flex items-center gap-2.5 w-full px-3.5 py-2.5 text-left
                   hover:bg-sand-50/80 transition-colors group"
        onClick={() => setExpanded(!expanded)}
      >
        {/* Status dot */}
        {isDone ? (
          toolCall.result?.includes("已中断") ? (
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0" />
          ) : (
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />
          )
        ) : (
          <Loader2 size={12} className="text-accent shrink-0 animate-spin" />
        )}

        <Icon size={13} className="text-sand-500 shrink-0" />

        <span className="text-[0.8125rem] font-medium text-sand-700">
          {config.label}
        </span>

        <span className="text-2xs text-sand-400 ml-auto mr-1">
          {isDone ? (toolCall.result?.includes("已中断") ? "已中断" : "") : "执行中"}
        </span>

        {expanded ? (
          <ChevronDown size={13} className="text-sand-400 group-hover:text-sand-600 transition-colors" />
        ) : (
          <ChevronRight size={13} className="text-sand-400 group-hover:text-sand-600 transition-colors" />
        )}
      </button>

      {/* 图片直接显示（不需要展开） */}
      {isDone && imageUrls.length > 0 && !expanded && (
        <div className="px-3.5 pb-3">
          {imageUrls.map((url, i) => (
            <img
              key={i}
              src={resolveImageSrc(url)}
              alt="生成的图片"
              className="rounded-xl max-w-full max-h-80 shadow-[0_2px_8px_rgba(0,0,0,0.08)] cursor-pointer"
              loading="lazy"
              onClick={() => window.open(resolveImageSrc(url), "_blank")}
            />
          ))}
        </div>
      )}

      {expanded && (
        <div className="border-t border-sand-200/80 px-3.5 py-3 space-y-3 animate-fade-in">
          {/* 图片预览 */}
          {imageUrls.length > 0 && (
            <div>
              {imageUrls.map((url, i) => (
                <img
                  key={i}
                  src={resolveImageSrc(url)}
                  alt="生成的图片"
                  className="rounded-xl max-w-full max-h-96 shadow-[0_2px_8px_rgba(0,0,0,0.08)] mb-3 cursor-pointer"
                  loading="lazy"
                  onClick={() => window.open(resolveImageSrc(url), "_blank")}
                />
              ))}
            </div>
          )}
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
