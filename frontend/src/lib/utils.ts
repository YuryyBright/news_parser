// src/lib/utils.ts
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { formatDistanceToNow, format } from "date-fns";
import { hu, ro, sk, uk } from "date-fns/locale";

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));

export const formatDate = (dateStr: string | null): string => {
  if (!dateStr) return "—";
  try {
    return formatDistanceToNow(new Date(dateStr), {
      addSuffix: true,
      locale: uk,
    });
  } catch {
    return "—";
  }
};

export const formatDateFull = (dateStr: string | null): string => {
  if (!dateStr) return "—";
  try {
    return format(new Date(dateStr), "dd.MM.yyyy HH:mm", { locale: uk });
  } catch {
    return "—";
  }
};

export const scoreColor = (score: number): string => {
  if (score >= 0.7)
    return "text-emerald-600 bg-emerald-50 dark:bg-emerald-950 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800";
  if (score >= 0.4)
    return "text-amber-600 bg-amber-50 dark:bg-amber-950 dark:text-amber-400 border-amber-200 dark:border-amber-800";
  return "text-slate-500 bg-slate-50 dark:bg-slate-800 dark:text-slate-400 border-slate-200 dark:border-slate-700";
};

export const statusColor = (status: string): string => {
  const map: Record<string, string> = {
    new: "text-blue-600 bg-blue-50 dark:bg-blue-950 dark:text-blue-400 border-blue-200",
    accepted:
      "text-emerald-600 bg-emerald-50 dark:bg-emerald-950 dark:text-emerald-400 border-emerald-200",
    rejected:
      "text-red-500 bg-red-50 dark:bg-red-950 dark:text-red-400 border-red-200",
    expired:
      "text-slate-400 bg-slate-50 dark:bg-slate-800 dark:text-slate-500 border-slate-200",
    processing:
      "text-violet-600 bg-violet-50 dark:bg-violet-950 dark:text-violet-400 border-violet-200",
    unread:
      "text-blue-600 bg-blue-50 dark:bg-blue-950 dark:text-blue-400 border-blue-200",
    read: "text-slate-400 bg-slate-50 dark:bg-slate-800 border-slate-200",
  };
  return map[status] ?? "text-slate-500 bg-slate-50 border-slate-200";
};
