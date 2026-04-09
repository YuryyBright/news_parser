// src/pages/FeedPage.tsx
import { useEffect, useRef } from "react";
import { RefreshCw, CheckCheck, Sparkles, Loader2 } from "lucide-react";
import { useFeed, useMarkRead, useMarkAllRead } from "../hooks/useFeed";
import { useFeedStore } from "../store/useFeedStore";
import { useArticlesStore } from "../store/useArticlesStore";
import { ArticleCard } from "../components/articles/ArticleCard";
import { ArticleDrawer } from "../components/articles/ArticleDrawer";
import { cn } from "../lib/utils";
import type { FeedFilter } from "../api/types";

const FILTER_TABS: { key: FeedFilter; label: string }[] = [
  { key: "all", label: "Всі" },
  { key: "unread", label: "Непрочитані" },
  { key: "read", label: "Прочитані" },
];

export const FeedPage = () => {
  const feedFilter = useFeedStore((s) => s.feedFilter);
  const setFeedFilter = useFeedStore((s) => s.setFeedFilter);
  const isRead = useFeedStore((s) => s.isRead);
  const markReadStore = useFeedStore((s) => s.markRead);

  const activeArticleId = useArticlesStore((s) => s.activeArticleId);
  const setActiveArticle = useArticlesStore((s) => s.setActiveArticle);

  const {
    data,
    isLoading,
    isFetching,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    refetch,
  } = useFeed(feedFilter);

  const markRead = useMarkRead();
  const markAllRead = useMarkAllRead();

  const items = data?.pages.flatMap((p) => p.items) ?? [];
  const total = data?.pages[0]?.total ?? 0;

  const checkIsRead = (item: any) =>
    isRead(item.article_id) || item.status === "read";

  const unreadCount =
    feedFilter === "all"
      ? items.filter((item) => !checkIsRead(item)).length
      : feedFilter === "unread"
        ? total
        : 0;

  // ─── Intersection Observer ────────────────────────────────────────────────
  const sentinelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage();
        }
      },
      { rootMargin: "200px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  // ─── Handlers ─────────────────────────────────────────────────────────────

  const handleOpen = (item: any) => {
    setActiveArticle(item.article_id);
    if (!checkIsRead(item)) {
      markRead.mutate(item.article_id);
      markReadStore(item.article_id);
    }
  };

  const handleMarkArticleRead = (e: React.MouseEvent, item: any) => {
    e.stopPropagation();
    if (!checkIsRead(item)) {
      markRead.mutate(item.article_id);
      markReadStore(item.article_id);
    }
  };

  const handleMarkAllRead = () => {
    const unreadIds = items
      .filter((item) => !checkIsRead(item))
      .map((item) => item.article_id);
    if (unreadIds.length === 0) return;
    markAllRead.mutate(unreadIds);
  };

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            Стрічка
            {unreadCount > 0 && (
              <span className="inline-flex items-center justify-center px-2 py-0.5 rounded-full text-xs font-bold bg-blue-500 text-white">
                {unreadCount}
              </span>
            )}
          </h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm mt-0.5">
            {data?.pages[0]?.generated_at
              ? `Оновлено ${new Date(data.pages[0].generated_at).toLocaleTimeString("uk")}`
              : "Персоналізовані новини"}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {feedFilter !== "read" && unreadCount > 0 && (
            <button
              onClick={handleMarkAllRead}
              disabled={markAllRead.isPending}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-all",
                "border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-400",
                "hover:bg-emerald-50 dark:hover:bg-emerald-900/30",
                "disabled:opacity-50 disabled:cursor-not-allowed",
              )}
            >
              <CheckCheck className="w-4 h-4" />
              Прочитати всі
            </button>
          )}
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-all",
              "border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300",
              "hover:bg-slate-100 dark:hover:bg-slate-800",
              "disabled:opacity-50 disabled:cursor-not-allowed",
            )}
          >
            <RefreshCw
              className={cn(
                "w-4 h-4",
                isFetching && !isFetchingNextPage && "animate-spin",
              )}
            />
            Оновити
          </button>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex items-center gap-1 mb-6 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg w-fit">
        {FILTER_TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setFeedFilter(key)}
            className={cn(
              "px-4 py-1.5 rounded-md text-sm font-medium transition-all",
              feedFilter === key
                ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-sm"
                : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200",
            )}
          >
            {label}
            {key === "unread" && unreadCount > 0 && (
              <span className="ml-1.5 inline-flex items-center justify-center w-4 h-4 rounded-full text-[10px] font-bold bg-blue-500 text-white">
                {unreadCount > 9 ? "9+" : unreadCount}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Feed list */}
      {isLoading ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="h-16 bg-slate-100 dark:bg-slate-800 rounded-xl animate-pulse"
            />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-slate-400">
          {feedFilter === "unread" ? (
            <>
              <CheckCheck className="w-12 h-12 mb-3 text-emerald-500" />
              <p className="text-lg font-medium text-slate-700 dark:text-slate-300">
                Все прочитано!
              </p>
              <p className="text-sm mt-1">Нових статей у фіді немає</p>
              <button
                onClick={() => setFeedFilter("all")}
                className="mt-4 text-sm text-blue-500 hover:underline"
              >
                Показати всі статті
              </button>
            </>
          ) : (
            <>
              <Sparkles className="w-12 h-12 mb-3" />
              <p className="text-lg font-medium text-slate-700 dark:text-slate-300">
                Стрічка порожня
              </p>
              <p className="text-sm mt-1">Додайте джерела або оновіть фід</p>
            </>
          )}
        </div>
      ) : (
        <>
          <div className="flex flex-col divide-y divide-slate-100 dark:divide-slate-800 border border-slate-100 dark:border-slate-800 rounded-xl overflow-hidden">
            {items.map((item) => {
              const read = checkIsRead(item);
              return (
                <ArticleCard
                  key={item.article_id}
                  variant="feed"
                  isRead={read}
                  onClick={() => handleOpen(item)}
                  onMarkRead={(e) => handleMarkArticleRead(e, item)}
                  article={{
                    id: item.article_id,
                    title: item.title,
                    url: item.url,
                    language: item.language,
                    status: read ? "accepted" : "new",
                    relevance_score: item.relevance_score,
                    published_at: item.published_at,
                    created_at: item.published_at ?? "",
                    tags: [],
                    original_body: null,
                    original_title: null,
                    body: null,
                  }}
                />
              );
            })}
          </div>

          {/* Sentinel div — intersection observer target */}
          <div ref={sentinelRef} className="h-4" />

          {isFetchingNextPage && (
            <div className="flex items-center justify-center py-6 text-slate-400">
              <Loader2 className="w-5 h-5 animate-spin mr-2" />
              <span className="text-sm">Завантаження...</span>
            </div>
          )}
          {!hasNextPage && items.length > 0 && (
            <p className="text-center text-xs text-slate-400 dark:text-slate-600 py-6">
              Всі {total} статей завантажено
            </p>
          )}
        </>
      )}

      <ArticleDrawer
        articleId={activeArticleId}
        onClose={() => setActiveArticle(null)}
      />
    </div>
  );
};
