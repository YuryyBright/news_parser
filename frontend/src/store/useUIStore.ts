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

        // Надійний спосіб перемикання класів
        if (next === "dark") {
          document.documentElement.classList.add("dark");
        } else {
          document.documentElement.classList.remove("dark");
        }

        set({ theme: next });
      },
      setTheme: (t) => {
        if (t === "dark") {
          document.documentElement.classList.add("dark");
        } else {
          document.documentElement.classList.remove("dark");
        }
        set({ theme: t });
      },
      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
    }),
    { name: "ui-store", partialize: (s) => ({ theme: s.theme }) },
  ),
);

// Ініціалізація теми при завантаженні (залишається без змін)
const savedTheme = localStorage.getItem("ui-store");
if (savedTheme) {
  try {
    const parsed = JSON.parse(savedTheme);
    if (parsed?.state?.theme === "dark") {
      document.documentElement.classList.add("dark");
    }
  } catch {}
}
