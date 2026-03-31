// src/components/articles/
import { Tag } from "lucide-react";
import { cn } from "../../lib/utils";
import { useArticlesStore } from "../../store/useArticlesStore";

interface Props {
  tags: string[];
  clickable?: boolean;
  className?: string;
}

export const TagsList = ({ tags, clickable = false, className }: Props) => {
  const setFilter = useArticlesStore((s) => s.setFilter);

  if (!tags?.length) return null;

  return (
    <div className={cn("flex flex-wrap gap-1", className)}>
      {tags.map((tag) => (
        <button
          key={tag}
          disabled={!clickable}
          onClick={() => clickable && setFilter("status", null)}
          className={cn(
            "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs",
            "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400",
            "border border-slate-200 dark:border-slate-700",
            clickable &&
              "hover:bg-blue-50 dark:hover:bg-blue-950 hover:text-blue-600 dark:hover:text-blue-400 hover:border-blue-200 cursor-pointer transition-colors",
          )}
        >
          <Tag className="w-2.5 h-2.5" />
          {tag}
        </button>
      ))}
    </div>
  );
};
