// src/components/admin/LanguagePieChart.tsx
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { useLanguageDistribution } from "../../hooks/useAdmin";
import type { AdminFiltersParams } from "../../hooks/useAdmin";

const COLORS = [
  "#3b82f6",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#ec489a",
  "#14b8a6",
  "#f97316",
];
const LANGUAGE_LABELS: Record<string, string> = {
  ro: "🇷🇴 Română",
  sk: "🇸🇰 Slovenčina",
  hu: "🇭🇺 Magyar",
  pl: "🇵🇱 Polski",
  ua: "🇺🇦 Українська",
};

interface Props {
  filters?: AdminFiltersParams;
}

export const LanguagePieChart = ({ filters }: Props) => {
  const { data, isLoading } = useLanguageDistribution(filters);

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
        Немає даних про мови
      </div>
    );

  const formattedData = items.map((item: any) => ({
    ...item,
    language: LANGUAGE_LABELS[item.language] || item.language,
  }));

  return (
    <ResponsiveContainer width="100%" height={340}>
      <PieChart>
        <Pie
          data={formattedData}
          dataKey="count"
          nameKey="language"
          cx="50%"
          cy="48%"
          outerRadius={115}
          innerRadius={45}
          label={({ name, percent }) =>
            percent > 4
              ? `${name.split(" ")[1]} ${(percent * 100).toFixed(0)}%`
              : ""
          }
          labelLine={false}
        >
          {formattedData.map((_: any, idx: number) => (
            <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip formatter={(value: number, name: string) => [value, name]} />
        <Legend verticalAlign="bottom" height={80} iconType="circle" />
      </PieChart>
    </ResponsiveContainer>
  );
};
