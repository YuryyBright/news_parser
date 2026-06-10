// src/components/admin/ArticleStatusChart.tsx
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { useArticleStatusDistribution } from "../../hooks/useAdmin";
import type { AdminFiltersParams } from "../../hooks/useAdmin";

const STATUS_COLORS: Record<string, string> = {
  accepted: "#10b981",
  rejected: "#ef4444",
  pending: "#f59e0b",
  expired: "#8b5cf6",
};
const STATUS_LABELS: Record<string, string> = {
  accepted: "✅ Прийнято",
  rejected: "❌ Відхилено",
  pending: "⏳ Очікування",
  expired: "⌛ Застаріло",
};

interface Props {
  filters?: AdminFiltersParams;
}

export const ArticleStatusChart = ({ filters }: Props) => {
  const { data, isLoading } = useArticleStatusDistribution(filters);

  const items: any[] = Array.isArray(data) ? data : [];

  if (isLoading)
    return (
      <div className="flex h-[300px] items-center justify-center">
        <div className="h-32 w-32 animate-pulse rounded-full bg-slate-100 dark:bg-slate-800" />
      </div>
    );

  if (!items.length)
    return (
      <div className="flex h-[300px] items-center justify-center text-slate-400 dark:text-slate-500">
        Немає даних про статуси
      </div>
    );

  const formattedData = items.map((item: any) => ({
    ...item,
    name: STATUS_LABELS[item.status] || item.status,
  }));

  return (
    <ResponsiveContainer width="100%" height={340}>
      <PieChart>
        <Pie
          data={formattedData}
          dataKey="count"
          nameKey="name"
          cx="50%"
          cy="48%"
          outerRadius={100}
          innerRadius={35}
          label={({ percentage }) =>
            percentage > 3 ? `${Number(percentage).toFixed(0)}%` : ""
          }
          labelLine={false}
        >
          {formattedData.map((item: any) => (
            <Cell
              key={item.status}
              fill={STATUS_COLORS[item.status] || "#6366f1"}
            />
          ))}
        </Pie>
        <Tooltip
          formatter={(value: number) => [`${value} статей`, "Кількість"]}
        />
        <Legend verticalAlign="bottom" height={40} />
      </PieChart>
    </ResponsiveContainer>
  );
};
