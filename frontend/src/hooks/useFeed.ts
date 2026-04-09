// src/hooks/useFeed.ts
import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { useMemo } from "react";
import { feedApi } from "../api";
import { useFeedStore } from "../store/useFeedStore";
import { UserID, type FeedFilter, type FeedArticle } from "../api/types";

const PAGE_SIZE = 20;

export const useFeed = (filter: FeedFilter = "all") => {
  const query = useInfiniteQuery({
    queryKey: ["feed", UserID, filter],
    queryFn: ({ pageParam = 0 }) =>
      feedApi.get(UserID, { offset: pageParam, limit: PAGE_SIZE, filter }),
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? lastPage.offset + lastPage.limit : undefined,
    initialPageParam: 0,
    // staleTime=0: при кожному фокусі/маунті перевіряємо нові статті.
    // Бекенд кешований (snapshot), тому це не дорого.
    staleTime: 0,
    refetchOnWindowFocus: true,
  });

  // Дедублікуємо статті по article_id з усіх сторінок.
  // Це виправляє зсув offset після markRead: одна й та сама стаття
  // може потрапити на дві сторінки якщо між запитами змінився total.
  const articles = useMemo<FeedArticle[]>(() => {
    const seen = new Set<string>();
    const result: FeedArticle[] = [];
    for (const page of query.data?.pages ?? []) {
      for (const item of page.items) {
        if (!seen.has(item.article_id)) {
          seen.add(item.article_id);
          result.push(item);
        }
      }
    }
    return result;
  }, [query.data]);

  return { ...query, articles };
};

export const useMarkRead = () => {
  const qc = useQueryClient();
  const { markRead } = useFeedStore();
  return useMutation({
    mutationFn: (articleId: string) => feedApi.markRead(UserID, articleId),
    onSuccess: (_, articleId) => {
      markRead(articleId);
      // Інвалідуємо тільки активний фільтр, щоб не скидати інші сторінки
      qc.invalidateQueries({ queryKey: ["feed", UserID] });
    },
  });
};

export const useMarkAllRead = () => {
  const qc = useQueryClient();
  const { markAllRead } = useFeedStore();
  return useMutation({
    mutationFn: (articleIds: string[]) =>
      Promise.all(articleIds.map((id) => feedApi.markRead(UserID, id))),
    onSuccess: (_, articleIds) => {
      markAllRead(articleIds);
      qc.invalidateQueries({ queryKey: ["feed", UserID] });
    },
  });
};
