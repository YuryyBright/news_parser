// src/components/layout/Layout.tsx
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { MobileNav } from "./MobileNav";
import { useUIStore } from "../../store/useUIStore";
import { cn } from "../../lib/utils";

export const Layout = () => {
  const { sidebarOpen } = useUIStore();

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50 dark:bg-slate-950 transition-colors duration-300">
      {/* Sidebar — hidden on mobile, visible md+ */}
      <div className="hidden md:block">
        <Sidebar />
      </div>

      <div
        className={cn(
          "flex flex-col flex-1 overflow-hidden transition-all duration-300",
          // md+ — зміщуємо під sidebar
          "md:ml-16",
          sidebarOpen ? "md:ml-64" : "md:ml-16",
        )}
      >
        <Header />
        <main className="flex-1 overflow-y-auto p-3 sm:p-4 md:p-6 pb-20 md:pb-6">
          <Outlet />
        </main>
      </div>

      {/* Bottom nav — тільки mobile */}
      <MobileNav />
    </div>
  );
};
