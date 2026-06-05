// src/hooks/useAdmin.ts
import { useQuery } from "@tanstack/react-query";
import { adminApi } from "../api/admin";

export interface AdminFiltersParams {
  from_date?: string;
  to_date?: string;
  language?: string;
}

export const adminKeys = {
  all: ["admin"] as const,
  overview: (f?: AdminFiltersParams) =>
    [...adminKeys.all, "overview", f] as const,
  timeSeries: (f?: AdminFiltersParams) =>
    [...adminKeys.all, "timeseries", f] as const,
  languageDist: (f?: AdminFiltersParams) =>
    [...adminKeys.all, "language", f] as const,
  topTags: (limit: number, f?: AdminFiltersParams) =>
    [...adminKeys.all, "topTags", limit, f] as const,
  scoreHistogram: (bins: number, f?: AdminFiltersParams) =>
    [...adminKeys.all, "histogram", bins, f] as const,
  sourcesPerformance: (f?: AdminFiltersParams) =>
    [...adminKeys.all, "sources", f] as const,
  popularArticles: (limit: number, f?: AdminFiltersParams) =>
    [...adminKeys.all, "popular", limit, f] as const,
  userStats: () => [...adminKeys.all, "users"] as const,
  articleStatusDist: (f?: AdminFiltersParams) =>
    [...adminKeys.all, "status", f] as const,
};

export const useAdminOverview = (filters?: AdminFiltersParams) =>
  useQuery({
    queryKey: adminKeys.overview(filters),
    queryFn: () => adminApi.getOverview(filters).then((r) => r.data),
  });

export const useAdminTimeSeries = (filters?: AdminFiltersParams) =>
  useQuery({
    queryKey: adminKeys.timeSeries(filters),
    queryFn: () => adminApi.getTimeSeries(filters).then((r) => r.data),
  });

export const useLanguageDistribution = (filters?: AdminFiltersParams) =>
  useQuery({
    queryKey: adminKeys.languageDist(filters),
    queryFn: () =>
      adminApi.getLanguageDistribution(filters).then((r) => r.data),
  });

export const useTopTags = (limit = 10, filters?: AdminFiltersParams) =>
  useQuery({
    queryKey: adminKeys.topTags(limit, filters),
    queryFn: () => adminApi.getTopTags(limit, filters).then((r) => r.data),
  });

export const useScoreHistogram = (bins = 10, filters?: AdminFiltersParams) =>
  useQuery({
    queryKey: adminKeys.scoreHistogram(bins, filters),
    queryFn: () =>
      adminApi.getScoreHistogram(bins, filters).then((r) => r.data),
  });

export const useSourcesPerformance = (filters?: AdminFiltersParams) =>
  useQuery({
    queryKey: adminKeys.sourcesPerformance(filters),
    queryFn: () => adminApi.getSourcesPerformance(filters).then((r) => r.data),
  });

export const usePopularArticles = (limit = 10, filters?: AdminFiltersParams) =>
  useQuery({
    queryKey: adminKeys.popularArticles(limit, filters),
    queryFn: () =>
      adminApi.getPopularArticles(limit, filters).then((r) => r.data),
  });

export const useUserStats = () =>
  useQuery({
    queryKey: adminKeys.userStats(),
    queryFn: () => adminApi.getUserStats().then((r) => r.data),
  });

export const useArticleStatusDistribution = (filters?: AdminFiltersParams) =>
  useQuery({
    queryKey: adminKeys.articleStatusDist(filters),
    queryFn: () =>
      adminApi.getArticleStatusDistribution(filters).then((r) => r.data),
  });
