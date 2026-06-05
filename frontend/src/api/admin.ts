// src/api/admin.ts
import { client } from "./client";
import type {
  AdminOverviewStats,
  TimeSeriesPoint,
  LanguageDistribution,
  TagStats,
  ScoreHistogramBin,
  SourcePerformance,
} from "./types";
import type { AdminFiltersParams } from "../hooks/useAdmin";

function toParams(filters?: AdminFiltersParams) {
  const p: Record<string, string> = {};
  if (filters?.from_date) p.from_date = filters.from_date;
  if (filters?.to_date) p.to_date = filters.to_date;
  if (filters?.language) p.language = filters.language;
  return p;
}

export const adminApi = {
  getOverview: (filters?: AdminFiltersParams) =>
    client.get<AdminOverviewStats>("/admin/overview", {
      params: toParams(filters),
    }),

  getTimeSeries: (filters?: AdminFiltersParams) =>
    client.get<TimeSeriesPoint[]>("/admin/timeseries", {
      params: toParams(filters),
    }),

  getLanguageDistribution: (filters?: AdminFiltersParams) =>
    client.get<LanguageDistribution[]>("/admin/language-distribution", {
      params: toParams(filters),
    }),

  getTopTags: (limit = 10, filters?: AdminFiltersParams) =>
    client.get<TagStats[]>("/admin/top-tags", {
      params: { limit, ...toParams(filters) },
    }),

  getScoreHistogram: (bins = 10, filters?: AdminFiltersParams) =>
    client.get<ScoreHistogramBin[]>("/admin/score-histogram", {
      params: { bins, ...toParams(filters) },
    }),

  getSourcesPerformance: (filters?: AdminFiltersParams) =>
    client.get<SourcePerformance[]>("/admin/sources-performance", {
      params: toParams(filters),
    }),

  getPopularArticles: (limit = 10, filters?: AdminFiltersParams) =>
    client.get<any[]>("/admin/popular-articles", {
      params: { limit, ...toParams(filters) },
    }),

  getUserStats: () => client.get<any>("/admin/user-stats"),

  getArticleStatusDistribution: (filters?: AdminFiltersParams) =>
    client.get<any[]>("/admin/article-status-distribution", {
      params: toParams(filters),
    }),
};
