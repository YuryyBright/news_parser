// src/components/layout/Layout.tsx
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { useUIStore } from "../../store/useUIStore";
import { cn } from "../../lib/utils";

export const Layout = () => {
  const { sidebarOpen } = useUIStore();

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50 dark:bg-slate-950 transition-colors duration-300">
      <Sidebar />
      <div
        className={cn(
          "flex flex-col flex-1 overflow-hidden transition-all duration-300",
          sidebarOpen ? "ml-64" : "ml-16",
        )}
      >
        <Header />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
