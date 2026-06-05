// src/components/admin/StatsCard.tsx
import { cn } from "../../lib/utils";

interface Props {
  title: string;
  value: number | string;
  icon?: React.ReactNode;
  trend?: number;
  className?: string;
}

export const StatsCard = ({ title, value, icon, trend, className }: Props) => (
  <div
    className={cn(
      "group rounded-3xl border border-slate-200 bg-white p-6 transition-all hover:-translate-y-1 hover:shadow-xl dark:border-slate-300 dark:border-slate-700 dark:bg-slate-50 dark:bg-slate-900",
      className,
    )}
  >
    <div className="flex items-start justify-between">
      <div className="space-y-1">
        <p className="text-sm font-medium text-slate-400 dark:text-slate-500 dark:text-slate-400 dark:text-slate-500 dark:text-slate-400">
          {title}
        </p>
        <p className="text-3xl font-semibold tracking-tighter text-slate-900 dark:text-slate-900 dark:text-white">
          {value}
        </p>
      </div>

      {icon && (
        <div className="rounded-2xl bg-slate-100 p-3 text-slate-400 dark:text-slate-500 dark:text-slate-400 transition-all group-hover:bg-blue-100 group-hover:text-blue-600 dark:bg-slate-100 dark:bg-slate-800 dark:group-hover:bg-blue-950">
          {icon}
        </div>
      )}
    </div>

    {trend !== undefined && (
      <div
        className={cn(
          "mt-4 flex items-center gap-1 text-sm font-medium",
          trend >= 0 ? "text-emerald-500" : "text-red-500",
        )}
      >
        {trend >= 0 ? "↑" : "↓"} {Math.abs(trend)}%
        <span className="text-slate-400 dark:text-slate-500 dark:text-slate-400 text-xs">
          від минулого періоду
        </span>
      </div>
    )}
  </div>
);
