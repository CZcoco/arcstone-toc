import { useState } from "react";

interface AuthScreenProps {
  onStart: (username: string, password: string) => Promise<void>;
}

export default function AuthScreen({ onStart }: AuthScreenProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError("请输入用户名和密码");
      return;
    }
    if (password.length < 8) {
      setError("密码至少 8 位");
      return;
    }
    setError("");
    setLoading(true);
    try {
      await onStart(username.trim(), password);
    } catch (err: any) {
      setError(err?.message || "操作失败，请重试");
    }
    setLoading(false);
  }

  return (
    <div className="flex items-center justify-center h-screen bg-sand-100">
      <div className="w-full max-w-sm mx-4">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-10 h-10 mb-4">
            <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M24 6L38 38H10L24 6Z" fill="none" stroke="#c8956c" strokeWidth="1.5" strokeLinejoin="round" />
              <path d="M24 16L32 38H16L24 16Z" fill="#c8956c" fillOpacity="0.12" stroke="#c8956c" strokeWidth="1" strokeLinejoin="round" />
              <circle cx="24" cy="28" r="2" fill="#c8956c" fillOpacity="0.5" />
            </svg>
          </div>
          <h1 className="text-lg font-medium text-sand-800 tracking-tight">Arcstone-econ</h1>
          <p className="text-xs text-sand-400 mt-1">输入用户名和密码即可开始</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-[0_2px_12px_rgba(0,0,0,0.06)] p-6">
          {error && (
            <div className="mb-4 px-3 py-2 rounded-lg bg-red-50 text-red-600 text-xs">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-3 py-2.5 text-sm text-sand-800 bg-sand-50 border border-sand-200
                           rounded-xl outline-none focus:border-sand-400 focus:ring-1 focus:ring-sand-200
                           transition-all placeholder:text-sand-300"
                placeholder="用户名"
                autoFocus
              />
            </div>

            <div>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2.5 text-sm text-sand-800 bg-sand-50 border border-sand-200
                           rounded-xl outline-none focus:border-sand-400 focus:ring-1 focus:ring-sand-200
                           transition-all placeholder:text-sand-300"
                placeholder="密码（至少 8 位）"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 mt-1 text-sm font-medium text-white rounded-xl
                         bg-[#c8956c] hover:bg-[#b8855c] active:bg-[#a87550]
                         disabled:opacity-50 disabled:cursor-not-allowed
                         transition-colors duration-150 shadow-sm"
            >
              {loading ? "正在连接..." : "开始使用"}
            </button>
          </form>

          <p className="text-center text-[0.6875rem] text-sand-300 mt-4">
            首次输入将自动创建账号
          </p>
        </div>
      </div>
    </div>
  );
}
