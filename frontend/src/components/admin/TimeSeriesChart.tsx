// src/components/admin/TimeSeriesChart.tsx
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { useAdminTimeSeries } from "../../hooks/useAdmin";
import type { AdminFiltersParams } from "../../hooks/useAdmin";
import { format } from "date-fns";

interface Props {
  filters?: AdminFiltersParams;
}

export const TimeSeriesChart = ({ filters }: Props) => {
  const { data, isLoading } = useAdminTimeSeries(filters);

  if (isLoading)
    return (
      <div className="h-[350px] w-full animate-pulse rounded-2xl bg-slate-100 dark:bg-slate-800" />
    );

  const chartData = Array.isArray(data)
    ? data.map((p: any) => ({
        date: format(new Date(p.date), "dd MMM"),
        created: p.articles_created,
        accepted: p.articles_accepted,
        liked: p.feedback_liked,
        disliked: p.feedback_disliked,
      }))
    : [];

  return (
    <ResponsiveContainer width="100%" height={350}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="date" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} />
        <Tooltip />
        <Legend />
        <Line
          type="monotone"
          dataKey="created"
          stroke="#3b82f6"
          strokeWidth={3}
          name="Створено"
          dot={{ r: 4 }}
        />
        <Line
          type="monotone"
          dataKey="accepted"
          stroke="#10b981"
          strokeWidth={3}
          name="Прийнято"
          dot={{ r: 4 }}
        />
        <Line
          type="monotone"
          dataKey="liked"
          stroke="#f59e0b"
          strokeWidth={2.5}
          name="Лайки"
          dot={{ r: 3 }}
        />
        <Line
          type="monotone"
          dataKey="disliked"
          stroke="#ef4444"
          strokeWidth={2.5}
          name="Дизлайки"
          dot={{ r: 3 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
};
