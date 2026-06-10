// src/components/admin/UserStatsGrid.tsx
import { useUserStats } from "../../hooks/useAdmin";
import type { AdminFiltersParams } from "../../hooks/useAdmin";
import { Users, TrendingUp, User, UserPlus } from "lucide-react";
import { cn } from "../../lib/utils";

interface Props {
  // UserStats is global (no language filter on the backend),
  // but we accept the prop for API consistency.
  filters?: AdminFiltersParams;
}

const StatBox = ({
  label,
  value,
  icon,
  trend,
  color = "blue",
}: {
  label: string;
  value: string | number;
  icon?: React.ReactNode;
  trend?: number;
  color?: string;
}) => {
  const colorClasses = {
    blue: "bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 border-blue-200 dark:border-blue-700",
    green:
      "bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-700",
    purple:
      "bg-purple-50 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400 border-purple-200 dark:border-purple-700",
    orange:
      "bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400 border-amber-200 dark:border-amber-700",
  };

  return (
    <div
      className={cn(
        "rounded-2xl border-2 p-5 transition-all hover:shadow-lg",
        colorClasses[color as keyof typeof colorClasses] || colorClasses.blue,
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium opacity-75 mb-1">{label}</p>
          <p className="text-3xl font-bold">{value}</p>
          {trend !== undefined && (
            <p className="text-xs mt-2 flex items-center gap-1 opacity-75">
              {trend >= 0 ? "↑" : "↓"} {Math.abs(trend)}% від минулого
            </p>
          )}
        </div>
        {icon && <div className="rounded-xl p-2.5 opacity-25">{icon}</div>}
      </div>
    </div>
  );
};

export const UserStatsGrid = ({ filters: _filters }: Props) => {
  const { data, isLoading } = useUserStats();

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-24 rounded-2xl bg-slate-200 dark:bg-slate-700" />
      </div>
    );
  }

  if (!data) return null;

  const returningUsersTrend = data.returning_rate;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-1">
          👥 Активність користувачів
        </h2>
        <p className="text-slate-400 dark:text-slate-500 dark:text-slate-500 dark:text-slate-400">
          Детальна аналітика користувачів та їх взаємодії
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatBox
          label="Всього користувачів"
          value={data.total_users}
          icon={<Users className="h-5 w-5" />}
          color="blue"
        />
        <StatBox
          label="Активних сьогодні"
          value={data.active_today}
          icon={<TrendingUp className="h-5 w-5" />}
          color="green"
        />
        <StatBox
          label="Активних за тиждень"
          value={data.active_week}
          icon={<User className="h-5 w-5" />}
          color="purple"
        />
        <StatBox
          label="Нових сьогодні"
          value={data.new_today}
          icon={<UserPlus className="h-5 w-5" />}
          color="orange"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatBox label="Нових за тиждень" value={data.new_week} color="blue" />
        <StatBox
          label="Повертаються користувачі"
          value={`${data.returning_rate.toFixed(1)}%`}
          trend={data.returning_rate > 50 ? 5 : -3}
          color="green"
        />
        <StatBox
          label="Середній DAU/MAU"
          value={`${((data.active_today / data.total_users) * 100).toFixed(1)}%`}
          color="purple"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="rounded-2xl border-2 border-slate-200 dark:border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 p-6">
          <p className="text-sm font-medium text-slate-400 dark:text-slate-500 dark:text-slate-500 dark:text-slate-400 mb-2">
            Середня статей на користувача
          </p>
          <div className="flex items-end gap-4">
            <p className="text-4xl font-bold text-blue-600">
              {data.avg_articles_per_user.toFixed(1)}
            </p>
            <div className="flex-1 h-12 rounded-lg bg-gradient-to-r from-blue-100 to-blue-50 dark:from-blue-900/30 dark:to-blue-900/10 flex items-end justify-center">
              <div
                className="w-1 bg-blue-600 rounded-t-lg transition-all"
                style={{
                  height: `${Math.min((data.avg_articles_per_user / 10) * 100, 100)}%`,
                }}
              />
            </div>
          </div>
        </div>

        <div className="rounded-2xl border-2 border-slate-200 dark:border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 p-6">
          <p className="text-sm font-medium text-slate-400 dark:text-slate-500 dark:text-slate-500 dark:text-slate-400 mb-2">
            Середній фідбек на користувача
          </p>
          <div className="flex items-end gap-4">
            <p className="text-4xl font-bold text-emerald-600">
              {data.avg_feedback_per_user.toFixed(1)}
            </p>
            <div className="flex-1 h-12 rounded-lg bg-gradient-to-r from-emerald-100 to-emerald-50 dark:from-emerald-900/30 dark:to-emerald-900/10 flex items-end justify-center">
              <div
                className="w-1 bg-emerald-600 rounded-t-lg transition-all"
                style={{
                  height: `${Math.min((data.avg_feedback_per_user / 5) * 100, 100)}%`,
                }}
              />
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border-2 border-slate-200 dark:border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 p-6">
        <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
          📊 Метрики утримання
        </h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-slate-400 dark:text-slate-500 dark:text-slate-500 dark:text-slate-400">
              DAU (Active Today)
            </p>
            <p className="text-2xl font-bold text-blue-600 mt-1">
              {data.active_today}
            </p>
            <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
              {((data.active_today / data.total_users) * 100).toFixed(1)}% від
              всіх
            </p>
          </div>
          <div>
            <p className="text-sm text-slate-400 dark:text-slate-500 dark:text-slate-500 dark:text-slate-400">
              WAU (Active Week)
            </p>
            <p className="text-2xl font-bold text-emerald-600 mt-1">
              {data.active_week}
            </p>
            <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
              {((data.active_week / data.total_users) * 100).toFixed(1)}% від
              всіх
            </p>
          </div>
        </div>
        <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-300 dark:border-slate-700">
          <p className="text-xs text-slate-400 dark:text-slate-500 dark:text-slate-500 dark:text-slate-400 mb-2">
            Утримання користувачів
          </p>
          <div className="w-full h-2 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-green-500 to-emerald-500 transition-all duration-500"
              style={{ width: `${Math.min(returningUsersTrend, 100)}%` }}
            />
          </div>
          <p className="text-sm font-semibold text-slate-900 dark:text-white mt-2">
            {returningUsersTrend.toFixed(1)}% повертаються
          </p>
        </div>
      </div>
    </div>
  );
};
