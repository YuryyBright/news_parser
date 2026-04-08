// src/pages/FeedPage.tsx
import { RefreshCw, CheckCheck, Sparkles } from "lucide-react";
import { useFeed, useMarkRead } from "../hooks/useFeed";
import { useFeedStore } from "../store/useFeedStore";
import { useArticlesStore } from "../store/useArticlesStore";
import { ArticleCard } from "../components/articles/ArticleCard";
import { ArticleDrawer } from "../components/articles/ArticleDrawer";
import { cn } from "../lib/utils";

const FILTER_TABS = [
  { key: "all", label: "Всі" },
  { key: "unread", label: "Непрочитані" },
  { key: "read", label: "Прочитані" },
] as const;

export const FeedPage = () => {
  const feedFilter = useFeedStore((s) => s.feedFilter);
  const setFeedFilter = useFeedStore((s) => s.setFeedFilter);
  const isRead = useFeedStore((s) => s.isRead);

  const activeArticleId = useArticlesStore((s) => s.activeArticleId);
  const setActiveArticle = useArticlesStore((s) => s.setActiveArticle);

  const { data: feed, isLoading, refetch, isFetching } = useFeed();
  const markRead = useMarkRead();

  const items = feed?.items ?? [];
  const checkIsRead = (item: any) => {
    // Стаття прочитана, якщо вона є в локальному сторі АБО база каже, що вона прочитана
    return isRead(item.article_id) || item.status === "read";
  };
  const filtered = items.filter((item) => {
    const itemRead = checkIsRead(item);
    if (feedFilter === "unread") return !itemRead;
    if (feedFilter === "read") return itemRead;
    return true;
  });

  const unreadCount = items.filter((item) => !checkIsRead(item)).length;

  const handleOpen = (item: any) => {
    setActiveArticle(item.article_id);
    // Перевіряємо через новий хелпер
    if (!checkIsRead(item)) {
      markRead.mutate(item.article_id);
    }
  };
  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            Фід
            {unreadCount > 0 && (
              <span className="inline-flex items-center justify-center px-2 py-0.5 rounded-full text-xs font-bold bg-blue-500 text-white">
                {unreadCount}
              </span>
            )}
          </h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm mt-0.5">
            {feed?.generated_at
              ? `Оновлено ${new Date(feed.generated_at).toLocaleTimeString("uk")}`
              : "Персоналізовані новини"}
          </p>
        </div>

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
          <RefreshCw className={cn("w-4 h-4", isFetching && "animate-spin")} />
          Оновити
        </button>
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

      {/* Articles grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-40 bg-slate-100 dark:bg-slate-800 rounded-xl animate-pulse"
            />
          ))}
        </div>
      ) : filtered.length === 0 ? (
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
                Фід порожній
              </p>
              <p className="text-sm mt-1">Додайте джерела або оновіть фід</p>
            </>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((item) => (
            <ArticleCard
              key={item.article_id}
              article={{
                id: item.article_id,
                title: item.title,
                url: item.url,
                language: item.language,
                status: "new",
                relevance_score: item.relevance_score,
                published_at: item.published_at,
                created_at: item.published_at ?? "",
                tags: [],
                original_body: item.original_body,
                original_title: item.original_title,
                body: null,
              }}
              // Залишаємо ТІЛЬКИ НОВИЙ варіант:
              isRead={checkIsRead(item)}
              onClick={() => handleOpen(item)}
            />
          ))}
        </div>
      )}

      <ArticleDrawer
        articleId={activeArticleId}
        onClose={() => setActiveArticle(null)}
      />
    </div>
  );
};
