import { useState, useEffect, useRef } from "react";
import { ChevronDown } from "lucide-react";
import { listModels, type ModelInfo } from "@/lib/api";

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
        const available = models.filter((m) => m.available);
        setModels(available);
        // 如果当前选中的模型不在列表里，自动选第一个
        if (available.length > 0 && !available.some((m) => m.id === value)) {
          onChange(available[0].id);
        }
      })
      .catch(() => { if (!cancelled) setModels([]); });
    return () => { cancelled = true; };
  }, [refreshKey]);

  // 点击外部关闭
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const currentModel = models.find((m) => m.id === value);
  const label = currentModel?.name || value || "未配置模型";
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
              onClick={() => { onChange(m.id); setOpen(false); }}
              className={`flex items-center justify-between w-full px-3.5 py-2 text-[0.8125rem]
                         transition-colors
                         ${m.id === value
                           ? "text-sand-800 bg-sand-50 font-medium"
                           : "text-sand-600 hover:bg-sand-50"}`}
            >
              <span>{m.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
