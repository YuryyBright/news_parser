// src/pages/GeneratedNewsPage.tsx

import { useState, useEffect, useRef } from "react";
import {
  Search,
  X,
  Send,
  Clock,
  Globe,
  Tag,
  ChevronLeft,
  ChevronRight,
  Filter,
  ExternalLink,
  CheckCircle2,
  FileText,
  Loader2,
} from "lucide-react";
import { useGeneratedNews, usePublishNews } from "../hooks/useGeneratedNews";
import { cn, formatDate } from "../lib/utils";
import { getLangMeta, flagImgProps } from "../lib/languages";
import type { GeneratedNewsItem } from "../api/generatedNews";

// ─── Constants ────────────────────────────────────────────────────────────────

const LANG_OPTIONS = ["", "uk", "en", "sk", "ro", "hu", "de", "fr", "pl"];

const STATUS_OPTIONS = [
  { value: "", label: "Всі" },
  { value: "draft", label: "Чернетки" },
  { value: "published", label: "Опубліковані" },
];

// ─── Flag ─────────────────────────────────────────────────────────────────────

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

// ─── Status Badge ─────────────────────────────────────────────────────────────

const StatusBadge = ({ status }: { status: string }) => (
  <span
    className={cn(
      "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium",
      status === "published"
        ? "bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400"
        : "bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400",
    )}
  >
    {status === "published" ? (
      <CheckCircle2 className="w-3 h-3" />
    ) : (
      <FileText className="w-3 h-3" />
    )}
    {status === "published" ? "Опубліковано" : "Чернетка"}
  </span>
);

// ─── News Card ────────────────────────────────────────────────────────────────

interface NewsCardProps {
  item: GeneratedNewsItem;
  onClick: () => void;
}

const NewsCard = ({ item, onClick }: NewsCardProps) => {
  const publish = usePublishNews();

  return (
    <article
      onClick={onClick}
      className={cn(
        "group relative bg-white dark:bg-slate-900 rounded-xl border cursor-pointer",
        "border-slate-200 dark:border-slate-800",
        "hover:border-blue-300 dark:hover:border-blue-700",
        "hover:shadow-lg dark:hover:shadow-slate-950/50",
        "active:scale-[0.99] transition-all duration-200",
      )}
    >
      {/* left accent */}
      <div
        className={cn(
          "absolute left-0 top-3 bottom-3 w-[3px] rounded-full",
          item.status === "published" ? "bg-emerald-500" : "bg-amber-400",
        )}
      />

      <div className="p-4 pl-5">
        {/* top meta */}
        <div className="flex items-center gap-2 flex-wrap mb-2">
          <StatusBadge status={item.status} />
          {item.language && (
            <span className="flex items-center gap-1 text-xs text-slate-400">
              <FlagImg lang={item.language} className="w-[18px] h-[13px]" />
              <span className="font-mono uppercase text-[11px]">
                {item.language}
              </span>
            </span>
          )}
          <div className="ml-auto flex items-center gap-1 text-xs text-slate-400 tabular-nums">
            <Clock className="w-3 h-3" />
            {formatDate(item.created_at)}
          </div>
        </div>
        {/* title */}
        {item.title && (
          <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-1.5 line-clamp-1 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
            {item.title}
          </h3>
        )}
        {/* rewritten text preview */}
        <p className="text-sm text-slate-600 dark:text-slate-400 line-clamp-3 leading-relaxed">
          {item.body}
        </p>
        {/* tags
        {item.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2.5">
            {item.tags.slice(0, 4).map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400"
              >
                <Tag className="w-2.5 h-2.5" />
                {tag}
              </span>
            ))}
          </div>
        )} */}
        {/* footer */}
        <div
          className="flex items-center justify-between mt-3 pt-3 border-t border-slate-100 dark:border-slate-800"
          onClick={(e) => e.stopPropagation()}
        >
          {item.source_url ? (
            <a
              href={item.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-xs text-slate-400 hover:text-blue-500 transition-colors"
            >
              <ExternalLink className="w-3 h-3" />
              Джерело
            </a>
          ) : (
            <span />
          )}

          {item.status === "draft" && (
            <button
              onClick={() => publish.mutate(item.id)}
              disabled={publish.isPending}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
                "bg-blue-500 hover:bg-blue-600 text-white",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                "opacity-0 group-hover:opacity-100",
              )}
            >
              {publish.isPending ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <Send className="w-3 h-3" />
              )}
              Telegram
            </button>
          )}
        </div>
      </div>
    </article>
  );
};

// ─── Detail Drawer ────────────────────────────────────────────────────────────

interface DrawerProps {
  item: GeneratedNewsItem | null;
  onClose: () => void;
}

const NewsDrawer = ({ item, onClose }: DrawerProps) => {
  const publish = usePublishNews();

  if (!item) return null;

  return (
    <>
      <div
        className="fixed inset-0 bg-black/30 dark:bg-black/50 z-40 backdrop-blur-sm hidden md:block"
        onClick={onClose}
      />
      <aside
        className={cn(
          "fixed inset-0 z-50 bg-white dark:bg-slate-900",
          "md:left-auto md:right-0 md:inset-y-0 md:w-full md:max-w-2xl",
          "border-l border-slate-200 dark:border-slate-800 flex flex-col shadow-2xl",
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="md:hidden p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <StatusBadge status={item.status} />
            {item.language && (
              <span className="flex items-center gap-1.5 text-sm text-slate-500">
                <FlagImg lang={item.language} className="w-[20px] h-[14px]" />
                {getLangMeta(item.language).label}
              </span>
            )}
          </div>
          <button
            onClick={onClose}
            className="hidden md:flex p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto overscroll-contain p-5 space-y-4">
          {item.title && (
            <h1 className="text-xl font-bold text-slate-900 dark:text-white leading-tight">
              {item.title}
            </h1>
          )}

          <div className="flex flex-wrap gap-3 text-sm text-slate-500">
            <span className="flex items-center gap-1">
              <Clock className="w-3.5 h-3.5" />
              {formatDate(item.created_at)}
            </span>
            {item.created_at && (
              <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Надіслано {formatDate(item.created_at)}
              </span>
            )}
          </div>

          {/* {item.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {item.tags.map((tag) => (
                <span
                  key={tag}
                  className="px-2.5 py-1 rounded-lg text-xs bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400"
                >
                  #{tag}
                </span>
              ))}
            </div>
          )} */}

          <div className="prose prose-sm dark:prose-invert max-w-none">
            <p className="text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-wrap">
              {item.body}
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between gap-4">
          {item.source_url ? (
            <a
              href={item.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-slate-500 hover:text-blue-500 transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              Оригінальне джерело
            </a>
          ) : (
            <span />
          )}

          {item.status === "draft" && (
            <button
              onClick={() => publish.mutate(item.id)}
              disabled={publish.isPending}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors",
                "bg-blue-500 hover:bg-blue-600 text-white",
                "disabled:opacity-50 disabled:cursor-not-allowed",
              )}
            >
              {publish.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
              Опублікувати в Telegram
            </button>
          )}
        </div>
      </aside>
    </>
  );
};

// ─── Pagination (reuse pattern) ───────────────────────────────────────────────

const Pagination = ({
  page,
  pages,
  total,
  page_size,
  onPage,
}: {
  page: number;
  pages: number;
  total: number;
  page_size: number;
  onPage: (p: number) => void;
}) => {
  if (pages <= 1) return null;
  const from = (page - 1) * page_size + 1;
  const to = Math.min(page * page_size, total);

  return (
    <div className="flex items-center justify-between mt-6 pt-4 border-t border-slate-200 dark:border-slate-800">
      <span className="text-xs text-slate-400">
        {from}–{to} з {total}
      </span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPage(page - 1)}
          disabled={page === 1}
          className="min-w-[36px] h-9 px-2 rounded-lg text-xs border border-slate-200 dark:border-slate-700 text-slate-400 hover:text-slate-600 disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <ChevronLeft className="w-3.5 h-3.5 mx-auto" />
        </button>
        {Array.from({ length: Math.min(pages, 7) }, (_, i) => i + 1).map(
          (p) => (
            <button
              key={p}
              onClick={() => onPage(p)}
              className={cn(
                "min-w-[36px] h-9 px-2 rounded-lg text-xs border transition-colors",
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
          className="min-w-[36px] h-9 px-2 rounded-lg text-xs border border-slate-200 dark:border-slate-700 text-slate-400 hover:text-slate-600 disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <ChevronRight className="w-3.5 h-3.5 mx-auto" />
        </button>
      </div>
    </div>
  );
};

// ─── Main Page ────────────────────────────────────────────────────────────────

export const GeneratedNewsPage = () => {
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [language, setLanguage] = useState("");
  const [status, setStatus] = useState("");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const [activeItem, setActiveItem] = useState<GeneratedNewsItem | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedQ(q);
      setPage(1);
    }, 350);
    return () => clearTimeout(t);
  }, [q]);

  const { data, isLoading } = useGeneratedNews({
    q: debouncedQ || undefined,
    language: language || undefined,
    status: status || undefined,
    sort_dir: sortDir,
    page,
    page_size: 12,
  });

  const hasFilters = !!(language || status);

  const selectCls = cn(
    "px-3 py-1.5 rounded-lg border text-sm",
    "bg-white dark:bg-slate-900",
    "border-slate-200 dark:border-slate-800",
    "text-slate-700 dark:text-slate-300",
    "focus:outline-none focus:ring-2 focus:ring-blue-500",
  );

  return (
    <div className="max-w-7xl mx-auto space-y-4">
      {/* ── Toolbar ── */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-2">
          {/* Search */}
          <div className="relative flex-1 min-w-0">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
            <input
              ref={searchRef}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Пошук по тексту..."
              className={cn(
                "w-full pl-10 pr-10 py-2.5 rounded-xl border text-sm transition-colors",
                "bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800",
                "text-slate-900 dark:text-white placeholder:text-slate-400",
                "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
                q && "border-blue-300 dark:border-blue-700",
              )}
            />
            {q && (
              <button
                onClick={() => {
                  setQ("");
                  searchRef.current?.focus();
                }}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Filters toggle */}
          <button
            onClick={() => setShowFilters((v) => !v)}
            className={cn(
              "flex items-center gap-1.5 px-3 py-2.5 rounded-xl border text-sm font-medium transition-all flex-shrink-0",
              showFilters || hasFilters
                ? "bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800 text-blue-600 dark:text-blue-400"
                : "border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800",
            )}
          >
            <Filter className="w-4 h-4" />
            <span className="hidden sm:inline">Фільтри</span>
          </button>

          {/* Sort dir */}
          <button
            onClick={() => setSortDir((d) => (d === "desc" ? "asc" : "desc"))}
            className="flex items-center gap-1.5 px-3 py-2.5 rounded-xl border text-sm border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 flex-shrink-0"
            title={sortDir === "desc" ? "Нові спочатку" : "Старі спочатку"}
          >
            <Clock className="w-4 h-4" />
            <span className="hidden sm:inline">
              {sortDir === "desc" ? "Нові" : "Старі"}
            </span>
          </button>
        </div>

        {/* Filter panel */}
        {showFilters && (
          <div className="flex flex-wrap gap-3 p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1.5">
                Статус
              </label>
              <select
                value={status}
                onChange={(e) => {
                  setStatus(e.target.value);
                  setPage(1);
                }}
                className={selectCls}
              >
                {STATUS_OPTIONS.map(({ value, label }) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1.5">
                Мова
              </label>
              <select
                value={language}
                onChange={(e) => {
                  setLanguage(e.target.value);
                  setPage(1);
                }}
                className={selectCls}
              >
                {LANG_OPTIONS.map((lang) => (
                  <option key={lang} value={lang}>
                    {lang
                      ? `${getLangMeta(lang).label} (${lang.toUpperCase()})`
                      : "Всі мови"}
                  </option>
                ))}
              </select>
            </div>
            {hasFilters && (
              <div className="flex items-end">
                <button
                  onClick={() => {
                    setLanguage("");
                    setStatus("");
                    setPage(1);
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-slate-500 hover:text-red-500 border border-transparent hover:border-red-200 dark:hover:border-red-900 transition-all"
                >
                  <X className="w-3.5 h-3.5" /> Скинути
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Stats row ── */}
      {data && (
        <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
          <span>{data.total} новин</span>
          {debouncedQ && <span>· за запитом «{debouncedQ}»</span>}
        </div>
      )}

      {/* ── Grid ── */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3 sm:gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-48 bg-slate-100 dark:bg-slate-800 rounded-xl animate-pulse"
            />
          ))}
        </div>
      ) : !data?.items.length ? (
        <div className="text-center py-20">
          <div className="text-4xl mb-4">📰</div>
          <p className="text-lg font-medium text-slate-700 dark:text-slate-300">
            {debouncedQ
              ? `Нічого не знайдено за «${debouncedQ}»`
              : "Згенерованих новин немає"}
          </p>
          <p className="text-sm text-slate-400 mt-1">
            Новини з'являться після обробки статей через Telegram rewriter
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3 sm:gap-4">
            {data.items.map((item) => (
              <NewsCard
                key={item.id}
                item={item}
                onClick={() => setActiveItem(item)}
              />
            ))}
          </div>
          {data && (
            <Pagination
              page={data.page}
              pages={data.pages}
              total={data.total}
              page_size={data.page_size}
              onPage={setPage}
            />
          )}
        </>
      )}

      {/* ── Drawer ── */}
      <NewsDrawer item={activeItem} onClose={() => setActiveItem(null)} />
    </div>
  );
};
