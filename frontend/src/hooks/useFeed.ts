// src/hooks/useFeed.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { feedApi } from "../api";
import { useFeedStore } from "../store/useFeedStore";
import { UserID } from "../api/types";
export const useFeed = () => {
  return useQuery({
    queryKey: ["feed", UserID],
    queryFn: () => feedApi.get(UserID),
    staleTime: 5 * 60_000, // 5 хвилин
  });
};

export const useMarkRead = () => {
  const qc = useQueryClient();
  const { markRead } = useFeedStore();

  return useMutation({
    mutationFn: (articleId: string) => feedApi.markRead(UserID, articleId),
    onSuccess: (_, articleId) => {
      markRead(articleId);
      qc.invalidateQueries({ queryKey: ["feed", UserID] });
    },
  });
};
