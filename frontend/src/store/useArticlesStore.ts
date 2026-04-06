// src/store/useArticlesStore.ts
import { create } from "zustand";
import type { ArticleStatus } from "../api/types";

export type SortBy = "created_at" | "published_at" | "relevance_score";
export type SortDir = "asc" | "desc";
export type DatePreset = "today" | "week" | "month" | null;

export interface ArticleFilters {
  status: ArticleStatus | null;
  min_score: number;
  language: string | null;
  tag: string | null;
  // Date
  date_from: string | null; // ISO string
  date_to: string | null;
  date_preset: DatePreset;
  // Sort
  sort_by: SortBy;
  sort_dir: SortDir;
  // Pagination
  page: number;
  page_size: number;
}

interface ArticlesStore {
  filters: ArticleFilters;
  // Search
  searchQuery: string;
  isSearchMode: boolean;
  // Active article (drawer)
  activeArticleId: string | null;

  setFilter: <K extends keyof ArticleFilters>(
    key: K,
    value: ArticleFilters[K],
  ) => void;
  setDatePreset: (preset: DatePreset) => void;
  setSort: (sort_by: SortBy, sort_dir?: SortDir) => void;
  setPage: (page: number) => void;
  resetFilters: () => void;

  setSearchQuery: (q: string) => void;
  setSearchMode: (on: boolean) => void;
  setActiveArticle: (id: string | null) => void;
}

const DEFAULT_FILTERS: ArticleFilters = {
  status: null,
  min_score: 0,
  language: null,
  tag: null,
  date_from: null,
  date_to: null,
  date_preset: null,
  sort_by: "created_at",
  sort_dir: "desc",
  page: 1,
  page_size: 30,
};

function getPresetDates(preset: DatePreset): {
  date_from: string | null;
  date_to: string | null;
} {
  if (!preset) return { date_from: null, date_to: null };
  const now = new Date();
  const to = now.toISOString();
  if (preset === "today") {
    const from = new Date(now);
    from.setHours(0, 0, 0, 0);
    return { date_from: from.toISOString(), date_to: to };
  }
  if (preset === "week") {
    const from = new Date(now);
    from.setDate(from.getDate() - 7);
    return { date_from: from.toISOString(), date_to: to };
  }
  if (preset === "month") {
    const from = new Date(now);
    from.setDate(from.getDate() - 30);
    return { date_from: from.toISOString(), date_to: to };
  }
  return { date_from: null, date_to: null };
}

export const useArticlesStore = create<ArticlesStore>((set, get) => ({
  filters: { ...DEFAULT_FILTERS },
  searchQuery: "",
  isSearchMode: false,
  activeArticleId: null,

  setFilter: (key, value) =>
    set((s) => ({
      filters: {
        ...s.filters,
        [key]: value,
        page: key === "page" ? (value as number) : 1,
      },
    })),

  setDatePreset: (preset) => {
    const dates = getPresetDates(preset);
    set((s) => ({
      filters: {
        ...s.filters,
        date_preset: preset,
        date_from: dates.date_from,
        date_to: dates.date_to,
        page: 1,
      },
    }));
  },

  setSort: (sort_by, sort_dir) => {
    const current = get().filters;
    // Якщо натиснули на вже активне сортування — перемикаємо напрямок
    const newDir =
      sort_dir ??
      (current.sort_by === sort_by && current.sort_dir === "desc"
        ? "asc"
        : "desc");
    set((s) => ({
      filters: { ...s.filters, sort_by, sort_dir: newDir, page: 1 },
    }));
  },

  setPage: (page) => set((s) => ({ filters: { ...s.filters, page } })),

  resetFilters: () => set({ filters: { ...DEFAULT_FILTERS } }),

  setSearchQuery: (q) =>
    set({ searchQuery: q, isSearchMode: q.trim().length >= 2 }),
  setSearchMode: (on) => set({ isSearchMode: on }),
  setActiveArticle: (id) => set({ activeArticleId: id }),
}));
