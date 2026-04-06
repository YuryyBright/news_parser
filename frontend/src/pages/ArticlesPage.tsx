// src/pages/ArticlesPage.tsx
import { useState, useEffect, useRef } from "react";
import {
  SlidersHorizontal,
  X,
  Tag,
  Search,
  Link2,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  ArrowUp,
  ArrowDown,
  Calendar,
  Clock,
  Star,
  Plus,
  Loader2,
  RefreshCw,
} from "lucide-react";
import {
  useArticles,
  useArticleSearch,
  useIngestUrl,
} from "../hooks/useArticles";
import {
  useArticlesStore,
  type SortBy,
  type DatePreset,
} from "../store/useArticlesStore";
import { ArticleCard } from "../components/articles/ArticleCard";
import { ArticleDrawer } from "../components/articles/ArticleDrawer";
import { ScoreBadge } from "../components/articles/ScoreBadge";
import { cn, languageFlag } from "../lib/utils";
import type { ArticleStatus } from "../api/types";

// ─── Constants ────────────────────────────────────────────────────────────────

const STATUS_OPTIONS: { value: ArticleStatus | ""; label: string }[] = [
  { value: "", label: "Всі статті" },
  { value: "new", label: "🟡 Нові" },
  { value: "accepted", label: "🟢 Прийняті" },
  { value: "rejected", label: "🔴 Відхилені" },
  { value: "expired", label: "⚫ Приховані" },
  { value: "processing", label: "🔵 В обробці" },
];

const LANG_OPTIONS = ["", "uk", "en", "sk", "ro", "hu", "de", "fr", "pl"];

const DATE_PRESETS: { value: DatePreset; label: string }[] = [
  { value: null, label: "Будь-коли" },
  { value: "today", label: "Сьогодні" },
  { value: "week", label: "7 днів" },
  { value: "month", label: "30 днів" },
];

const SORT_OPTIONS: { value: SortBy; label: string; icon: React.ReactNode }[] =
  [
    {
      value: "created_at",
      label: "Дата додавання",
      icon: <Clock className="w-3.5 h-3.5" />,
    },
    {
      value: "published_at",
      label: "Дата публікації",
      icon: <Calendar className="w-3.5 h-3.5" />,
    },
    {
      value: "relevance_score",
      label: "Релевантність",
      icon: <Star className="w-3.5 h-3.5" />,
    },
  ];

// ─── AddByUrl Modal ───────────────────────────────────────────────────────────

interface AddByUrlModalProps {
  onClose: () => void;
}

const AddByUrlModal = ({ onClose }: AddByUrlModalProps) => {
  const [url, setUrl] = useState("");
  const ingest = useIngestUrl();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = async () => {
    if (!url.trim()) return;
    try {
      new URL(url); // validate
    } catch {
      return;
    }
    await ingest.mutateAsync(url.trim());
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />
      {/* Modal */}
      <div
        className={cn(
          "relative w-full max-w-lg rounded-2xl shadow-2xl",
          "bg-white dark:bg-slate-900",
          "border border-slate-200 dark:border-slate-800",
          "p-6",
        )}
      >
        <div className="flex items-center gap-3 mb-5">
          <div className="p-2 rounded-xl bg-blue-50 dark:bg-blue-950">
            <Link2 className="w-5 h-5 text-blue-500" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-900 dark:text-white">
              Додати статтю за URL
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Стаття буде спарсена і поставлена в чергу на обробку
            </p>
          </div>
          <button
            onClick={onClose}
            className="ml-auto p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-3">
          <input
            ref={inputRef}
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
            placeholder="https://example.com/article/..."
            className={cn(
              "w-full px-4 py-3 rounded-xl border text-sm transition-colors",
              "bg-slate-50 dark:bg-slate-800",
              "border-slate-200 dark:border-slate-700",
              "text-slate-900 dark:text-white placeholder:text-slate-400",
              "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
            )}
          />

          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="flex-1 px-4 py-2.5 rounded-xl text-sm font-medium border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              Скасувати
            </button>
            <button
              onClick={handleSubmit}
              disabled={ingest.isPending || !url.trim()}
              className={cn(
                "flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors",
                "bg-blue-500 hover:bg-blue-600 text-white",
                "disabled:opacity-50 disabled:cursor-not-allowed",
              )}
            >
              {ingest.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" /> Відправляємо...
                </>
              ) : (
                <>
                  <Plus className="w-4 h-4" /> Додати
                </>
              )}
            </button>
          </div>
        </div>

        <p className="mt-4 text-xs text-slate-400 dark:text-slate-500">
          💡 Статус обробки можна відслідкувати в розділі Sources → Tasks
        </p>
      </div>
    </div>
  );
};

// ─── Search Bar ───────────────────────────────────────────────────────────────

interface SearchBarProps {
  value: string;
  onChange: (v: string) => void;
  onClear: () => void;
  isLoading?: boolean;
}

const SearchBar = ({ value, onChange, onClear, isLoading }: SearchBarProps) => {
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <div className="relative flex-1 min-w-0">
      <div className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none">
        {isLoading ? (
          <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
        ) : (
          <Search className="w-4 h-4 text-slate-400" />
        )}
      </div>
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Пошук по заголовку та тексту..."
        className={cn(
          "w-full pl-10 pr-10 py-2.5 rounded-xl border text-sm transition-colors",
          "bg-white dark:bg-slate-900",
          "border-slate-200 dark:border-slate-800",
          "text-slate-900 dark:text-white placeholder:text-slate-400",
          "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
          value &&
            "border-blue-300 dark:border-blue-700 ring-1 ring-blue-300 dark:ring-blue-700",
        )}
      />
      {value && (
        <button
          onClick={() => {
            onClear();
            inputRef.current?.focus();
          }}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
};

// ─── Sort Button ──────────────────────────────────────────────────────────────

interface SortButtonProps {
  sortBy: SortBy;
  activeSortBy: SortBy;
  sortDir: "asc" | "desc";
  label: string;
  icon: React.ReactNode;
  onClick: () => void;
}

const SortButton = ({
  sortBy,
  activeSortBy,
  sortDir,
  label,
  icon,
  onClick,
}: SortButtonProps) => {
  const isActive = sortBy === activeSortBy;
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all",
        isActive
          ? "bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800 text-blue-600 dark:text-blue-400"
          : "border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800",
      )}
    >
      {icon}
      {label}
      {isActive &&
        (sortDir === "desc" ? (
          <ArrowDown className="w-3 h-3 ml-0.5" />
        ) : (
          <ArrowUp className="w-3 h-3 ml-0.5" />
        ))}
    </button>
  );
};

// ─── Pagination ───────────────────────────────────────────────────────────────

interface PaginationProps {
  page: number;
  pages: number;
  total: number;
  page_size: number;
  onPage: (p: number) => void;
}

const Pagination = ({
  page,
  pages,
  total,
  page_size,
  onPage,
}: PaginationProps) => {
  if (pages <= 1) return null;

  const from = (page - 1) * page_size + 1;
  const to = Math.min(page * page_size, total);

  // Generate page numbers with ellipsis
  const getPages = () => {
    const nums: (number | "...")[] = [];
    if (pages <= 7) {
      for (let i = 1; i <= pages; i++) nums.push(i);
    } else {
      nums.push(1);
      if (page > 3) nums.push("...");
      for (
        let i = Math.max(2, page - 1);
        i <= Math.min(pages - 1, page + 1);
        i++
      )
        nums.push(i);
      if (page < pages - 2) nums.push("...");
      nums.push(pages);
    }
    return nums;
  };

  const btnBase =
    "min-w-[32px] h-8 px-2 rounded-lg text-xs font-medium border transition-colors";

  return (
    <div className="flex items-center justify-between mt-6 pt-4 border-t border-slate-200 dark:border-slate-800">
      <span className="text-xs text-slate-400 dark:text-slate-500">
        {from}–{to} з {total} статей
      </span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPage(page - 1)}
          disabled={page === 1}
          className={cn(
            btnBase,
            "border-slate-200 dark:border-slate-700 text-slate-400 hover:text-slate-600 disabled:opacity-30 disabled:cursor-not-allowed",
          )}
        >
          <ChevronLeft className="w-3.5 h-3.5 mx-auto" />
        </button>

        {getPages().map((p, i) =>
          p === "..." ? (
            <span key={`e-${i}`} className="px-1 text-xs text-slate-400">
              …
            </span>
          ) : (
            <button
              key={p}
              onClick={() => onPage(p as number)}
              className={cn(
                btnBase,
                p === page
                  ? "bg-blue-500 border-blue-500 text-white"
                  : "border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800",
              )}
            >
              {p}
            </button>
          ),
        )}

        <button
          onClick={() => onPage(page + 1)}
          disabled={page === pages}
          className={cn(
            btnBase,
            "border-slate-200 dark:border-slate-700 text-slate-400 hover:text-slate-600 disabled:opacity-30 disabled:cursor-not-allowed",
          )}
        >
          <ChevronRight className="w-3.5 h-3.5 mx-auto" />
        </button>
      </div>
    </div>
  );
};

// ─── Main Page ────────────────────────────────────────────────────────────────

export const ArticlesPage = () => {
  const {
    filters,
    setFilter,
    setDatePreset,
    setSort,
    setPage,
    resetFilters,
    searchQuery,
    isSearchMode,
    setSearchQuery,
    activeArticleId,
    setActiveArticle,
  } = useArticlesStore();

  const [showFilters, setShowFilters] = useState(false);
  const [showAddUrl, setShowAddUrl] = useState(false);

  // Дебаунс пошуку
  const [debouncedQ, setDebouncedQ] = useState(searchQuery);
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(searchQuery), 350);
    return () => clearTimeout(t);
  }, [searchQuery]);

  // Запити
  const { data: listData, isLoading: listLoading } = useArticles(
    isSearchMode
      ? {}
      : {
          status: filters.status ?? undefined,
          min_score: filters.min_score,
          language: filters.language ?? undefined,
          tag: filters.tag ?? undefined,
          date_from: filters.date_from ?? undefined,
          date_to: filters.date_to ?? undefined,
          sort_by: filters.sort_by,
          sort_dir: filters.sort_dir,
          page: filters.page,
          page_size: filters.page_size,
        },
  );

  const { data: searchData, isFetching: searchFetching } = useArticleSearch(
    debouncedQ,
    {
      language: filters.language ?? undefined,
      status: filters.status ?? undefined,
    },
  );

  const articles = isSearchMode
    ? (searchData?.items ?? [])
    : (listData?.items ?? []);

  const pagination =
    !isSearchMode && listData
      ? {
          total: listData.total,
          page: listData.page,
          pages: listData.pages,
          page_size: listData.page_size,
        }
      : null;

  const isLoading = isSearchMode
    ? searchFetching && debouncedQ.length >= 2
    : listLoading;
  const totalInfo = isSearchMode
    ? searchData
      ? `${searchData.total} результатів для "${searchData.query}"`
      : ""
    : listData
      ? `${listData.total} статей`
      : "";

  const hasActiveFilters =
    !!filters.status ||
    (filters.min_score ?? 0) > 0 ||
    !!filters.language ||
    !!filters.tag ||
    !!filters.date_from ||
    !!filters.date_to;

  const selectClass = cn(
    "px-3 py-2 rounded-lg border text-sm transition-colors",
    "bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700",
    "text-slate-700 dark:text-slate-300",
    "focus:outline-none focus:ring-2 focus:ring-blue-500",
  );

  return (
    <div>
      {/* ─── Header ─────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            Статті
          </h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm mt-0.5">
            {isLoading ? "Завантаження..." : totalInfo}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAddUrl(true)}
            className={cn(
              "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium border transition-all",
              "border-emerald-200 dark:border-emerald-800 text-emerald-600 dark:text-emerald-400",
              "hover:bg-emerald-50 dark:hover:bg-emerald-950",
            )}
          >
            <Link2 className="w-4 h-4" />
            Додати URL
          </button>

          <button
            onClick={() => setShowFilters(!showFilters)}
            className={cn(
              "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium border transition-all",
              showFilters || hasActiveFilters
                ? "bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800 text-blue-600 dark:text-blue-400"
                : "border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800",
            )}
          >
            <SlidersHorizontal className="w-4 h-4" />
            Фільтри
            {hasActiveFilters && (
              <span className="w-2 h-2 bg-blue-500 rounded-full" />
            )}
          </button>
        </div>
      </div>

      {/* ─── Search + Sort row ──────────────────────────────────────────── */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <SearchBar
          value={searchQuery}
          onChange={setSearchQuery}
          onClear={() => {
            setSearchQuery("");
            setDebouncedQ("");
          }}
          isLoading={searchFetching && debouncedQ.length >= 2}
        />

        {/* Sort buttons (hidden in search mode) */}
        {!isSearchMode && (
          <div className="flex items-center gap-1.5 flex-shrink-0">
            {SORT_OPTIONS.map(({ value, label, icon }) => (
              <SortButton
                key={value}
                sortBy={value}
                activeSortBy={filters.sort_by}
                sortDir={filters.sort_dir}
                label={label}
                icon={icon}
                onClick={() => setSort(value)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Search mode banner */}
      {isSearchMode && (
        <div
          className={cn(
            "flex items-center gap-2 mb-4 px-3 py-2 rounded-lg text-sm",
            "bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800",
            "text-blue-700 dark:text-blue-300",
          )}
        >
          <Search className="w-3.5 h-3.5 shrink-0" />
          <span>Режим пошуку — пагінація і сортування тимчасово вимкнені</span>
          <button
            onClick={() => {
              setSearchQuery("");
              setDebouncedQ("");
            }}
            className="ml-auto text-blue-500 hover:text-blue-700 underline text-xs"
          >
            Очистити
          </button>
        </div>
      )}

      {/* Active tag chip (outside filter panel) */}
      {filters.tag && !showFilters && (
        <div className="flex items-center gap-2 mb-4">
          <span className="text-xs text-slate-500 dark:text-slate-400">
            Тег:
          </span>
          <button
            onClick={() => setFilter("tag", null)}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-blue-500 text-white hover:bg-blue-600 transition-colors"
          >
            <Tag className="w-3 h-3" />
            {filters.tag}
            <X className="w-3 h-3" />
          </button>
        </div>
      )}

      {/* ─── Filter Panel ───────────────────────────────────────────────── */}
      {showFilters && (
        <div
          className={cn(
            "mb-5 p-4 rounded-xl border",
            "bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800",
          )}
        >
          <div className="flex flex-wrap gap-x-6 gap-y-4 items-end">
            {/* Status */}
            <div>
              <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1.5">
                Статус
              </label>
              <select
                value={filters.status ?? ""}
                onChange={(e) =>
                  setFilter("status", (e.target.value as ArticleStatus) || null)
                }
                className={selectClass}
              >
                {STATUS_OPTIONS.map(({ value, label }) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>

            {/* Language */}
            <div>
              <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1.5">
                Мова
              </label>
              <select
                value={filters.language ?? ""}
                onChange={(e) => setFilter("language", e.target.value || null)}
                className={selectClass}
              >
                {LANG_OPTIONS.map((lang) => (
                  <option key={lang} value={lang}>
                    {lang
                      ? `${languageFlag(lang)} ${lang.toUpperCase()}`
                      : "Всі мови"}
                  </option>
                ))}
              </select>
            </div>

            {/* Min score */}
            <div>
              <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1.5">
                Мін. score: <ScoreBadge score={filters.min_score ?? 0} />
              </label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={filters.min_score ?? 0}
                onChange={(e) =>
                  setFilter("min_score", parseFloat(e.target.value))
                }
                className="w-36 accent-blue-500"
              />
            </div>

            {/* Page size */}
            <div>
              <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1.5">
                Статей на сторінці
              </label>
              <select
                value={filters.page_size}
                onChange={(e) => setFilter("page_size", Number(e.target.value))}
                className={selectClass}
              >
                {[10, 20, 30, 50, 100].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </div>

            {/* Active tag */}
            {filters.tag && (
              <div>
                <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1.5">
                  Тег
                </label>
                <button
                  onClick={() => setFilter("tag", null)}
                  className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm bg-blue-500 text-white hover:bg-blue-600 transition-colors"
                >
                  <Tag className="w-3.5 h-3.5" />
                  {filters.tag}
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            )}

            {/* Reset */}
            {hasActiveFilters && (
              <button
                onClick={resetFilters}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm text-slate-500 hover:text-red-500 border border-transparent hover:border-red-200 dark:hover:border-red-900 transition-all"
              >
                <X className="w-3.5 h-3.5" />
                Скинути фільтри
              </button>
            )}
          </div>

          {/* Date presets */}
          <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800">
            <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-2">
              Дата додавання
            </label>
            <div className="flex items-center gap-2 flex-wrap">
              {DATE_PRESETS.map(({ value, label }) => (
                <button
                  key={String(value)}
                  onClick={() => setDatePreset(value)}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-xs font-medium border transition-all",
                    filters.date_preset === value
                      ? "bg-blue-500 border-blue-500 text-white"
                      : "border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800",
                  )}
                >
                  {label}
                </button>
              ))}

              {/* Custom date range */}
              <div className="flex items-center gap-2 ml-2">
                <span className="text-xs text-slate-400">Від:</span>
                <input
                  type="date"
                  value={
                    filters.date_from ? filters.date_from.split("T")[0] : ""
                  }
                  onChange={(e) => {
                    setFilter(
                      "date_from",
                      e.target.value
                        ? new Date(e.target.value).toISOString()
                        : null,
                    );
                    setFilter("date_preset", null);
                  }}
                  className={cn(selectClass, "py-1.5 text-xs")}
                />
                <span className="text-xs text-slate-400">До:</span>
                <input
                  type="date"
                  value={filters.date_to ? filters.date_to.split("T")[0] : ""}
                  onChange={(e) => {
                    setFilter(
                      "date_to",
                      e.target.value
                        ? new Date(e.target.value + "T23:59:59").toISOString()
                        : null,
                    );
                    setFilter("date_preset", null);
                  }}
                  className={cn(selectClass, "py-1.5 text-xs")}
                />
              </div>
            </div>
          </div>

          {!filters.status && (
            <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
              💡 Фільтр "Всі статті" включає всі статуси. Приховані ("Не
              показувати") теж відображаються якщо не вибрано конкретний статус.
            </p>
          )}
        </div>
      )}

      {/* ─── Grid ───────────────────────────────────────────────────────── */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({
            length: filters.page_size > 9 ? 9 : filters.page_size,
          }).map((_, i) => (
            <div
              key={i}
              className="h-40 bg-slate-100 dark:bg-slate-800 rounded-xl animate-pulse"
            />
          ))}
        </div>
      ) : articles.length === 0 ? (
        <div className="text-center py-20">
          <div className="text-4xl mb-4">{isSearchMode ? "🔎" : "🔍"}</div>
          <p className="text-lg font-medium text-slate-700 dark:text-slate-300">
            {isSearchMode
              ? `Нічого не знайдено за "${debouncedQ}"`
              : "Статей не знайдено"}
          </p>
          <p className="text-sm text-slate-400 dark:text-slate-500 mt-1">
            {isSearchMode
              ? "Спробуйте інший запит або перевірте написання"
              : hasActiveFilters
                ? "Спробуйте змінити або скинути фільтри"
                : "Поки що немає статей у цьому розділі"}
          </p>
          {isSearchMode && (
            <button
              onClick={() => setShowAddUrl(true)}
              className="mt-4 inline-flex items-center gap-2 px-4 py-2 text-sm text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800 rounded-lg hover:bg-emerald-50 dark:hover:bg-emerald-950 transition-colors"
            >
              <Link2 className="w-3.5 h-3.5" />
              Додати статтю за URL
            </button>
          )}
          {!isSearchMode && hasActiveFilters && (
            <button
              onClick={resetFilters}
              className="mt-4 px-4 py-2 text-sm text-blue-600 dark:text-blue-400 hover:underline"
            >
              Скинути фільтри
            </button>
          )}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {articles.map((article) => (
              <ArticleCard
                key={article.id}
                article={article}
                onClick={() => setActiveArticle(article.id)}
              />
            ))}
          </div>

          {/* Pagination */}
          {pagination && (
            <Pagination
              page={pagination.page}
              pages={pagination.pages}
              total={pagination.total}
              page_size={pagination.page_size}
              onPage={setPage}
            />
          )}
        </>
      )}

      {/* ─── Drawers & Modals ───────────────────────────────────────────── */}
      <ArticleDrawer
        articleId={activeArticleId}
        onClose={() => setActiveArticle(null)}
      />

      {showAddUrl && <AddByUrlModal onClose={() => setShowAddUrl(false)} />}
    </div>
  );
};
