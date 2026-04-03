// src/components/articles/TagsList.tsx
import { Tag, X } from "lucide-react";
import { cn } from "../../lib/utils";
import { useArticlesStore } from "../../store/useArticlesStore";

interface Props {
  tags: string[];
  /** Якщо true — клік по тегу встановлює фільтр по тегу в ArticlesStore */
  clickable?: boolean;
  /** Активний тег (для підсвітки) */
  activeTag?: string | null;
  className?: string;
}

export const TagsList = ({
  tags,
  clickable = false,
  activeTag,
  className,
}: Props) => {
  const setFilter = useArticlesStore((s) => s.setFilter);
  const filters = useArticlesStore((s) => s.filters);

  if (!tags?.length) return null;

  const currentTag = activeTag ?? filters.tag ?? null;

  const handleTagClick = (tag: string) => {
    if (!clickable) return;
    // Якщо цей тег вже активний — знімаємо фільтр
    if (currentTag === tag) {
      setFilter("tag", null);
    } else {
      setFilter("tag", tag);
    }
  };

  return (
    <div className={cn("flex flex-wrap gap-1", className)}>
      {tags.map((tag) => {
        const isActive = currentTag === tag;
        return (
          <button
            key={tag}
            disabled={!clickable}
            onClick={() => handleTagClick(tag)}
            className={cn(
              "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs transition-all duration-150",
              "border",
              isActive
                ? "bg-blue-500 text-white border-blue-500 shadow-sm"
                : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700",
              clickable &&
                !isActive && [
                  "hover:bg-blue-50 dark:hover:bg-blue-950",
                  "hover:text-blue-600 dark:hover:text-blue-400",
                  "hover:border-blue-200 dark:hover:border-blue-800",
                  "cursor-pointer",
                ],
              clickable && isActive && "cursor-pointer",
            )}
          >
            {isActive ? (
              <X className="w-2.5 h-2.5" />
            ) : (
              <Tag className="w-2.5 h-2.5" />
            )}
            {tag}
          </button>
        );
      })}
    </div>
  );
};
