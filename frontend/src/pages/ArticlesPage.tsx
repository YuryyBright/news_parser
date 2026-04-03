// src/pages/ArticlesPage.tsx
import { useState } from "react";
import { SlidersHorizontal, X, Tag } from "lucide-react";
import { useArticles } from "../hooks/useArticles";
import { useArticlesStore } from "../store/useArticlesStore";
import { ArticleCard } from "../components/articles/ArticleCard";
import { ArticleDrawer } from "../components/articles/ArticleDrawer";
import { ScoreBadge } from "../components/articles/ScoreBadge";
import { cn, languageFlag } from "../lib/utils";
import type { ArticleStatus } from "../api/types";

const STATUS_OPTIONS: { value: ArticleStatus | ""; label: string }[] = [
  { value: "", label: "Всі (крім прихованих)" },
  { value: "new", label: "Нові" },
  { value: "accepted", label: "Прийняті" },
  { value: "rejected", label: "Відхилені" },
  { value: "expired", label: "Приховані" },
];

const LANG_OPTIONS = ["", "uk", "en", "de", "fr", "pl", "es"];

export const ArticlesPage = () => {
  const { filters, setFilter, resetFilters } = useArticlesStore();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);

  // За замовчуванням не показуємо "expired" статті — вони приховані
  // Якщо юзер явно вибирає "Приховані" — показуємо
  const effectiveFilters = {
    ...filters,
    // Якщо статус не вибраний — передаємо спеціальний параметр exclude_expired
    // (або просто не показуємо expired у дефолті через дефолтний статус)
  };

  const { data: articles = [], isLoading } = useArticles(filters);

  const hasActiveFilters =
    !!filters.status ||
    (filters.min_score ?? 0) > 0 ||
    !!filters.language ||
    !!filters.tag;

  const selectClass = cn(
    "px-3 py-2 rounded-lg border text-sm transition-colors",
    "bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700",
    "text-slate-700 dark:text-slate-300",
    "focus:outline-none focus:ring-2 focus:ring-blue-500",
  );

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            Статті
          </h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm mt-0.5">
            {isLoading ? "Завантаження..." : `${articles.length} статей`}
          </p>
        </div>

        <button
          onClick={() => setShowFilters(!showFilters)}
          className={cn(
            "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-all",
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

      {/* Active tag chip (shown even when filter panel is closed) */}
      {filters.tag && !showFilters && (
        <div className="flex items-center gap-2 mb-4">
          <span className="text-xs text-slate-500 dark:text-slate-400">
            Тег:
          </span>
          <button
            onClick={() => setFilter("tag", null)}
            className={cn(
              "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium",
              "bg-blue-500 text-white",
              "hover:bg-blue-600 transition-colors",
            )}
          >
            <Tag className="w-3 h-3" />
            {filters.tag}
            <X className="w-3 h-3" />
          </button>
        </div>
      )}

      {/* Filter panel */}
      {showFilters && (
        <div
          className={cn(
            "mb-6 p-4 rounded-xl border",
            "bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800",
          )}
        >
          <div className="flex flex-wrap gap-4 items-end">
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

            {/* Active tag */}
            {filters.tag && (
              <div>
                <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1.5">
                  Тег
                </label>
                <button
                  onClick={() => setFilter("tag", null)}
                  className={cn(
                    "inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm",
                    "bg-blue-500 text-white hover:bg-blue-600 transition-colors",
                  )}
                >
                  <Tag className="w-3.5 h-3.5" />
                  {filters.tag}
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            )}

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
                className="w-40 accent-blue-500"
              />
            </div>

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

          {/* Hint about expired articles */}
          {!filters.status && (
            <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
              💡 Приховані статті ("Не показувати") не відображаються за
              замовчуванням. Виберіть статус "Приховані" щоб їх побачити.
            </p>
          )}
        </div>
      )}

      {/* Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 9 }).map((_, i) => (
            <div
              key={i}
              className="h-40 bg-slate-100 dark:bg-slate-800 rounded-xl animate-pulse"
            />
          ))}
        </div>
      ) : articles.length === 0 ? (
        <div className="text-center py-20">
          <div className="text-4xl mb-4">🔍</div>
          <p className="text-lg font-medium text-slate-700 dark:text-slate-300">
            Статей не знайдено
          </p>
          <p className="text-sm text-slate-400 dark:text-slate-500 mt-1">
            {hasActiveFilters
              ? "Спробуйте змінити або скинути фільтри"
              : "Поки що немає статей"}
          </p>
          {hasActiveFilters && (
            <button
              onClick={resetFilters}
              className="mt-4 px-4 py-2 text-sm text-blue-600 dark:text-blue-400 hover:underline"
            >
              Скинути фільтри
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {articles.map((article) => (
            <ArticleCard
              key={article.id}
              article={article}
              onClick={() => setSelectedId(article.id)}
            />
          ))}
        </div>
      )}

      <ArticleDrawer
        articleId={selectedId}
        onClose={() => setSelectedId(null)}
      />
    </div>
  );
};
