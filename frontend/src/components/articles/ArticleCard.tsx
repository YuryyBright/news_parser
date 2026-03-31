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
        "hover:shadow-md dark:hover:shadow-slate-900",
        "transition-all duration-200 cursor-pointer",
        isRead && "opacity-60",
      )}
      onClick={onClick}
    >
      {/* Unread indicator */}
      {!isRead && (
        <div className="absolute left-0 top-4 bottom-4 w-0.5 bg-blue-500 rounded-full" />
      )}

      <div className="p-4">
        {/* Top row: badges */}
        <div className="flex items-center gap-2 flex-wrap mb-2">
          <ArticleBadge status={article.status} />
          <ScoreBadge score={article.relevance_score} />
          <span className="text-sm" title={article.language}>
            {languageFlag(article.language)} {article.language.toUpperCase()}
          </span>
          <div className="ml-auto flex items-center gap-1 text-xs text-slate-400 dark:text-slate-500">
            <Clock className="w-3 h-3" />
            {formatDate(article.published_at ?? article.created_at)}
          </div>
        </div>

        {/* Title */}
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

        {/* Tags */}
        <TagsList tags={article.tags} clickable className="mb-3" />

        {/* Bottom: actions */}
        <div
          className="flex items-center justify-between"
          onClick={(e) => e.stopPropagation()}
        >
          <FeedbackButtons articleId={article.id} compact />
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-400 hover:text-blue-500 transition-colors p-1"
            title="Відкрити оригінал"
          >
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>
      </div>
    </article>
  );
};
