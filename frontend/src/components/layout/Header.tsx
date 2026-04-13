// src/components/layout/Header.tsx
import { Moon, Sun } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useUIStore } from "../../store/useUIStore";
import { cn } from "../../lib/utils";

export const Header = () => {
  const { theme, toggleTheme } = useUIStore();
  const navigate = useNavigate();

  return (
    <header
      className={cn(
        // Використовуємо justify-end, щоб притиснути елементи вправо
        "flex items-center justify-end h-14 sm:h-16 px-3 sm:px-6 gap-3",
        "bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800",
        "transition-colors duration-300",
      )}
    >
      <div className="flex items-center gap-1.5 sm:gap-3">
        {/* Перемикач теми */}
        <button
          onClick={toggleTheme}
          className={cn(
            "w-9 h-9 rounded-lg flex items-center justify-center",
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

        {/* Заглушка аватара користувача */}
        <button
          onClick={() => navigate("/login")}
          className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center text-white text-sm font-semibold hover:opacity-90 transition-opacity"
          aria-label="Профіль користувача"
        >
          U
        </button>
      </div>
    </header>
  );
};
