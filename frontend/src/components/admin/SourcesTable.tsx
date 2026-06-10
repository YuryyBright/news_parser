// src/components/admin/SourcesTable.tsx
import { useSourcesPerformance } from "../../hooks/useAdmin";
import type { AdminFiltersParams } from "../../hooks/useAdmin";

interface Props {
  filters?: AdminFiltersParams;
}

export const SourcesTable = ({ filters }: Props) => {
  const { data, isLoading } = useSourcesPerformance(filters);

  const items: any[] = Array.isArray(data) ? data : [];

  if (isLoading)
    return (
      <div className="p-6 space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-10 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800"
          />
        ))}
      </div>
    );

  if (!items.length)
    return (
      <div className="py-12 text-center text-slate-400 dark:text-slate-500">
        Немає даних про джерела
      </div>
    );

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 dark:bg-slate-100 dark:bg-slate-800 dark:border-slate-300 dark:border-slate-700">
          <tr>
            <th className="px-6 py-4 text-left font-medium">Джерело</th>
            <th className="px-6 py-4 text-right font-medium">Всього статей</th>
            <th className="px-6 py-4 text-right font-medium">Прийнято</th>
            <th className="px-6 py-4 text-right font-medium">Середній score</th>
            <th className="px-6 py-4 text-center font-medium">Статус</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
          {items.map((s: any) => (
            <tr
              key={s.source_id}
              className="hover:bg-slate-50 dark:hover:bg-slate-800/50"
            >
              <td className="px-6 py-4 font-medium">{s.source_name}</td>
              <td className="px-6 py-4 text-right">{s.total_articles}</td>
              <td className="px-6 py-4 text-right font-medium text-emerald-600">
                {s.accepted_articles}
              </td>
              <td className="px-6 py-4 text-right font-medium">
                {s.avg_score.toFixed(2)}
              </td>
              <td className="px-6 py-4 text-center">
                {s.is_active ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-400">
                    ● Активне
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-400 dark:text-slate-500">
                    ● Неактивне
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
