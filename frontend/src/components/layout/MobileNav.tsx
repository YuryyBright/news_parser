// src/components/layout/MobileNav.tsx
import { NavLink } from "react-router-dom";
import { Rss, BookOpen, Database, Activity } from "lucide-react";
import { cn } from "../../lib/utils";

const navItems = [
  { to: "/feed", icon: Rss, label: "Фід" },
  { to: "/articles", icon: BookOpen, label: "Статті" },
  { to: "/sources", icon: Database, label: "Джерела" },
  { to: "/tasks", icon: Activity, label: "Задачі" },
];

export const MobileNav = () => {
  return (
    <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 safe-area-bottom">
      <div className="flex items-stretch h-16">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "flex-1 flex flex-col items-center justify-center gap-0.5 text-[10px] font-medium transition-colors",
                isActive
                  ? "text-blue-600 dark:text-blue-400"
                  : "text-slate-400 dark:text-slate-500",
              )
            }
          >
            {({ isActive }) => (
              <>
                <div
                  className={cn(
                    "w-10 h-6 flex items-center justify-center rounded-full transition-colors",
                    isActive && "bg-blue-50 dark:bg-blue-950",
                  )}
                >
                  <Icon className="w-5 h-5" />
                </div>
                {label}
              </>
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  );
};
