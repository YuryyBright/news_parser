// src/pages/FeedPage.tsx
import { useEffect, useRef, useState, useCallback } from "react";
import {
  RefreshCw,
  CheckCheck,
  Sparkles,
  Loader2,
  Timer,
  X,
} from "lucide-react";
import { useFeed, useMarkRead, useMarkAllRead } from "../hooks/useFeed";
import { useFeedStore } from "../store/useFeedStore";
import { useArticlesStore } from "../store/useArticlesStore";
import { ArticleCard } from "../components/articles/ArticleCard";
import { ArticleDrawer } from "../components/articles/ArticleDrawer";
import { cn } from "../lib/utils";
import type { FeedFilter } from "../api/types";

// ─── Constants ─────────────────────────────────────────────────────────────

const FILTER_TABS: { key: FeedFilter; label: string }[] = [
  { key: "all", label: "Всі" },
  { key: "unread", label: "Непрочитані" },
  { key: "read", label: "Прочитані" },
];

const AUTO_REFRESH_OPTIONS: { label: string; value: number | null }[] = [
  { label: "1хв", value: 60 },
  { label: "5хв", value: 300 },
  { label: "15хв", value: 900 },
  { label: "30хв", value: 1800 },
  { label: "Вимк", value: null },
];

const LANGUAGE_META: Record<string, { label: string; flag: string }> = {
  uk: { label: "Українська", flag: "🇺🇦" },
  en: { label: "English", flag: "🇬🇧" },
  de: { label: "Deutsch", flag: "🇩🇪" },
  fr: { label: "Français", flag: "🇫🇷" },
  pl: { label: "Polski", flag: "🇵🇱" },
  ru: { label: "Русский", flag: "🇷🇺" },
};

const getLangMeta = (lang: string) =>
  LANGUAGE_META[lang?.toLowerCase()] ?? {
    label: lang?.toUpperCase() ?? "??",
    flag: "🌐",
  };

// ─── Auto-refresh hook ──────────────────────────────────────────────────────

const STORAGE_KEY = "feed_auto_refresh_interval";

function useAutoRefresh(onRefresh: () => void) {
  const stored =
    typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
  const parsedStored =
    stored === "null" ? null : stored ? Number(stored) : null;

  const [intervalSec, setIntervalSec] = useState<number | null>(parsedStored);
  const [countdown, setCountdown] = useState<number | null>(parsedStored);
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearTimer = useCallback(() => {
    if (countdownRef.current) {
      clearInterval(countdownRef.current);
      countdownRef.current = null;
    }
  }, []);

  const startTimer = useCallback(
    (sec: number) => {
      clearTimer();
      setCountdown(sec);
      countdownRef.current = setInterval(() => {
        setCountdown((prev) => {
          if (prev === null) return null;
          if (prev <= 1) {
            onRefresh();
            return sec;
          }
          return prev - 1;
        });
      }, 1000);
    },
    [clearTimer, onRefresh],
  );

  const setAutoRefresh = useCallback(
    (sec: number | null) => {
      setIntervalSec(sec);
      localStorage.setItem(STORAGE_KEY, String(sec));
      clearTimer();
      if (sec !== null) {
        startTimer(sec);
      } else {
        setCountdown(null);
      }
    },
    [clearTimer, startTimer],
  );

  useEffect(() => {
    if (intervalSec !== null) {
      startTimer(intervalSec);
    }
    return clearTimer;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const formatCountdown = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return m > 0 ? `${m}:${String(s).padStart(2, "0")}` : `${s}с`;
  };

  return { intervalSec, countdown, setAutoRefresh, formatCountdown };
}

// ─── Component ──────────────────────────────────────────────────────────────

export const FeedPage = () => {
  const feedFilter = useFeedStore((s) => s.feedFilter);
  const setFeedFilter = useFeedStore((s) => s.setFeedFilter);
  const isRead = useFeedStore((s) => s.isRead);
  const markReadStore = useFeedStore((s) => s.markRead);

  const activeArticleId = useArticlesStore((s) => s.activeArticleId);
  const setActiveArticle = useArticlesStore((s) => s.setActiveArticle);

  const {
    data,
    articles: allItems,
    isLoading,
    isFetching,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    refetch,
  } = useFeed(feedFilter);

  const markRead = useMarkRead();
  const markAllRead = useMarkAllRead();

  // Language filter — only active on "unread" tab
  const [activeLang, setActiveLang] = useState<string | null>(null);

  // Auto-refresh timer
  const [showTimerPanel, setShowTimerPanel] = useState(false);
  const { intervalSec, countdown, setAutoRefresh, formatCountdown } =
    useAutoRefresh(useCallback(() => refetch(), [refetch]));

  // ─── Derived data ────────────────────────────────────────────────────────

  const total = data?.pages[0]?.total ?? 0;

  const checkIsRead = (item: any) =>
    isRead(item.article_id) || item.status === "read";

  const unreadItems = allItems.filter((item) => !checkIsRead(item));

  const unreadCount =
    feedFilter === "all"
      ? unreadItems.length
      : feedFilter === "unread"
        ? total
        : 0;

  // Available languages derived from unread items
  const availableLangs = Array.from(
    new Set(
      unreadItems.map((item) => item.language?.toLowerCase()).filter(Boolean),
    ),
  ) as string[];

  // Items to render — apply lang filter only on "unread" tab
  const filteredItems =
    feedFilter === "unread" && activeLang
      ? allItems.filter(
          (item) =>
            !checkIsRead(item) && item.language?.toLowerCase() === activeLang,
        )
      : allItems;

  // Group by language when on "unread" tab and no specific lang selected
  const groupByLang =
    feedFilter === "unread" && !activeLang && availableLangs.length > 1;

  const groupedItems = groupByLang
    ? availableLangs
        .map((lang) => ({
          lang,
          items: allItems.filter(
            (item) =>
              !checkIsRead(item) && item.language?.toLowerCase() === lang,
          ),
        }))
        .filter((g) => g.items.length > 0)
    : null;

  // ─── Intersection Observer ───────────────────────────────────────────────

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

  // Reset lang filter when switching away from "unread"
  useEffect(() => {
    if (feedFilter !== "unread") setActiveLang(null);
  }, [feedFilter]);

  // ─── Handlers ────────────────────────────────────────────────────────────

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
    const unreadIds = allItems
      .filter((item) => !checkIsRead(item))
      .map((item) => item.article_id);
    if (unreadIds.length === 0) return;
    markAllRead.mutate(unreadIds);
  };

  // ─── Article card renderer ───────────────────────────────────────────────

  const renderItem = (item: any) => {
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

          {/* Auto-refresh toggle button */}
          <div className="relative">
            <button
              onClick={() => setShowTimerPanel((v) => !v)}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-all",
                intervalSec !== null
                  ? "border-blue-300 dark:border-blue-700 text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20"
                  : "border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800",
              )}
            >
              <Timer className="w-4 h-4" />
              {countdown !== null ? (
                <span className="tabular-nums">
                  {formatCountdown(countdown)}
                </span>
              ) : (
                "Авто"
              )}
            </button>

            {/* Timer panel */}
            {showTimerPanel && (
              <div className="absolute right-0 top-full mt-2 z-20 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl shadow-lg p-3 w-64">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                    Автооновлення
                  </span>
                  <button
                    onClick={() => setShowTimerPanel(false)}
                    className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {AUTO_REFRESH_OPTIONS.map(({ label, value }) => (
                    <button
                      key={label}
                      onClick={() => {
                        setAutoRefresh(value);
                        setShowTimerPanel(false);
                      }}
                      className={cn(
                        "px-3 py-1.5 rounded-lg text-sm font-medium border transition-all",
                        intervalSec === value
                          ? "bg-blue-500 border-blue-500 text-white"
                          : "border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800",
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                {intervalSec !== null && countdown !== null && (
                  <p className="text-xs text-slate-400 dark:text-slate-500 mt-2">
                    Наступне оновлення через{" "}
                    <span className="tabular-nums font-medium text-blue-500">
                      {formatCountdown(countdown)}
                    </span>
                  </p>
                )}
              </div>
            )}
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
      <div className="flex items-center gap-1 mb-4 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg w-fit">
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

      {/* Language filter chips — only on "unread" tab */}
      {feedFilter === "unread" && availableLangs.length > 1 && (
        <div className="flex items-center gap-2 mb-4 flex-wrap">
          <button
            onClick={() => setActiveLang(null)}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border transition-all",
              activeLang === null
                ? "bg-slate-800 dark:bg-white border-slate-800 dark:border-white text-white dark:text-slate-900"
                : "border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400 hover:border-slate-300 dark:hover:border-slate-600",
            )}
          >
            Всі мови
          </button>
          {availableLangs.map((lang) => {
            const meta = getLangMeta(lang);
            const count = unreadItems.filter(
              (item) => item.language?.toLowerCase() === lang,
            ).length;
            return (
              <button
                key={lang}
                onClick={() => setActiveLang(activeLang === lang ? null : lang)}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border transition-all",
                  activeLang === lang
                    ? "bg-slate-800 dark:bg-white border-slate-800 dark:border-white text-white dark:text-slate-900"
                    : "border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400 hover:border-slate-300 dark:hover:border-slate-600",
                )}
              >
                <span>{meta.flag}</span>
                {meta.label}
                <span
                  className={cn(
                    "inline-flex items-center justify-center min-w-[16px] h-4 px-1 rounded-full text-[10px] font-bold",
                    activeLang === lang
                      ? "bg-white/20 text-white dark:bg-black/20 dark:text-slate-900"
                      : "bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400",
                  )}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>
      )}

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
      ) : filteredItems.length === 0 &&
        !groupedItems?.some((g) => g.items.length > 0) ? (
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
      ) : groupedItems ? (
        /* Grouped by language sections */
        <div className="flex flex-col gap-6">
          {groupedItems.map(({ lang, items }) => {
            const meta = getLangMeta(lang);
            return (
              <div key={lang}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-base">{meta.flag}</span>
                  <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                    {meta.label}
                  </span>
                  <span className="text-xs text-slate-400 dark:text-slate-500">
                    · {items.length}
                  </span>
                  <button
                    onClick={() => setActiveLang(lang)}
                    className="ml-auto text-xs text-blue-500 hover:underline"
                  >
                    Тільки ця мова
                  </button>
                </div>
                <div className="flex flex-col divide-y divide-slate-100 dark:divide-slate-800 border border-slate-100 dark:border-slate-800 rounded-xl overflow-hidden">
                  {items.map(renderItem)}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* Flat list (filtered or non-unread tabs) */
        <div className="flex flex-col divide-y divide-slate-100 dark:divide-slate-800 border border-slate-100 dark:border-slate-800 rounded-xl overflow-hidden">
          {filteredItems.map(renderItem)}
        </div>
      )}

      {/* Sentinel div — intersection observer target */}
      <div ref={sentinelRef} className="h-4" />

      {isFetchingNextPage && (
        <div className="flex items-center justify-center py-6 text-slate-400">
          <Loader2 className="w-5 h-5 animate-spin mr-2" />
          <span className="text-sm">Завантаження...</span>
        </div>
      )}
      {!hasNextPage && allItems.length > 0 && (
        <p className="text-center text-xs text-slate-400 dark:text-slate-600 py-6">
          Всі {total} статей завантажено
        </p>
      )}

      <ArticleDrawer
        articleId={activeArticleId}
        onClose={() => setActiveArticle(null)}
      />
    </div>
  );
};
