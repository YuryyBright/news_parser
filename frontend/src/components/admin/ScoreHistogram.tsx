// src/components/admin/ScoreHistogram.tsx
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useScoreHistogram } from "../../hooks/useAdmin";
import type { AdminFiltersParams } from "../../hooks/useAdmin";

interface Props {
  filters?: AdminFiltersParams;
}

export const ScoreHistogram = ({ filters }: Props) => {
  const { data, isLoading } = useScoreHistogram(12, filters);

  const items: any[] = Array.isArray(data) ? data : [];

  if (isLoading)
    return (
      <div className="h-[320px] w-full animate-pulse rounded-xl bg-slate-100 dark:bg-slate-100 dark:bg-slate-800" />
    );

  if (!items.length) return null;

  const chartData = items.map((b: any) => ({
    range: `${b.bucket_min.toFixed(1)}–${b.bucket_max.toFixed(1)}`,
    count: b.count,
  }));

  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="range" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} />
        <Tooltip />
        <Bar
          dataKey="count"
          fill="#6366f1"
          radius={[8, 8, 0, 0]}
          name="Кількість статей"
        />
      </BarChart>
    </ResponsiveContainer>
  );
};
