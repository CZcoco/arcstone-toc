import { useState, useEffect, useRef } from "react";
import { ChevronDown } from "lucide-react";
import { listModels, type ModelInfo } from "@/lib/api";

// 模型显示名映射
const MODEL_LABELS: Record<string, string> = {
  "claude-opus": "Claude Opus 4.6 API",
  "claude-sonnet": "Claude Sonnet 4.6 API",
  "claude-opus-hon": "Claude Opus 4.6 API2",
  "claude-sonnet-hon": "Claude Sonnet 4.6 API2",
  "claude-opus-plan": "Claude Opus 4.6 Plan",
  "claude-sonnet-plan": "Claude Sonnet 4.6 Plan",
  gpt: "GPT-5.4 xhigh Plan",
  deepseek: "应急模型",
};

const MODEL_FALLBACKS: Record<string, string[]> = {
  "claude-opus-plan": ["claude-opus", "claude-opus-hon", "claude-sonnet", "claude-sonnet-hon", "gpt", "claude-sonnet-plan", "deepseek"],
  "claude-sonnet-plan": ["claude-sonnet", "claude-sonnet-hon", "claude-opus", "claude-opus-hon", "gpt", "claude-opus-plan", "deepseek"],
  "claude-opus": ["claude-opus-hon", "claude-sonnet", "claude-sonnet-hon", "gpt", "claude-opus-plan", "claude-sonnet-plan", "deepseek"],
  "claude-sonnet": ["claude-sonnet-hon", "claude-opus", "claude-opus-hon", "gpt", "claude-sonnet-plan", "claude-opus-plan", "deepseek"],
  "claude-opus-hon": ["claude-opus", "claude-sonnet-hon", "claude-sonnet", "gpt", "claude-opus-plan", "claude-sonnet-plan", "deepseek"],
  "claude-sonnet-hon": ["claude-sonnet", "claude-opus-hon", "claude-opus", "gpt", "claude-sonnet-plan", "claude-opus-plan", "deepseek"],
  gpt: ["claude-sonnet", "claude-sonnet-hon", "claude-opus", "claude-opus-hon", "claude-sonnet-plan", "claude-opus-plan", "deepseek"],
  deepseek: ["gpt", "claude-sonnet", "claude-sonnet-hon", "claude-opus", "claude-opus-hon", "claude-sonnet-plan", "claude-opus-plan"],
};

const MODEL_PRIORITY = [
  "gpt",
  "claude-sonnet",
  "claude-sonnet-hon",
  "claude-opus",
  "claude-opus-hon",
  "claude-sonnet-plan",
  "claude-opus-plan",
  "deepseek",
];

function resolveFallbackModel(current: string, availableModels: ModelInfo[]) {
  const availableIds = new Set(availableModels.map((model) => model.id));

  if (current && availableIds.has(current)) {
    return current;
  }

  for (const candidate of MODEL_FALLBACKS[current] || []) {
    if (availableIds.has(candidate)) {
      return candidate;
    }
  }

  for (const candidate of MODEL_PRIORITY) {
    if (availableIds.has(candidate)) {
      return candidate;
    }
  }

  return "";
}

interface ModelSelectorProps {
  value: string;
  onChange: (model: string) => void;
  disabled?: boolean;
  refreshKey?: number;
}

export default function ModelSelector({ value, onChange, disabled, refreshKey }: ModelSelectorProps) {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;

    listModels()
      .then(({ models }) => {
        if (cancelled) return;

        const availableModels = models.filter((m) => m.available);
        setModels(availableModels);

        const resolvedModel = resolveFallbackModel(value, availableModels);
        if (resolvedModel !== value) {
          onChange(resolvedModel);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setModels([]);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [refreshKey, value, onChange]);

  // 点击外部关闭
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const label = value ? (MODEL_LABELS[value] || value) : "未配置模型";

  // 只隐藏下拉菜单（当只有1个或0个模型时），但始终显示当前模型
  const showDropdown = models.length > 1;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => !disabled && showDropdown && setOpen(!open)}
        disabled={disabled || !showDropdown}
        className="flex items-center gap-1 px-2.5 py-1.5 text-2xs font-medium
                   text-sand-500 hover:text-sand-700 hover:bg-sand-200/50
                   rounded-lg transition-colors disabled:opacity-60"
      >
        {label}
        {showDropdown && (
          <ChevronDown size={12} className={`transition-transform ${open ? "rotate-180" : ""}`} />
        )}
      </button>

      {open && showDropdown && (
        <div className="absolute bottom-full left-0 mb-1 min-w-[170px]
                        bg-white rounded-xl shadow-[0_4px_16px_rgba(0,0,0,0.1),0_0_0_1px_rgba(0,0,0,0.04)]
                        py-1 animate-fade-in z-50 whitespace-nowrap">
          {models.map((m) => (
            <button
              key={m.id}
              onClick={() => {
                onChange(m.id);
                setOpen(false);
              }}
              className={`flex items-center justify-between w-full px-3.5 py-2 text-[0.8125rem]
                         transition-colors
                         ${m.id === value
                           ? "text-sand-800 bg-sand-50 font-medium"
                           : "text-sand-600 hover:bg-sand-50"
                         }`}
            >
              <span>{MODEL_LABELS[m.id] || m.id}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
