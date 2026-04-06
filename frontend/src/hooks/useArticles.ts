// src/hooks/useArticles.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { articlesApi } from "../api/articles";
import type { ArticleFilter } from "../api/types";

// ── Keys ──────────────────────────────────────────────────────────────────────

export const articleKeys = {
  all: ["articles"] as const,
  lists: () => [...articleKeys.all, "list"] as const,
  list: (filters: ArticleFilter) => [...articleKeys.lists(), filters] as const,
  search: (q: string, params?: object) =>
    [...articleKeys.all, "search", q, params] as const,
  detail: (id: string) => [...articleKeys.all, "detail", id] as const,
};

// ── LIST with pagination ──────────────────────────────────────────────────────

export const useArticles = (filters: ArticleFilter = {}) => {
  return useQuery({
    queryKey: articleKeys.list(filters),
    queryFn: () => articlesApi.list(filters),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });
};

// ── SEARCH ────────────────────────────────────────────────────────────────────

export const useArticleSearch = (
  q: string,
  params?: { language?: string; status?: string },
) => {
  return useQuery({
    queryKey: articleKeys.search(q, params),
    queryFn: () => articlesApi.search(q, params),
    enabled: q.trim().length >= 2,
    staleTime: 60_000,
  });
};

// ── DETAIL ────────────────────────────────────────────────────────────────────

export const useArticle = (id: string | null) => {
  return useQuery({
    queryKey: articleKeys.detail(id!),
    queryFn: () => articlesApi.get(id!),
    enabled: !!id,
    staleTime: 60_000,
  });
};

// ── FEEDBACK ──────────────────────────────────────────────────────────────────

export const useFeedback = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, liked }: { id: string; liked: boolean }) =>
      articlesApi.feedback(id, {
        user_id: "00000000-0000-0000-0000-000000000001",
        liked,
      }),
    onSuccess: (_, { liked }) => {
      toast.success(
        liked ? "👍 Відмічено як цікаве" : "👎 Відмічено як нецікаве",
      );
      qc.invalidateQueries({ queryKey: articleKeys.lists() });
    },
    onError: () => toast.error("Не вдалось зберегти оцінку"),
  });
};

// ── EXPIRE ────────────────────────────────────────────────────────────────────

export const useExpireArticle = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => articlesApi.expire(id),
    onSuccess: () => {
      toast.success("Статтю приховано");
      qc.invalidateQueries({ queryKey: articleKeys.lists() });
    },
    onError: () => toast.error("Не вдалось приховати статтю"),
  });
};

// ── INGEST URL ────────────────────────────────────────────────────────────────

export const useIngestUrl = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (url: string) => articlesApi.ingestUrl({ url }),
    onSuccess: (data) => {
      toast.success(
        `Статтю поставлено в чергу (task: ${data.task_id.slice(0, 8)}...)`,
      );
      // Через 3с перечитуємо список — стаття може вже з'явитись
      setTimeout(
        () => qc.invalidateQueries({ queryKey: articleKeys.lists() }),
        3000,
      );
    },
    onError: () => toast.error("Не вдалось поставити статтю в чергу"),
  });
};
