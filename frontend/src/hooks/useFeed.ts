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
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
  });

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
    onMutate: (articleId) => {
      // Оптимістично оновлюємо кеш — без жодного HTTP запиту
      markRead(articleId);
      qc.setQueriesData<ReturnType<typeof useInfiniteQuery>["data"]>(
        { queryKey: ["feed", UserID] },
        (old: any) => {
          if (!old) return old;
          return {
            ...old,
            pages: old.pages.map((page: any) => ({
              ...page,
              items: page.items.map((item: FeedArticle) =>
                item.article_id === articleId
                  ? { ...item, status: "read" as const }
                  : item,
              ),
            })),
          };
        },
      );
    },
    onError: () => {
      // При помилці — інвалідуємо щоб відновити реальний стан
      qc.invalidateQueries({ queryKey: ["feed", UserID] });
    },
    // onSuccess навмисно відсутній — invalidate не потрібен,
    // кеш вже оновлено оптимістично в onMutate
  });
};

export const useMarkAllRead = () => {
  const qc = useQueryClient();
  const { markAllRead } = useFeedStore();
  return useMutation({
    mutationFn: (articleIds: string[]) =>
      Promise.all(articleIds.map((id) => feedApi.markRead(UserID, id))),
    onMutate: (articleIds) => {
      const idSet = new Set(articleIds);
      markAllRead(articleIds);
      qc.setQueriesData<ReturnType<typeof useInfiniteQuery>["data"]>(
        { queryKey: ["feed", UserID] },
        (old: any) => {
          if (!old) return old;
          return {
            ...old,
            pages: old.pages.map((page: any) => ({
              ...page,
              items: page.items.map((item: FeedArticle) =>
                idSet.has(item.article_id)
                  ? { ...item, status: "read" as const }
                  : item,
              ),
            })),
          };
        },
      );
    },
    onError: () => {
      qc.invalidateQueries({ queryKey: ["feed", UserID] });
    },
  });
};
