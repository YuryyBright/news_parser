// src/pages/FeedPage.tsx
import { RefreshCw, CheckCheck } from "lucide-react";
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
  // Використовуємо селектори для кращої продуктивності (запобігають зайвим ререндерам)
  const feedFilter = useFeedStore((s) => s.feedFilter);
  const setFeedFilter = useFeedStore((s) => s.setFeedFilter);
  const isRead = useFeedStore((s) => s.isRead);

  const activeArticleId = useArticlesStore((s) => s.activeArticleId);
  const setActiveArticle = useArticlesStore((s) => s.setActiveArticle);

  const { data: feed, isLoading, refetch, isFetching } = useFeed();
  const markRead = useMarkRead();

  const items = feed?.items ?? [];
  const filtered = items.filter((item) => {
    if (feedFilter === "unread") return !isRead(item.article_id);
    if (feedFilter === "read") return isRead(item.article_id);
    return true;
  });

  const handleOpen = (articleId: string) => {
    setActiveArticle(articleId);
    if (!isRead(articleId)) {
      markRead.mutate(articleId); // Відправляємо запит на сервер через hook
      // markRead у useFeedStore зазвичай викликається автоматично через success-callback мутації,
      // або ви можете додати s.markRead(articleId) тут.
    }
  };

  return (
    <div>
      {/* Заголовок сторінки */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            Фід
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
            "disabled:opacity-50",
          )}
        >
          <RefreshCw className={cn("w-4 h-4", isFetching && "animate-spin")} />
          Оновити
        </button>
      </div>

      {/* Таби фільтрації */}
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
          </button>
        ))}
      </div>

      {/* Сітка статей */}
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
          <CheckCheck className="w-12 h-12 mb-3" />
          <p className="text-lg font-medium">Все прочитано!</p>
          <p className="text-sm">У фіді немає нових статей</p>
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
                language: "uk",
                status: "new",
                relevance_score: item.relevance_score,
                published_at: item.published_at,
                created_at: item.published_at ?? "",
                tags: [],
              }}
              isRead={isRead(item.article_id)}
              onClick={() => handleOpen(item.article_id)}
            />
          ))}
        </div>
      )}

      {/* Drawer тепер використовує глобальний стан */}
      <ArticleDrawer
        articleId={activeArticleId}
        onClose={() => setActiveArticle(null)}
      />
    </div>
  );
};
