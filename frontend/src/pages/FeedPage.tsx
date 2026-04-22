// src/pages/FeedPage.tsx
import { useEffect, useRef, useState, useCallback } from "react";
import {
  RefreshCw,
  CheckCheck,
  Sparkles,
  Loader2,
  Timer,
  X,
  SlidersHorizontal,
  ArrowUpDown,
  Tag,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useFeed, useMarkRead, useMarkAllRead } from "../hooks/useFeed";
import { useFeedStore } from "../store/useFeedStore";
import { useArticlesStore } from "../store/useArticlesStore";
import { ArticleCard } from "../components/articles/ArticleCard";
import { ArticleDrawer } from "../components/articles/ArticleDrawer";
import { cn } from "../lib/utils";
// ─── Shared language helpers (single source of truth) ────────────────────────
import { getLangMeta, flagImgProps } from "../lib/languages";
import type { FeedFilter } from "../api/types";

// ─── Constants ───────────────────────────────────────────────────────────────

const FEED_FILTER_TABS: { key: FeedFilter; label: string }[] = [
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

const SORT_OPTIONS: { label: string; value: "date" | "score" }[] = [
  { label: "За датою", value: "date" },
  { label: "За релевантністю", value: "score" },
];

// ─── Auto-refresh hook ────────────────────────────────────────────────────────

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
      if (sec !== null) startTimer(sec);
      else setCountdown(null);
    },
    [clearTimer, startTimer],
  );

  useEffect(() => {
    if (intervalSec !== null) startTimer(intervalSec);
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

// ─── Filter state ─────────────────────────────────────────────────────────────

interface FilterState {
  minScore: number;
  sortBy: "date" | "score";
  langs: string[];
  tags: string[];
}

const DEFAULT_FILTERS: FilterState = {
  minScore: 0,
  sortBy: "date",
  langs: [],
  tags: [],
};

// ─── Flag image component ─────────────────────────────────────────────────────

const FlagImg = ({ lang, className }: { lang: string; className?: string }) => {
  const meta = getLangMeta(lang);
  if (!meta.country) return null;
  return (
    <img
      {...flagImgProps(meta.country)}
      alt={meta.label}
      className={cn("inline-block rounded-sm object-cover", className)}
    />
  );
};

// ─── Filter panel ─────────────────────────────────────────────────────────────

interface FilterPanelProps {
  open: boolean;
  onClose: () => void;
  filters: FilterState;
  onChange: (f: FilterState) => void;
  availableLangs: string[];
  availableTags: string[];
}

const FilterPanel = ({
  open,
  onClose,
  filters,
  onChange,
  availableLangs,
  availableTags,
}: FilterPanelProps) => {
  const [draft, setDraft] = useState<FilterState>(filters);

  useEffect(() => {
    if (open) setDraft(filters);
  }, [open, filters]);

  const toggleLang = (lang: string) =>
    setDraft((d) => ({
      ...d,
      langs: d.langs.includes(lang)
        ? d.langs.filter((l) => l !== lang)
        : [...d.langs, lang],
    }));

  const toggleTag = (tag: string) =>
    setDraft((d) => ({
      ...d,
      tags: d.tags.includes(tag)
        ? d.tags.filter((t) => t !== tag)
        : [...d.tags, tag],
    }));

  const hasChanges =
    draft.minScore !== filters.minScore ||
    draft.sortBy !== filters.sortBy ||
    JSON.stringify([...draft.langs].sort()) !==
      JSON.stringify([...filters.langs].sort()) ||
    JSON.stringify([...draft.tags].sort()) !==
      JSON.stringify([...filters.tags].sort());

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 bg-black/20 dark:bg-black/40 z-40 backdrop-blur-[2px]"
            onClick={onClose}
          />

          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 320 }}
            className={cn(
              "fixed right-0 top-0 bottom-0 z-50 w-80 max-w-[90vw]",
              "bg-white dark:bg-slate-900",
              "border-l border-slate-200 dark:border-slate-800",
              "flex flex-col shadow-2xl",
            )}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 dark:border-slate-800 flex-shrink-0">
              <span className="text-sm font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                <SlidersHorizontal className="w-4 h-4" />
                Фільтри
              </span>
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto p-5 space-y-6">
              {/* Sort */}
              <div>
                <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2.5">
                  Сортування
                </label>
                <div className="flex gap-2">
                  {SORT_OPTIONS.map(({ label, value }) => (
                    <button
                      key={value}
                      onClick={() => setDraft((d) => ({ ...d, sortBy: value }))}
                      className={cn(
                        "flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium border transition-all",
                        draft.sortBy === value
                          ? "bg-slate-900 dark:bg-white border-slate-900 dark:border-white text-white dark:text-slate-900"
                          : "border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400 hover:border-slate-300",
                      )}
                    >
                      <ArrowUpDown className="w-3 h-3" />
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Score slider */}
              <div>
                <div className="flex items-center justify-between mb-2.5">
                  <label className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                    Мін. релевантність
                  </label>
                  <span className="text-sm font-mono font-semibold text-slate-900 dark:text-white tabular-nums">
                    {draft.minScore.toFixed(2)}
                  </span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={draft.minScore}
                  onChange={(e) =>
                    setDraft((d) => ({
                      ...d,
                      minScore: parseFloat(e.target.value),
                    }))
                  }
                  className={cn(
                    "w-full h-1.5 rounded-full appearance-none cursor-pointer",
                    "bg-slate-200 dark:bg-slate-700",
                    "[&::-webkit-slider-thumb]:appearance-none",
                    "[&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4",
                    "[&::-webkit-slider-thumb]:rounded-full",
                    "[&::-webkit-slider-thumb]:bg-slate-900 dark:[&::-webkit-slider-thumb]:bg-white",
                    "[&::-webkit-slider-thumb]:shadow-sm",
                  )}
                />
                <div className="flex justify-between mt-1.5">
                  <span className="text-[10px] text-slate-400">0.00</span>
                  <span className="text-[10px] text-slate-400">0.50</span>
                  <span className="text-[10px] text-slate-400">1.00</span>
                </div>
              </div>

              {/* Languages */}
              {availableLangs.length > 1 && (
                <div>
                  <div className="flex items-center justify-between mb-2.5">
                    <label className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                      Мови
                    </label>
                    {draft.langs.length > 0 && (
                      <button
                        onClick={() => setDraft((d) => ({ ...d, langs: [] }))}
                        className="text-[11px] text-blue-500 hover:underline"
                      >
                        Скинути
                      </button>
                    )}
                  </div>
                  <div className="grid grid-cols-2 gap-1.5">
                    {availableLangs.map((lang) => {
                      const meta = getLangMeta(lang);
                      const active = draft.langs.includes(lang);
                      return (
                        <button
                          key={lang}
                          onClick={() => toggleLang(lang)}
                          className={cn(
                            "flex items-center gap-2 px-3 py-2 rounded-lg border transition-all text-left",
                            active
                              ? "bg-slate-900 dark:bg-white border-slate-900 dark:border-white"
                              : "border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600",
                          )}
                        >
                          <FlagImg lang={lang} className="w-5 h-3.5" />
                          <span
                            className={cn(
                              "text-xs font-medium",
                              active
                                ? "text-white dark:text-slate-900"
                                : "text-slate-700 dark:text-slate-300",
                            )}
                          >
                            {meta.label}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Tags */}
              {availableTags.length > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-2.5">
                    <label className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide flex items-center gap-1.5">
                      <Tag className="w-3 h-3" />
                      Теги
                    </label>
                    {draft.tags.length > 0 && (
                      <button
                        onClick={() => setDraft((d) => ({ ...d, tags: [] }))}
                        className="text-[11px] text-blue-500 hover:underline"
                      >
                        Скинути
                      </button>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {availableTags.map((tag) => {
                      const active = draft.tags.includes(tag);
                      return (
                        <button
                          key={tag}
                          onClick={() => toggleTag(tag)}
                          className={cn(
                            "px-2.5 py-1 rounded-full text-xs font-medium border transition-all",
                            active
                              ? "bg-slate-900 dark:bg-white border-slate-900 dark:border-white text-white dark:text-slate-900"
                              : "border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400 hover:border-slate-400 dark:hover:border-slate-500",
                          )}
                        >
                          {tag}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="px-5 py-4 border-t border-slate-100 dark:border-slate-800 flex gap-2 flex-shrink-0">
              <button
                onClick={() => setDraft(DEFAULT_FILTERS)}
                className={cn(
                  "flex-1 py-2 rounded-lg text-sm font-medium border transition-all",
                  "border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400",
                  "hover:bg-slate-50 dark:hover:bg-slate-800",
                )}
              >
                Скинути
              </button>
              <button
                onClick={() => {
                  onChange(draft);
                  onClose();
                }}
                disabled={!hasChanges}
                className={cn(
                  "flex-1 py-2 rounded-lg text-sm font-medium transition-all",
                  "bg-slate-900 dark:bg-white text-white dark:text-slate-900",
                  "hover:bg-slate-700 dark:hover:bg-slate-100",
                  "disabled:opacity-40 disabled:cursor-not-allowed",
                )}
              >
                Застосувати
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

// ─── Language tab bar ─────────────────────────────────────────────────────────

interface LangTabBarProps {
  langs: string[];
  active: string | null;
  counts: Record<string, number>;
  onSelect: (lang: string | null) => void;
}

const LangTabBar = ({ langs, active, counts, onSelect }: LangTabBarProps) => {
  const total = Object.values(counts).reduce((a, b) => a + b, 0);

  return (
    <div className="flex items-center gap-1 overflow-x-auto scrollbar-none pb-0.5 -mx-1 px-1">
      {/* All */}
      <button
        onClick={() => onSelect(null)}
        className={cn(
          "flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all whitespace-nowrap",
          active === null
            ? "bg-slate-900 dark:bg-white border-slate-900 dark:border-white text-white dark:text-slate-900"
            : "border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400 hover:border-slate-300 dark:hover:border-slate-600",
        )}
      >
        Всі
        <span
          className={cn(
            "inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-bold",
            active === null
              ? "bg-white/20 text-white dark:bg-black/15 dark:text-slate-900"
              : "bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400",
          )}
        >
          {total}
        </span>
      </button>

      {/* Divider */}
      <div className="flex-shrink-0 w-px h-4 bg-slate-200 dark:bg-slate-700 mx-0.5" />

      {/* Per-language */}
      {langs.map((lang) => {
        const meta = getLangMeta(lang);
        const count = counts[lang] ?? 0;
        const isActive = active === lang;
        return (
          <button
            key={lang}
            onClick={() => onSelect(isActive ? null : lang)}
            className={cn(
              "flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all whitespace-nowrap",
              isActive
                ? "bg-slate-900 dark:bg-white border-slate-900 dark:border-white text-white dark:text-slate-900"
                : "border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400 hover:border-slate-300 dark:hover:border-slate-600",
            )}
          >
            <FlagImg lang={lang} className="w-5 h-3.5" />
            {meta.label}
            <span
              className={cn(
                "inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-bold",
                isActive
                  ? "bg-white/20 text-white dark:bg-black/15 dark:text-slate-900"
                  : "bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400",
              )}
            >
              {count}
            </span>
          </button>
        );
      })}
    </div>
  );
};

// ─── Chip ─────────────────────────────────────────────────────────────────────

const Chip = ({ label, onRemove }: { label: string; onRemove: () => void }) => (
  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-800">
    {label}
    <button
      onClick={onRemove}
      className="hover:text-blue-800 dark:hover:text-blue-200 transition-colors"
    >
      <X className="w-3 h-3" />
    </button>
  </span>
);

// ─── Main ─────────────────────────────────────────────────────────────────────

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

  const [filterPanelOpen, setFilterPanelOpen] = useState(false);
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [activeLang, setActiveLang] = useState<string | null>(null);
  const [showTimerPanel, setShowTimerPanel] = useState(false);

  const { intervalSec, countdown, setAutoRefresh, formatCountdown } =
    useAutoRefresh(useCallback(() => refetch(), [refetch]));

  // ─── Derived ─────────────────────────────────────────────────────────────

  const total = data?.pages[0]?.total ?? 0;
  const checkIsRead = (item: any) =>
    isRead(item.article_id) || item.status === "read";
  const unreadItems = allItems.filter((item) => !checkIsRead(item));
  const unreadCount = feedFilter === "read" ? 0 : unreadItems.length;

  const availableLangs = Array.from(
    new Set(allItems.map((i) => i.language?.toLowerCase()).filter(Boolean)),
  ) as string[];

  const availableTags = Array.from(
    new Set(allItems.flatMap((i) => i.tags ?? []).filter(Boolean)),
  ) as string[];

  // Per-lang unread counts for tab bar
  const unreadLangCounts = unreadItems.reduce<Record<string, number>>(
    (acc, i) => {
      const l = i.language?.toLowerCase();
      if (l) acc[l] = (acc[l] ?? 0) + 1;
      return acc;
    },
    {},
  );

  const applyFilters = (items: any[]) => {
    let result = items;
    if (filters.minScore > 0)
      result = result.filter(
        (i) => (i.relevance_score ?? i.score ?? 0) >= filters.minScore,
      );
    if (filters.langs.length > 0)
      result = result.filter((i) =>
        filters.langs.includes(i.language?.toLowerCase()),
      );
    if (filters.tags.length > 0)
      result = result.filter((i) =>
        filters.tags.some((t) => (i.tags ?? []).includes(t)),
      );
    return [...result].sort((a, b) => {
      if (filters.sortBy === "score")
        return (
          (b.relevance_score ?? b.score ?? 0) -
          (a.relevance_score ?? a.score ?? 0)
        );
      const ta = a.article_published_at
        ? new Date(a.article_published_at).getTime()
        : 0;
      const tb = b.article_published_at
        ? new Date(b.article_published_at).getTime()
        : 0;
      return tb - ta;
    });
  };

  const basePool = feedFilter === "unread" ? unreadItems : allItems;

  // Apply active lang tab (only when no panel lang filter is set)
  const langFilteredPool =
    feedFilter === "unread" && activeLang && filters.langs.length === 0
      ? basePool.filter((i) => i.language?.toLowerCase() === activeLang)
      : basePool;

  const filteredItems = applyFilters(langFilteredPool);

  // Show lang tabs in unread mode with >1 lang and no panel lang filter active
  const showLangTabs =
    feedFilter === "unread" &&
    availableLangs.length > 1 &&
    filters.langs.length === 0;

  const activeFilterCount =
    (filters.minScore > 0 ? 1 : 0) +
    (filters.langs.length > 0 ? 1 : 0) +
    (filters.tags.length > 0 ? 1 : 0) +
    (filters.sortBy !== "date" ? 1 : 0);

  useEffect(() => {
    if (feedFilter !== "unread") setActiveLang(null);
  }, [feedFilter]);

  // ─── Infinite scroll ──────────────────────────────────────────────────────

  const sentinelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage)
          fetchNextPage();
      },
      { rootMargin: "200px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  // ─── Render item ──────────────────────────────────────────────────────────

  const renderItem = (item: any) => {
    const read = checkIsRead(item);
    return (
      <ArticleCard
        key={item.article_id ?? item.id}
        article={item}
        variant="feed"
        isRead={read}
        onClick={() => setActiveArticle(item.article_id ?? item.id)}
        onMarkRead={
          !read
            ? (e) => {
                e.stopPropagation();
                markReadStore(item.article_id ?? item.id);
                markRead.mutate(item.article_id ?? item.id);
              }
            : undefined
        }
      />
    );
  };

  const isEmpty = !isLoading && filteredItems.length === 0;

  // ─── JSX ──────────────────────────────────────────────────────────────────

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-lg sm:text-xl font-bold text-slate-900 dark:text-white">
            Стрічка
          </h1>
          {total > 0 && (
            <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">
              {total} статей ·{" "}
              {unreadCount > 0 ? `${unreadCount} нових` : "всі прочитані"}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {unreadCount > 0 && (
            <button
              onClick={() =>
                markAllRead.mutate(unreadItems.map((i) => i.article_id))
              }
              disabled={markAllRead.isPending}
              className={cn(
                "flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs sm:text-sm font-medium border transition-all",
                "border-emerald-200 dark:border-emerald-800 text-emerald-600 dark:text-emerald-400",
                "hover:bg-emerald-50 dark:hover:bg-emerald-950 disabled:opacity-50",
              )}
            >
              <CheckCheck className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              <span className="hidden xs:inline">Всі прочитані</span>
            </button>
          )}

          {/* Filters button */}
          <button
            onClick={() => setFilterPanelOpen(true)}
            className={cn(
              "relative flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs sm:text-sm font-medium border transition-all",
              activeFilterCount > 0
                ? "border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400"
                : "border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800",
            )}
          >
            <SlidersHorizontal className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
            <span className="hidden xs:inline">Фільтри</span>
            {activeFilterCount > 0 && (
              <span className="inline-flex items-center justify-center w-4 h-4 rounded-full text-[10px] font-bold bg-blue-500 text-white">
                {activeFilterCount}
              </span>
            )}
          </button>

          {/* Auto-refresh */}
          <div className="relative">
            <button
              onClick={() => setShowTimerPanel((v) => !v)}
              className={cn(
                "flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs sm:text-sm font-medium border transition-all",
                intervalSec !== null
                  ? "border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400"
                  : "border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800",
              )}
            >
              <Timer className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              {intervalSec !== null && countdown !== null ? (
                <span className="tabular-nums font-mono text-xs">
                  {formatCountdown(countdown)}
                </span>
              ) : (
                <span className="hidden xs:inline">Авто</span>
              )}
            </button>

            {showTimerPanel && (
              <div className="absolute right-0 top-full mt-2 z-20 w-48 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-slate-700 dark:text-slate-300">
                    Авто-оновлення
                  </span>
                  <button
                    onClick={() => setShowTimerPanel(false)}
                    className="text-slate-400 hover:text-slate-600 dark:hover:text-white"
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
                        "px-2.5 py-1 rounded-lg text-xs font-medium border transition-all",
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
                    Оновлення через{" "}
                    <span className="tabular-nums font-medium text-blue-500">
                      {formatCountdown(countdown)}
                    </span>
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Refresh */}
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className={cn(
              "flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs sm:text-sm font-medium border transition-all",
              "border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300",
              "hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed",
            )}
          >
            <RefreshCw
              className={cn(
                "w-3.5 h-3.5 sm:w-4 sm:h-4",
                isFetching && !isFetchingNextPage && "animate-spin",
              )}
            />
            <span className="hidden xs:inline">Оновити</span>
          </button>
        </div>
      </div>

      {/* Read/Unread/All tabs */}
      <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg w-full sm:w-fit">
        {FEED_FILTER_TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setFeedFilter(key)}
            className={cn(
              "flex-1 sm:flex-none px-3 sm:px-4 py-1.5 rounded-md text-sm font-medium transition-all",
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

      {/* Language tab bar */}
      {showLangTabs && (
        <LangTabBar
          langs={availableLangs}
          active={activeLang}
          counts={unreadLangCounts}
          onSelect={setActiveLang}
        />
      )}

      {/* Active filter chips */}
      {activeFilterCount > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-slate-400 dark:text-slate-500">
            Фільтри:
          </span>
          {filters.minScore > 0 && (
            <Chip
              label={`Score ≥ ${filters.minScore.toFixed(2)}`}
              onRemove={() => setFilters((f) => ({ ...f, minScore: 0 }))}
            />
          )}
          {filters.sortBy !== "date" && (
            <Chip
              label="За релевантністю"
              onRemove={() => setFilters((f) => ({ ...f, sortBy: "date" }))}
            />
          )}
          {filters.langs.map((lang) => (
            <Chip
              key={lang}
              label={`${getLangMeta(lang).label}`}
              onRemove={() =>
                setFilters((f) => ({
                  ...f,
                  langs: f.langs.filter((l) => l !== lang),
                }))
              }
            />
          ))}
          {filters.tags.map((tag) => (
            <Chip
              key={tag}
              label={tag}
              onRemove={() =>
                setFilters((f) => ({
                  ...f,
                  tags: f.tags.filter((t) => t !== tag),
                }))
              }
            />
          ))}
          <button
            onClick={() => setFilters(DEFAULT_FILTERS)}
            className="text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 hover:underline"
          >
            Скинути всі
          </button>
        </div>
      )}

      {/* Feed list */}
      {isLoading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="h-[60px] bg-slate-100 dark:bg-slate-800 rounded-xl animate-pulse"
              style={{ opacity: 1 - i * 0.1 }}
            />
          ))}
        </div>
      ) : isEmpty ? (
        <div className="flex flex-col items-center justify-center py-16 text-slate-400">
          {feedFilter === "unread" ? (
            <>
              <CheckCheck className="w-10 h-10 mb-3 text-emerald-500" />
              <p className="text-base font-medium text-slate-700 dark:text-slate-300">
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
              <Sparkles className="w-10 h-10 mb-3" />
              <p className="text-base font-medium text-slate-700 dark:text-slate-300">
                Стрічка порожня
              </p>
              <p className="text-sm mt-1">Додайте джерела або оновіть фід</p>
            </>
          )}
        </div>
      ) : (
        <div className="flex flex-col divide-y divide-slate-100 dark:divide-slate-800 border border-slate-100 dark:border-slate-800 rounded-xl overflow-hidden">
          {filteredItems.map(renderItem)}
        </div>
      )}

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

      <FilterPanel
        open={filterPanelOpen}
        onClose={() => setFilterPanelOpen(false)}
        filters={filters}
        onChange={setFilters}
        availableLangs={availableLangs}
        availableTags={availableTags}
      />

      <ArticleDrawer
        articleId={activeArticleId}
        onClose={() => setActiveArticle(null)}
      />
    </div>
  );
};
