// src/hooks/useFeed.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { feedApi } from "../api";
import { useFeedStore } from "../store/useFeedStore";

export const useFeed = () => {
  const { userId } = useFeedStore();
  return useQuery({
    queryKey: ["feed", userId],
    queryFn: () => feedApi.get(userId),
    staleTime: 5 * 60_000, // 5 хвилин
  });
};

export const useMarkRead = () => {
  const qc = useQueryClient();
  const { userId, markRead } = useFeedStore();

  return useMutation({
    mutationFn: (articleId: string) => feedApi.markRead(userId, articleId),
    onSuccess: (_, articleId) => {
      markRead(articleId);
      qc.invalidateQueries({ queryKey: ["feed", userId] });
    },
  });
};
