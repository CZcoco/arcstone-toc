import type { LucideIcon } from "lucide-react";
import {
  Lightbulb, BookOpen, BarChart3, FileEdit, Calculator,
  CheckCircle, FileText, GraduationCap, Presentation, Bot,
} from "lucide-react";
import type { TemplateCard } from "@/lib/api";

const ICON_MAP: Record<string, LucideIcon> = {
  "lightbulb": Lightbulb,
  "book-open": BookOpen,
  "bar-chart-3": BarChart3,
  "file-edit": FileEdit,
  "calculator": Calculator,
  "check-circle": CheckCircle,
  "file-text": FileText,
  "graduation-cap": GraduationCap,
  "presentation": Presentation,
  "bot": Bot,
};

const DEFAULT_TEMPLATES: TemplateCard[] = [
  {
    icon: "lightbulb",
    title: "帮我选题",
    description: "根据你的兴趣和研究方向，推荐合适的毕业论文题目",
    message: "我是经济学本科生，请帮我选一个合适的毕业论文题目。我对宏观经济感兴趣，请给我几个方向建议。",
  },
  {
    icon: "book-open",
    title: "文献综述",
    description: "搜索真实学术文献，生成规范的文献综述",
    message: "请帮我围绕「数字经济对就业结构的影响」这个主题，搜索相关文献并撰写一段文献综述。",
  },
  {
    icon: "bar-chart-3",
    title: "数据分析",
    description: "获取经济数据，运行计量回归和统计分析",
    message: "请帮我获取中国近20年的GDP和城镇化率数据，并做一个简单的回归分析，看看两者的关系。",
  },
  {
    icon: "file-edit",
    title: "论文写作",
    description: "按学术规范生成 Word 格式的论文章节",
    message: "请帮我生成一篇关于「人口老龄化对消费结构影响」的论文开题报告，包含研究背景、意义、文献综述提纲和研究方法。",
  },
];

interface WelcomeScreenProps {
  onSendMessage: (message: string) => void;
  username?: string;
  templates?: TemplateCard[];
}

export default function WelcomeScreen({ onSendMessage, username, templates }: WelcomeScreenProps) {
  const cards = templates && templates.length > 0 ? templates : DEFAULT_TEMPLATES;

  return (
    <div className="flex flex-col items-center justify-center h-full animate-fade-in px-4">
      {/* Logo */}
      <div className="mb-4">
        <div className="w-10 h-10">
          <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M24 6L38 38H10L24 6Z" fill="none" stroke="#c8956c" strokeWidth="1.5" strokeLinejoin="round" />
            <path d="M24 16L32 38H16L24 16Z" fill="#c8956c" fillOpacity="0.12" stroke="#c8956c" strokeWidth="1" strokeLinejoin="round" />
            <circle cx="24" cy="28" r="2" fill="#c8956c" fillOpacity="0.5" />
          </svg>
        </div>
      </div>

      {/* Greeting */}
      <h1 className="text-lg font-medium text-sand-800 tracking-tight mb-1">
        {username ? `你好，${username}！` : "你好！"}
      </h1>
      <p className="text-sm text-sand-500 mb-8 text-center max-w-sm leading-relaxed">
        我是你的经济学论文 AI 助手，可以帮你完成从选题到定稿的全流程。
      </p>

      {/* Template cards — 响应式：窄屏单列，宽屏两列 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-[min(90%,32rem)] px-2">
        {cards.map((t) => {
          const Icon = ICON_MAP[t.icon] || Lightbulb;
          return (
            <button
              key={t.title}
              onClick={() => onSendMessage(t.message)}
              className="bg-white rounded-2xl p-4 text-left
                         border border-sand-200/40 hover:border-[#c8956c]/30
                         shadow-[0_1px_4px_rgba(0,0,0,0.04)]
                         hover:shadow-[0_2px_12px_rgba(0,0,0,0.07)]
                         transition-all duration-200 cursor-pointer group"
            >
              <Icon size={22} className="text-[#c8956c] mb-2 group-hover:scale-105 transition-transform" />
              <div className="text-sm font-medium text-sand-800 mb-0.5">{t.title}</div>
              <div className="text-xs text-sand-500 leading-relaxed">{t.description}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
