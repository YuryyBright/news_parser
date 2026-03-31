// src/store/useUIStore.ts
import { create } from "zustand";
import { persist } from "zustand/middleware";

type Theme = "light" | "dark";

interface UIStore {
  theme: Theme;
  sidebarOpen: boolean;
  toggleTheme: () => void;
  setTheme: (t: Theme) => void;
  toggleSidebar: () => void;
}

export const useUIStore = create<UIStore>()(
  persist(
    (set, get) => ({
      theme: "light",
      sidebarOpen: true,
      toggleTheme: () => {
        const next = get().theme === "light" ? "dark" : "light";
        document.documentElement.classList.toggle("dark", next === "dark");
        set({ theme: next });
      },
      setTheme: (t) => {
        document.documentElement.classList.toggle("dark", t === "dark");
        set({ theme: t });
      },
      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
    }),
    { name: "ui-store", partialize: (s) => ({ theme: s.theme }) },
  ),
);

// Ініціалізація теми при завантаженні
const savedTheme = localStorage.getItem("ui-store");
if (savedTheme) {
  try {
    const parsed = JSON.parse(savedTheme);
    if (parsed?.state?.theme === "dark") {
      document.documentElement.classList.add("dark");
    }
  } catch {}
}
