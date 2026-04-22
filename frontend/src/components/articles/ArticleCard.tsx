// src/components/articles/ArticleCard.tsx
import { ExternalLink, Clock, Eye } from "lucide-react";
import { cn, formatDate } from "../../lib/utils";
import { getLangMeta, flagImgProps } from "../../lib/languages";
import { ScoreBadge } from "./ScoreBadge";
import { ArticleBadge } from "./ArticleBadge";
import { TagsList } from "./TagsList";
import { FeedbackButtons } from "./FeedbackButtons";
import type { Article } from "../../api/types";

interface Props {
  article: Article;
  onClick?: () => void;
  isRead?: boolean;
  /** "card" — grid-картка (default), "feed" — рядок стрічки */
  variant?: "card" | "feed";
  onMarkRead?: (e: React.MouseEvent) => void;
}

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

export const ArticleCard = ({
  article,
  onClick,
  isRead,
  variant = "card",
  onMarkRead,
}: Props) => {
  if (variant === "feed") {
    return (
      <article
        onClick={onClick}
        className={cn(
          "flex items-start gap-3 px-3 sm:px-4 py-3 sm:py-4 cursor-pointer transition-colors group",
          "bg-white dark:bg-slate-900",
          !isRead &&
            "hover:bg-slate-50 dark:hover:bg-slate-800/60 active:bg-slate-100 dark:active:bg-slate-800",
          isRead && "opacity-60",
        )}
      >
        {/* Unread dot */}
        <div className="mt-1.5 flex-shrink-0 w-2 h-2">
          <div
            className={cn(
              "w-2 h-2 rounded-full transition-colors",
              isRead ? "bg-transparent" : "bg-blue-500",
            )}
          />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <p
            className={cn(
              "text-sm font-medium leading-snug line-clamp-2",
              isRead
                ? "text-slate-400 dark:text-slate-500"
                : "text-slate-900 dark:text-white",
            )}
          >
            {article.title}
          </p>

          <div className="flex items-center flex-wrap gap-2 mt-1.5">
            {article.published_at && (
              <span className="flex items-center gap-1 text-xs text-slate-400 dark:text-slate-500">
                <Clock className="w-3 h-3" />
                {formatDate(article.published_at)}
              </span>
            )}
            {article.language && (
              <span className="flex items-center text-xs">
                <FlagImg
                  lang={article.language}
                  className="w-[18px] h-[13px]"
                />
                <span className="ml-1.5 font-mono text-slate-400 dark:text-slate-500 uppercase text-[11px]">
                  {article.language}
                </span>
              </span>
            )}
            {article.relevance_score != null && (
              <ScoreBadge score={article.relevance_score} />
            )}
            {/* Теги — ховаємо на дуже малих екранах */}
            {article.tags?.length > 0 && (
              <span className="hidden xs:block">
                <TagsList tags={article.tags.slice(0, 2)} clickable />
              </span>
            )}
          </div>
        </div>

        {/* Right-side actions — на мобільних завжди видимі, на десктопі при hover */}
        <div
          className="flex-shrink-0 flex items-center gap-0.5 mt-0.5"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Feedback — при hover на md+ або завжди на touch */}
          <div className="hidden sm:flex opacity-0 group-hover:opacity-100 transition-opacity items-center gap-0.5">
            <FeedbackButtons articleId={article.article_id} compact />
          </div>

          {!isRead && onMarkRead && (
            <button
              onClick={onMarkRead}
              title="Позначити прочитаним"
              className={cn(
                "p-1.5 rounded-md transition-all",
                "sm:opacity-0 sm:group-hover:opacity-100",
                "text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-900/30",
              )}
            >
              <Eye className="w-4 h-4" />
            </button>
          )}

          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            title="Відкрити оригінал"
            className={cn(
              "p-1.5 rounded-md transition-all",
              "sm:opacity-0 sm:group-hover:opacity-100",
              "text-slate-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-950/50",
            )}
          >
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>
      </article>
    );
  }

  // ─── variant="card" ───────────────────────────────────────────────────────
  return (
    <article
      className={cn(
        "group relative bg-white dark:bg-slate-900 rounded-xl border",
        "border-slate-200 dark:border-slate-800",
        "hover:border-blue-300 dark:hover:border-blue-700",
        "hover:shadow-lg dark:hover:shadow-slate-950/50",
        "active:scale-[0.99]",
        "transition-all duration-200",
        onClick && "cursor-pointer",
        isRead && "opacity-55",
      )}
      onClick={onClick}
    >
      {!isRead && (
        <div className="absolute left-0 top-3 bottom-3 w-[3px] bg-blue-500 rounded-full" />
      )}

      <div className="p-3 sm:p-4 pl-4 sm:pl-5">
        <div className="flex items-center gap-2 flex-wrap mb-2">
          <ArticleBadge status={article.status} />
          <ScoreBadge score={article.relevance_score} />
          <span
            className="flex items-center justify-center leading-none"
            title={getLangMeta(article.language).label}
          >
            <FlagImg lang={article.language} className="w-[20px] h-[15px]" />
          </span>
          <div className="ml-auto flex items-center gap-1 text-xs text-slate-400 dark:text-slate-500 tabular-nums">
            <Clock className="w-3 h-3 shrink-0" />
            {formatDate(article.published_at ?? article.created_at)}
          </div>
        </div>

        <h3
          className={cn(
            "text-sm font-semibold leading-snug mb-2",
            "text-slate-900 dark:text-white",
            "group-hover:text-blue-600 dark:group-hover:text-blue-400",
            "transition-colors line-clamp-2",
          )}
        >
          {article.title}
        </h3>

        {article.tags.length > 0 && (
          <TagsList tags={article.tags} clickable className="mb-3" />
        )}

        <div
          className="flex items-center justify-between gap-2 pt-2 border-t border-slate-100 dark:border-slate-800"
          onClick={(e) => e.stopPropagation()}
        >
          <FeedbackButtons articleId={article.id} compact />
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(
              "p-1.5 rounded-lg transition-colors",
              "text-slate-400 hover:text-blue-500",
              "hover:bg-blue-50 dark:hover:bg-blue-950/50",
            )}
            title="Відкрити оригінал"
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>
    </article>
  );
};
