// src/pages/NotFoundPage.tsx
// Design: Editorial Dark — glitchy 404
import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

export const NotFoundPage = () => {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-950 relative overflow-hidden">
      {/* Background detail */}
      <div className="absolute inset-0 opacity-[0.03]">
        {Array.from({ length: 20 }).map((_, i) => (
          <div
            key={i}
            className="absolute w-full h-px bg-zinc-300"
            style={{ top: `${i * 5}%` }}
          />
        ))}
      </div>

      <div className="text-center relative z-10">
        <div className="relative mb-6 select-none">
          <div className="text-[10rem] font-black text-zinc-900 leading-none tracking-tighter">
            404
          </div>
          {/* Glitch layer */}
          <div className="absolute inset-0 text-[10rem] font-black text-amber-500/20 leading-none tracking-tighter translate-x-1">
            404
          </div>
        </div>

        <div className="w-16 h-px bg-amber-500 mx-auto mb-6" />

        <h1 className="text-xl font-bold text-zinc-200 mb-2 tracking-tight">
          Сторінку не знайдено
        </h1>
        <p className="text-zinc-600 text-sm mb-8 font-mono">
          ERROR_CODE: PAGE_NOT_FOUND
        </p>

        <button
          onClick={() => navigate("/feed")}
          className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg text-sm font-bold transition-all
            bg-amber-500 hover:bg-amber-400 text-zinc-950 shadow-lg shadow-amber-500/20"
        >
          <ArrowLeft className="w-4 h-4" />
          На головну
        </button>
      </div>
    </div>
  );
};
