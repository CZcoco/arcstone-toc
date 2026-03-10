import { useState, useEffect, useRef } from "react";
import { ChevronDown } from "lucide-react";
import { listModels, type ModelInfo } from "@/lib/api";

// 模型显示名映射
const MODEL_LABELS: Record<string, string> = {
  deepseek: "DeepSeek V3.2",
  kimi: "Kimi K2.5",
  qwen: "Qwen 3.5",
  "claude-opus": "Claude Opus 4.6",
  "claude-sonnet": "Claude Sonnet 4.6",
  "claude-opus-plan": "Claude Opus 4.6 Plan",
  "claude-sonnet-plan": "Claude Sonnet 4.6 Plan",
  gpt: "GPT-5.4 xhigh fast Plan",
};

interface ModelSelectorProps {
  value: string;
  onChange: (model: string) => void;
  disabled?: boolean;
}

export default function ModelSelector({ value, onChange, disabled }: ModelSelectorProps) {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listModels()
      .then(({ models }) => setModels(models.filter((m) => m.available)))
      .catch(() => {});
  }, []);

  // 点击外部关闭
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const label = MODEL_LABELS[value] || value;

  if (models.length <= 1) return null;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => !disabled && setOpen(!open)}
        disabled={disabled}
        className="flex items-center gap-1 px-2.5 py-1.5 text-2xs font-medium
                   text-sand-500 hover:text-sand-700 hover:bg-sand-200/50
                   rounded-lg transition-colors disabled:opacity-40"
      >
        {label}
        <ChevronDown size={12} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute bottom-full left-0 mb-1 min-w-[160px]
                        bg-white rounded-xl shadow-[0_4px_16px_rgba(0,0,0,0.1),0_0_0_1px_rgba(0,0,0,0.04)]
                        py-1 animate-fade-in z-50">
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
