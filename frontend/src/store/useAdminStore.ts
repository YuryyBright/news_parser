// src/store/useAdminStore.ts
import { create } from "zustand";

interface AdminFilters {
  fromDate: string | null;
  toDate: string | null;
  language: string | null;
  setDateRange: (from: string | null, to: string | null) => void;
  setLanguage: (lang: string | null) => void;
  reset: () => void;
}

export const useAdminStore = create<AdminFilters>((set) => ({
  fromDate: null,
  toDate: null,
  language: null,
  setDateRange: (from, to) => set({ fromDate: from, toDate: to }),
  setLanguage: (lang) => set({ language: lang }),
  reset: () => set({ fromDate: null, toDate: null, language: null }),
}));
