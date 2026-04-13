// src/components/articles/FeedbackButtons.tsx
import { ThumbsUp, ThumbsDown, EyeOff } from "lucide-react";
import { cn } from "../../lib/utils";
import { useFeedback, useExpireArticle } from "../../hooks/useArticles";

interface Props {
  articleId: string;
  compact?: boolean;
}

export const FeedbackButtons = ({ articleId, compact = false }: Props) => {
  const feedback = useFeedback();
  const expire = useExpireArticle();

  const btnBase = cn(
    "flex items-center gap-1.5 rounded-lg font-medium border transition-all duration-150",
    "active:scale-95",
    compact
      ? "px-2 py-1 text-xs min-h-[28px]"
      : "px-3 py-1.5 text-sm min-h-[36px] sm:min-h-[32px]",
  );

  return (
    <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
      <button
        onClick={() => feedback.mutate({ id: articleId, liked: true })}
        disabled={feedback.isPending}
        className={cn(
          btnBase,
          "text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800",
          "hover:bg-emerald-50 dark:hover:bg-emerald-950",
          "disabled:opacity-50",
        )}
      >
        <ThumbsUp className={cn("w-4 h-4", compact && "w-3.5 h-3.5")} />
        {!compact && <span className="hidden xs:inline">Цікаво</span>}
      </button>

      <button
        onClick={() => feedback.mutate({ id: articleId, liked: false })}
        disabled={feedback.isPending}
        className={cn(
          btnBase,
          "text-red-500 dark:text-red-400 border-red-200 dark:border-red-800",
          "hover:bg-red-50 dark:hover:bg-red-950",
          "disabled:opacity-50",
        )}
      >
        <ThumbsDown className={cn("w-4 h-4", compact && "w-3.5 h-3.5")} />
        {!compact && <span className="hidden xs:inline">Нецікаво</span>}
      </button>

      <button
        onClick={() => expire.mutate(articleId)}
        disabled={expire.isPending}
        className={cn(
          btnBase,
          "text-slate-400 dark:text-slate-500 border-slate-200 dark:border-slate-700",
          "hover:bg-slate-100 dark:hover:bg-slate-800",
          "disabled:opacity-50",
        )}
        title="Не показувати"
      >
        <EyeOff className={cn("w-4 h-4", compact && "w-3.5 h-3.5")} />
        {!compact && <span className="hidden sm:inline">Не показувати</span>}
      </button>
    </div>
  );
};
