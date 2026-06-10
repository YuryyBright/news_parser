// src/components/articles/FeedbackButtons.tsx
import { useEffect } from "react";
import { ThumbsUp, ThumbsDown, EyeOff } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { cn } from "../../lib/utils";
import { useFeedback, useExpireArticle } from "../../hooks/useArticles";
import { articleKeys } from "../../hooks/useArticles";

interface Props {
  articleId: string;
  initialLiked?: boolean | null;
  compact?: boolean;
}

export const FeedbackButtons = ({
  articleId,
  initialLiked = null, // ← тепер деструктурується
  compact = false,
}: Props) => {
  const qc = useQueryClient();
  const feedback = useFeedback();
  const expire = useExpireArticle();

  // Seed кешу при першому рендері або зміні initialLiked
  // Тільки якщо в кеші ще нічого немає — не затираємо optimistic update
  useEffect(() => {
    const cached = qc.getQueryData(articleKeys.feedback(articleId));
    if (cached === undefined) {
      qc.setQueryData(articleKeys.feedback(articleId), initialLiked);
    }
  }, [articleId, initialLiked, qc]);

  // Читаємо стан виключно з кешу — без HTTP запиту
  const currentLiked = qc.getQueryData<boolean | null>(
    articleKeys.feedback(articleId),
  );

  const isLiked = currentLiked === true;
  const isDisliked = currentLiked === false;

  const handleFeedback = (liked: boolean) => {
    feedback.mutate({ id: articleId, liked });
  };

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
        onClick={() => handleFeedback(true)}
        disabled={feedback.isPending}
        title={isLiked ? "Скасувати оцінку" : "Цікаво"}
        className={cn(
          btnBase,
          isLiked
            ? "bg-emerald-500 border-emerald-500 text-slate-900 dark:text-white dark:bg-emerald-600 dark:border-emerald-600"
            : "text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800 hover:bg-emerald-50 dark:hover:bg-emerald-950",
          "disabled:opacity-50",
        )}
      >
        <ThumbsUp
          className={cn(
            compact ? "w-3.5 h-3.5" : "w-4 h-4",
            isLiked && "fill-current",
          )}
        />
        {!compact && (
          <span className="hidden xs:inline">
            {isLiked ? "Оцінено" : "Цікаво"}
          </span>
        )}
      </button>

      <button
        onClick={() => handleFeedback(false)}
        disabled={feedback.isPending}
        title={isDisliked ? "Скасувати оцінку" : "Нецікаво"}
        className={cn(
          btnBase,
          isDisliked
            ? "bg-red-500 border-red-500 text-slate-900 dark:text-white dark:bg-red-600 dark:border-red-600"
            : "text-red-500 dark:text-red-400 border-red-200 dark:border-red-800 hover:bg-red-50 dark:hover:bg-red-950",
          "disabled:opacity-50",
        )}
      >
        <ThumbsDown
          className={cn(
            compact ? "w-3.5 h-3.5" : "w-4 h-4",
            isDisliked && "fill-current",
          )}
        />
        {!compact && (
          <span className="hidden xs:inline">
            {isDisliked ? "Оцінено" : "Нецікаво"}
          </span>
        )}
      </button>

      <button
        onClick={() => expire.mutate(articleId)}
        disabled={expire.isPending}
        title="Не показувати"
        className={cn(
          btnBase,
          "text-slate-400 dark:text-slate-500 dark:text-slate-500 border-slate-200 dark:border-slate-300 dark:border-slate-700",
          "hover:bg-slate-100 dark:hover:bg-slate-800",
          "disabled:opacity-50",
        )}
      >
        <EyeOff className={cn("w-4 h-4", compact && "w-3.5 h-3.5")} />
        {!compact && <span className="hidden sm:inline">Не показувати</span>}
      </button>
    </div>
  );
};
