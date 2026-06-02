// src/hooks/useGeneratedNews.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  generatedNewsApi,
  type GeneratedNewsFilter,
} from "../api/generatedNews";
import toast from "react-hot-toast";

export const useGeneratedNews = (filters: GeneratedNewsFilter = {}) =>
  useQuery({
    queryKey: ["generated-news", filters],
    queryFn: () => generatedNewsApi.list(filters),
    staleTime: 30_000,
  });

export const usePublishNews = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => generatedNewsApi.publish(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["generated-news"] });
      toast.success("Опубліковано в Telegram!");
    },
    onError: () => toast.error("Помилка публікації"),
  });
};
