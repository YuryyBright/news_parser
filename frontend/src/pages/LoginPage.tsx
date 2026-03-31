// src/pages/LoginPage.tsx
// Design: Editorial Dark — dramatic split with geometric accent
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Eye, EyeOff, Rss } from "lucide-react";
import { cn } from "../lib/utils";

export const LoginPage = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    await new Promise((r) => setTimeout(r, 800));
    localStorage.setItem("access_token", "stub-token");
    navigate("/feed");
  };

  const inputClass = cn(
    "w-full px-4 py-3 rounded-lg border text-sm transition-all duration-200",
    "bg-zinc-900 border-zinc-700 text-zinc-100 placeholder-zinc-600",
    "focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500/60",
  );

  return (
    <div className="min-h-screen flex bg-zinc-950">
      {/* Left panel — editorial branding */}
      <div className="hidden lg:flex flex-col justify-between w-1/2 p-14 relative overflow-hidden bg-zinc-900">
        {/* Background geometric detail */}
        <div className="absolute inset-0 opacity-5">
          <div className="absolute top-0 right-0 w-[600px] h-[600px] border border-zinc-400 rounded-full -translate-y-1/2 translate-x-1/3" />
          <div className="absolute top-0 right-0 w-[400px] h-[400px] border border-zinc-400 rounded-full -translate-y-1/4 translate-x-1/4" />
          <div className="absolute bottom-0 left-0 w-[300px] h-[300px] border border-zinc-400 rounded-full translate-y-1/3 -translate-x-1/4" />
        </div>
        {/* Diagonal amber accent line */}
        <div className="absolute top-0 right-0 w-px h-full bg-gradient-to-b from-amber-500/40 via-amber-500/10 to-transparent" />

        {/* Logo */}
        <div className="flex items-center gap-3 relative z-10">
          <div className="w-9 h-9 rounded-lg bg-amber-500 flex items-center justify-center shadow-lg shadow-amber-500/30">
            <Rss className="w-4 h-4 text-zinc-950" />
          </div>
          <span className="text-zinc-100 font-bold text-lg tracking-tight">
            NewsAgg
          </span>
        </div>

        {/* Main copy */}
        <div className="relative z-10">
          <div className="w-12 h-px bg-amber-500 mb-6" />
          <h1 className="text-5xl font-black text-zinc-50 leading-[1.05] mb-5 tracking-tight">
            Актуальні
            <br />
            <span className="text-amber-400">новини</span>
            <br />
            без шуму
          </h1>
          <p className="text-zinc-400 text-base leading-relaxed max-w-xs">
            Персоналізований агрегатор, що вчиться ваших інтересів і фільтрує
            зайве.
          </p>

          {/* Stats row */}
          <div className="flex gap-8 mt-10">
            {[
              ["24/7", "Моніторинг"],
              ["AI", "Ранжування"],
              ["0", "Реклами"],
            ].map(([val, lbl]) => (
              <div key={lbl}>
                <div className="text-2xl font-black text-amber-400 leading-none">
                  {val}
                </div>
                <div className="text-xs text-zinc-500 mt-1 uppercase tracking-widest">
                  {lbl}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="text-zinc-700 text-xs font-mono relative z-10">
          © 2025 NewsAgg
        </div>
      </div>

      {/* Right panel — form */}
      <div className="flex-1 flex items-center justify-center p-8 bg-zinc-950">
        <div className="w-full max-w-sm">
          {/* Mobile logo */}
          <div className="flex items-center gap-2.5 mb-10 lg:hidden">
            <div className="w-8 h-8 rounded-lg bg-amber-500 flex items-center justify-center">
              <Rss className="w-3.5 h-3.5 text-zinc-950" />
            </div>
            <span className="text-zinc-100 font-bold">NewsAgg</span>
          </div>

          <div className="mb-8">
            <p className="text-xs font-mono text-amber-500 uppercase tracking-widest mb-2">
              Вхід до системи
            </p>
            <h2 className="text-2xl font-black text-zinc-50 tracking-tight">
              Привіт знову
            </h2>
            <p className="text-zinc-500 mt-1 text-sm">
              Введіть ваші облікові дані
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-mono text-zinc-500 uppercase tracking-widest mb-2">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="user@example.com"
                required
                className={inputClass}
              />
            </div>

            <div>
              <label className="block text-xs font-mono text-zinc-500 uppercase tracking-widest mb-2">
                Пароль
              </label>
              <div className="relative">
                <input
                  type={showPass ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className={cn(inputClass, "pr-12")}
                />
                <button
                  type="button"
                  onClick={() => setShowPass(!showPass)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-600 hover:text-zinc-300 transition-colors"
                >
                  {showPass ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className={cn(
                "w-full py-3 rounded-lg text-sm font-bold transition-all duration-200 mt-2",
                "bg-amber-500 hover:bg-amber-400 text-zinc-950",
                "shadow-lg shadow-amber-500/20 hover:shadow-amber-500/30",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                loading && "animate-pulse",
              )}
            >
              {loading ? "Входимо..." : "Увійти →"}
            </button>
          </form>

          <p className="text-[11px] text-zinc-700 font-mono text-center mt-6">
            AUTH_MODE=stub · JWT coming soon
          </p>
        </div>
      </div>
    </div>
  );
};
