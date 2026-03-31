// src/components/articles/ArticleBadge.tsx
// Design: Editorial Dark — status pill system
import { cn } from "../../lib/utils";

const STATUS_CONFIG: Record<
  string,
  { label: string; style: string; dot: string }
> = {
  new: {
    label: "Нова",
    style: "bg-amber-500/10 text-amber-400 border-amber-500/25",
    dot: "bg-amber-400 animate-pulse",
  },
  accepted: {
    label: "Прийнята",
    style: "bg-emerald-500/10 text-emerald-400 border-emerald-500/25",
    dot: "bg-emerald-400",
  },
  rejected: {
    label: "Відхилена",
    style: "bg-red-500/10 text-red-400 border-red-500/25",
    dot: "bg-red-400",
  },
  expired: {
    label: "Застаріла",
    style: "bg-zinc-500/10 text-zinc-500 border-zinc-500/20",
    dot: "bg-zinc-500",
  },
  processing: {
    label: "Обробка",
    style: "bg-blue-500/10 text-blue-400 border-blue-500/25",
    dot: "bg-blue-400 animate-pulse",
  },
  unread: {
    label: "Нова",
    style: "bg-amber-500/10 text-amber-400 border-amber-500/25",
    dot: "bg-amber-400 animate-pulse",
  },
  read: {
    label: "Прочитана",
    style: "bg-zinc-500/10 text-zinc-500 border-zinc-500/20",
    dot: "bg-zinc-500",
  },
};

const FALLBACK = {
  label: "",
  style: "bg-zinc-500/10 text-zinc-500 border-zinc-500/20",
  dot: "bg-zinc-500",
};

interface Props {
  status: string;
  className?: string;
}

export const ArticleBadge = ({ status, className }: Props) => {
  const cfg = STATUS_CONFIG[status] ?? { ...FALLBACK, label: status };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium border",
        cfg.style,
        className,
      )}
    >
      <span className={cn("w-1.5 h-1.5 rounded-full", cfg.dot)} />
      {cfg.label}
    </span>
  );
};
