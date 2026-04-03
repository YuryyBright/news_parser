// src/components/articles/ArticleCard.tsx
import { ExternalLink, Clock } from "lucide-react";
import { cn, formatDate, languageFlag } from "../../lib/utils";
import { ScoreBadge } from "./ScoreBadge";
import { ArticleBadge } from "./ArticleBadge";
import { TagsList } from "./TagsList";
import { FeedbackButtons } from "./FeedbackButtons";
import type { Article } from "../../api/types";

interface Props {
  article: Article;
  onClick?: () => void;
  isRead?: boolean;
}

export const ArticleCard = ({ article, onClick, isRead }: Props) => {
  return (
    <article
      className={cn(
        "group relative bg-white dark:bg-slate-900 rounded-xl border",
        "border-slate-200 dark:border-slate-800",
        "hover:border-blue-300 dark:hover:border-blue-700",
        "hover:shadow-lg dark:hover:shadow-slate-950/50",
        "transition-all duration-200",
        onClick && "cursor-pointer",
        isRead && "opacity-55",
      )}
      onClick={onClick}
    >
      {/* Unread indicator stripe */}
      {!isRead && (
        <div className="absolute left-0 top-3 bottom-3 w-[3px] bg-blue-500 rounded-full" />
      )}

      <div className="p-4 pl-5">
        {/* Top row: status + score + language + date */}
        <div className="flex items-center gap-2 flex-wrap mb-2.5">
          <ArticleBadge status={article.status} />
          <ScoreBadge score={article.relevance_score} />
          <span className="text-base leading-none" title={article.language}>
            {languageFlag(article.language)}
          </span>
          <div className="ml-auto flex items-center gap-1 text-xs text-slate-400 dark:text-slate-500 tabular-nums">
            <Clock className="w-3 h-3 shrink-0" />
            {formatDate(article.published_at ?? article.created_at)}
          </div>
        </div>

        {/* Title */}
        <h3
          className={cn(
            "text-sm font-semibold leading-snug mb-2.5",
            "text-slate-900 dark:text-white",
            "group-hover:text-blue-600 dark:group-hover:text-blue-400",
            "transition-colors line-clamp-2",
          )}
        >
          {article.title}
        </h3>

        {/* Tags */}
        {article.tags.length > 0 && (
          <TagsList tags={article.tags} clickable className="mb-3" />
        )}

        {/* Bottom actions row */}
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
