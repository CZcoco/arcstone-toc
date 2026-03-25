import { useState } from "react";
import { Lightbulb, BookOpen, BarChart3, FileEdit, Upload, X } from "lucide-react";

interface OnboardingModalProps {
  open: boolean;
  onClose: () => void;
}

const STEPS = [
  {
    title: "欢迎使用 Arcstone-econ",
    subtitle: "你的经济学论文 AI 助手，从选题到定稿，全程陪伴。",
    content: (
      <div className="space-y-3 mt-6">
        {[
          { icon: Lightbulb, text: "智能选题推荐" },
          { icon: BookOpen, text: "真实文献检索" },
          { icon: BarChart3, text: "数据获取与回归分析" },
          { icon: FileEdit, text: "Word 论文生成" },
        ].map(({ icon: Icon, text }) => (
          <div key={text} className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#c8956c]/10 flex items-center justify-center shrink-0">
              <Icon size={16} className="text-[#c8956c]" />
            </div>
            <span className="text-sm text-sand-700">{text}</span>
          </div>
        ))}
      </div>
    ),
  },
  {
    title: "怎么开始？",
    subtitle: "直接用自然语言告诉 AI 你想做什么。",
    content: (
      <div className="mt-6 space-y-4">
        <div className="space-y-2">
          {[
            "帮我选一个关于数字经济的论文题目",
            "搜索近5年关于碳排放的文献",
          ].map((msg) => (
            <div
              key={msg}
              className="bg-[#c8956c]/8 border border-[#c8956c]/15 rounded-xl px-3.5 py-2.5 text-sm text-sand-700"
            >
              {msg}
            </div>
          ))}
        </div>
        <div className="flex items-center gap-2 text-xs text-sand-500">
          <Upload size={12} className="shrink-0" />
          <span>也可以上传 PDF、Excel、Word 文件让 AI 分析</span>
        </div>
      </div>
    ),
  },
  {
    title: "准备好了！",
    subtitle: "点击下方模板卡片快速开始，或直接在输入框输入你的需求。",
    content: (
      <div className="mt-8 flex justify-center">
        <div className="w-20 h-20">
          <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M24 6L38 38H10L24 6Z" fill="none" stroke="#c8956c" strokeWidth="1.5" strokeLinejoin="round" />
            <path d="M24 16L32 38H16L24 16Z" fill="#c8956c" fillOpacity="0.12" stroke="#c8956c" strokeWidth="1" strokeLinejoin="round" />
            <circle cx="24" cy="28" r="2" fill="#c8956c" fillOpacity="0.5" />
          </svg>
        </div>
      </div>
    ),
  },
];

export default function OnboardingModal({ open, onClose }: OnboardingModalProps) {
  const [step, setStep] = useState(0);

  if (!open) return null;

  const isLast = step === STEPS.length - 1;
  const current = STEPS[step];

  const handleClose = () => {
    localStorage.setItem("econ-agent-onboarding-done", "1");
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/20 backdrop-blur-[2px] flex items-center justify-center animate-fade-in">
      <div className="bg-white rounded-2xl shadow-xl max-w-sm w-full mx-4 p-7 relative">
        {/* Skip */}
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 text-sand-400 hover:text-sand-600 transition-colors"
        >
          <X size={16} />
        </button>

        {/* Content */}
        <h2 className="text-base font-semibold text-sand-800 pr-6">{current.title}</h2>
        <p className="text-sm text-sand-500 mt-1 leading-relaxed">{current.subtitle}</p>
        {current.content}

        {/* Footer */}
        <div className="mt-8 flex items-center justify-between">
          {/* Dots */}
          <div className="flex gap-1.5">
            {STEPS.map((_, i) => (
              <div
                key={i}
                className={`w-1.5 h-1.5 rounded-full transition-colors ${
                  i === step ? "bg-[#c8956c]" : "bg-sand-200"
                }`}
              />
            ))}
          </div>

          {/* Button */}
          <button
            onClick={() => (isLast ? handleClose() : setStep(step + 1))}
            className="px-5 py-2 rounded-xl text-sm font-medium transition-colors
                       bg-[#c8956c] text-white hover:bg-[#b8855c]"
          >
            {isLast ? "开始使用" : "下一步"}
          </button>
        </div>
      </div>
    </div>
  );
}
