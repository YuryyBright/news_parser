// src/components/admin/TopTagsChart.tsx
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useTopTags } from "../../hooks/useAdmin";
import type { AdminFiltersParams } from "../../hooks/useAdmin";

interface Props {
  filters?: AdminFiltersParams;
}

export const TopTagsChart = ({ filters }: Props) => {
  const { data, isLoading } = useTopTags(10, filters);

  const items: any[] = Array.isArray(data) ? data : [];

  if (isLoading)
    return (
      <div className="h-[320px] w-full animate-pulse rounded-xl bg-slate-100 dark:bg-slate-100 dark:bg-slate-800" />
    );

  if (!items.length)
    return (
      <div className="flex h-[300px] items-center justify-center text-slate-400 dark:text-slate-500">
        Немає даних про теги
      </div>
    );

  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={items} layout="vertical" margin={{ left: 80, right: 20 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis type="number" />
        <YAxis type="category" dataKey="tag_name" tick={{ fontSize: 13 }} />
        <Tooltip />
        <Bar
          dataKey="articles_count"
          fill="#3b82f6"
          radius={[0, 8, 8, 0]}
          name="Статей"
        />
      </BarChart>
    </ResponsiveContainer>
  );
};
