// src/components/layout/Sidebar.tsx
import { NavLink } from "react-router-dom";
import {
  Rss,
  BookOpen,
  Database,
  Activity,
  ChevronLeft,
  ChevronRight,
  Newspaper,
} from "lucide-react";
import { useUIStore } from "../../store/useUIStore";
import { cn } from "../../lib/utils";

const navItems = [
  { to: "/feed", icon: Rss, label: "Фід" },
  { to: "/articles", icon: BookOpen, label: "Статті" },
  { to: "/sources", icon: Database, label: "Джерела" },
  { to: "/tasks", icon: Activity, label: "Задачі" },
];

export const Sidebar = () => {
  const { sidebarOpen, toggleSidebar } = useUIStore();

  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-40 flex flex-col",
        "bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800",
        "transition-all duration-300",
        sidebarOpen ? "w-64" : "w-16",
      )}
    >
      {/* Logo */}
      <div className="flex items-center h-16 px-4 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center flex-shrink-0">
            <Newspaper className="w-4 h-4 text-white" />
          </div>
          {sidebarOpen && (
            <span className="font-semibold text-slate-900 dark:text-white truncate">
              NewsAgg
            </span>
          )}
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 space-y-1 px-2 overflow-y-auto">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-150 group",
                isActive
                  ? "bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400"
                  : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white",
              )
            }
          >
            <Icon className="w-5 h-5 flex-shrink-0" />
            {sidebarOpen && (
              <span className="text-sm font-medium truncate">{label}</span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Toggle button */}
      <button
        onClick={toggleSidebar}
        className="flex items-center justify-center h-12 border-t border-slate-200 dark:border-slate-800 text-slate-400 hover:text-slate-600 dark:hover:text-white transition-colors"
      >
        {sidebarOpen ? (
          <ChevronLeft className="w-4 h-4" />
        ) : (
          <ChevronRight className="w-4 h-4" />
        )}
      </button>
    </aside>
  );
};
