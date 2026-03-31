// src/hooks/useArticles.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { articlesApi } from "../api";
import type { ArticleFilter, FeedbackPayload } from "../api/types";

// ── Queries ───────────────────────────────────────────────────────────────────

export const useArticles = (filters: ArticleFilter) =>
  useQuery({
    queryKey: ["articles", filters],
    queryFn: () => articlesApi.list(filters),
    staleTime: 60_000,
  });

export const useArticle = (id: string | null) =>
  useQuery({
    queryKey: ["article", id],
    queryFn: () => articlesApi.get(id!),
    enabled: !!id,
    staleTime: 30_000,
  });

// ── Mutations ─────────────────────────────────────────────────────────────────

export const useFeedback = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, liked }: { id: string; liked: boolean }) =>
      articlesApi.feedback(id, {
        user_id:
          import.meta.env.VITE_DEFAULT_USER_ID ??
          "00000000-0000-0000-0000-000000000001",
        liked,
      }),
    onSuccess: (_, { liked }) => {
      toast.success(
        liked ? "👍 Цікаво — враховано!" : "👎 Нецікаво — враховано!",
      );
      qc.invalidateQueries({ queryKey: ["articles"] });
    },
    onError: () => toast.error("Не вдалося зберегти відгук"),
  });
};

export const useExpireArticle = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => articlesApi.expire(id),
    onSuccess: () => {
      toast.success("Статтю позначено як застарілу");
      qc.invalidateQueries({ queryKey: ["articles"] });
    },
  });
};

export const useDeleteArticle = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => articlesApi.delete(id),
    onSuccess: () => {
      toast.success("Статтю видалено");
      qc.invalidateQueries({ queryKey: ["articles"] });
    },
  });
};

export const useAddTags = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, tags }: { id: string; tags: string[] }) =>
      articlesApi.addTags(id, tags),
    onSuccess: (_, { id }) => {
      toast.success("Теги додано");
      qc.invalidateQueries({ queryKey: ["article", id] });
    },
  });
};
