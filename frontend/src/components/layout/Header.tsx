// src/components/layout/Header.tsx
import { Search, Moon, Sun } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useUIStore } from "../../store/useUIStore";
import { cn } from "../../lib/utils";

export const Header = () => {
  const { theme, toggleTheme } = useUIStore();
  const [search, setSearch] = useState("");
  const navigate = useNavigate();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (search.trim()) {
      navigate(`/articles?q=${encodeURIComponent(search.trim())}`);
      setSearch("");
    }
  };

  return (
    <header
      className={cn(
        "flex items-center justify-between h-16 px-6",
        "bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800",
        "transition-colors duration-300",
      )}
    >
      {/* Search */}
      <form onSubmit={handleSearch} className="flex-1 max-w-md">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Пошук статей..."
            className={cn(
              "w-full pl-10 pr-4 py-2 text-sm rounded-lg border",
              "bg-slate-50 dark:bg-slate-800",
              "border-slate-200 dark:border-slate-700",
              "text-slate-900 dark:text-white placeholder-slate-400",
              "focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400",
              "transition-colors duration-200",
            )}
          />
        </div>
      </form>

      {/* Right controls */}
      <div className="flex items-center gap-3 ml-4">
        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          className={cn(
            "relative w-9 h-9 rounded-lg flex items-center justify-center",
            "text-slate-500 dark:text-slate-400",
            "hover:bg-slate-100 dark:hover:bg-slate-800",
            "transition-all duration-200",
          )}
          aria-label="Переключити тему"
        >
          {theme === "dark" ? (
            <Sun className="w-4 h-4" />
          ) : (
            <Moon className="w-4 h-4" />
          )}
        </button>

        {/* User avatar (заглушка) */}
        <button
          onClick={() => navigate("/login")}
          className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center text-white text-sm font-semibold hover:opacity-90 transition-opacity"
        >
          U
        </button>
      </div>
    </header>
  );
};
