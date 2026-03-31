// src/pages/ArticlesPage.tsx
import { useState } from "react";
import { SlidersHorizontal, X } from "lucide-react";
import { useArticles } from "../hooks/useArticles";
import { useArticlesStore } from "../store/useArticlesStore";
import { ArticleCard } from "../components/articles/ArticleCard";
import { ArticleDrawer } from "../components/articles/ArticleDrawer";
import { ScoreBadge } from "../components/articles/ScoreBadge";
import { cn, languageFlag } from "../lib/utils";
import type { ArticleStatus } from "../api/types";

const STATUS_OPTIONS: { value: ArticleStatus | ""; label: string }[] = [
  { value: "", label: "Всі статуси" },
  { value: "new", label: "Нові" },
  { value: "accepted", label: "Прийняті" },
  { value: "expired", label: "Застарілі" },
  { value: "rejected", label: "Відхилені" },
];

const LANG_OPTIONS = ["", "uk", "en", "de", "fr", "pl", "es"];

export const ArticlesPage = () => {
  const { filters, setFilter, resetFilters } = useArticlesStore();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);

  const { data: articles = [], isLoading } = useArticles(filters);

  const hasActiveFilters =
    filters.status || (filters.min_score ?? 0) > 0 || filters.language;

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
            showFilters
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
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm text-slate-500 hover:text-red-500 border border-transparent hover:border-red-200 transition-all"
              >
                <X className="w-3.5 h-3.5" />
                Скинути
              </button>
            )}
          </div>
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
        <div className="text-center py-20 text-slate-400">
          <p className="text-lg font-medium">Статей не знайдено</p>
          <p className="text-sm">Спробуйте змінити фільтри</p>
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
