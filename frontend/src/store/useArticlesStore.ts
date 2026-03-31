// src/store/useArticlesStore.ts
import { create } from "zustand";
import type { ArticleFilter } from "../api/types";

interface ArticlesStore {
  filters: ArticleFilter;
  activeArticleId: string | null;
  setFilter: <K extends keyof ArticleFilter>(
    key: K,
    value: ArticleFilter[K],
  ) => void;
  resetFilters: () => void;
  setActiveArticle: (id: string | null) => void;
}

const defaultFilters: ArticleFilter = {
  status: null,
  min_score: 0,
  language: null,
  limit: 50,
  offset: 0,
};

export const useArticlesStore = create<ArticlesStore>((set) => ({
  filters: defaultFilters,
  activeArticleId: null,

  setFilter: (key, value) =>
    set((s) => ({ filters: { ...s.filters, [key]: value, offset: 0 } })),

  resetFilters: () => set({ filters: defaultFilters }),

  setActiveArticle: (id) => set({ activeArticleId: id }),
}));
