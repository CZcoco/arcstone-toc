import { useState, useEffect, useRef } from "react";
import type { LucideIcon } from "lucide-react";
import { ChevronDown, Bot, GraduationCap, PencilLine, Presentation } from "lucide-react";
import { listModes, selectMode } from "@/lib/api";
import type { ModeInfo, TemplateCard } from "@/lib/api";

const ICON_MAP: Record<string, LucideIcon> = {
  "bot": Bot,
  "graduation-cap": GraduationCap,
  "pencil-line": PencilLine,
  "presentation": Presentation,
};

function ModeIcon({ icon, size = 14, className }: { icon: string; size?: number; className?: string }) {
  const Icon = ICON_MAP[icon] || Bot;
  return <Icon size={size} className={className} />;
}

interface ModeSelectorProps {
  onChange?: (modeId: string, templates?: TemplateCard[]) => void;
}

export default function ModeSelector({ onChange }: ModeSelectorProps) {
  const [modes, setModes] = useState<ModeInfo[]>([]);
  const [activeId, setActiveId] = useState("default");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listModes()
      .then(({ modes: m, active_id }) => {
        setModes(m);
        // Restore from localStorage if available
        const saved = localStorage.getItem("econ-agent-mode");
        let effectiveId = active_id;
        if (saved && m.some(mode => mode.id === saved)) {
          effectiveId = saved;
          setActiveId(saved);
          if (saved !== active_id) {
            selectMode(saved).catch(() => {});
          }
        } else {
          setActiveId(active_id);
        }
        // 初始化时传递当前 mode 的 templates
        const active = m.find(mode => mode.id === effectiveId);
        onChange?.(effectiveId, active?.templates);
      })
      .catch(() => {});
  }, []);

  // Click outside to close
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, [open]);

  const current = modes.find(m => m.id === activeId);

  async function handleSelect(modeId: string) {
    setOpen(false);
    if (modeId === activeId) return;
    setActiveId(modeId);
    localStorage.setItem("econ-agent-mode", modeId);
    const selected = modes.find(m => m.id === modeId);
    try {
      await selectMode(modeId);
      onChange?.(modeId, selected?.templates);
    } catch {
      // 静默失败
    }
  }

  if (modes.length === 0) return null;

  return (
    <div ref={ref} className="relative px-2.5 pb-2">
      <button
        onClick={(e) => { e.stopPropagation(); setOpen(!open); }}
        className="flex items-center gap-2 w-full px-3 py-2 text-[0.8125rem]
                   rounded-xl border border-sand-200/80 text-sand-600
                   hover:bg-white hover:border-sand-300/80 hover:shadow-[0_1px_3px_rgba(0,0,0,0.04)]
                   transition-all duration-150"
      >
        {current && <ModeIcon icon={current.icon} size={14} className="text-[#c8956c] shrink-0" />}
        <span className="truncate flex-1 text-left">{current?.name || "选择模式"}</span>
        <ChevronDown size={13} className={`text-sand-400 shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute left-2.5 right-2.5 top-full mt-1 z-20
                        bg-white rounded-xl shadow-[0_4px_16px_rgba(0,0,0,0.1),0_0_0_1px_rgba(0,0,0,0.04)]
                        py-1 animate-fade-in max-h-60 overflow-y-auto">
          {modes.map(m => (
            <button
              key={m.id}
              onClick={() => handleSelect(m.id)}
              className={`flex items-start gap-2.5 w-full px-3.5 py-2.5 text-left transition-colors
                         ${m.id === activeId ? "bg-sand-50" : "hover:bg-sand-50/60"}`}
            >
              <ModeIcon icon={m.icon} size={15} className={`mt-0.5 shrink-0 ${m.id === activeId ? "text-[#c8956c]" : "text-sand-400"}`} />
              <div className="min-w-0">
                <div className={`text-[0.8125rem] leading-snug ${m.id === activeId ? "text-sand-800 font-medium" : "text-sand-700"}`}>
                  {m.name}
                </div>
                <div className="text-[0.6875rem] text-sand-400 leading-snug mt-0.5 truncate">
                  {m.description}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
