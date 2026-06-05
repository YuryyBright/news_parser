// src/components/admin/PopularArticlesTable.tsx
import { usePopularArticles } from "../../hooks/useAdmin";
import type { AdminFiltersParams } from "../../hooks/useAdmin";
import { TrendingUp } from "lucide-react";

interface Props {
  filters?: AdminFiltersParams;
}

export const PopularArticlesTable = ({ filters }: Props) => {
  const { data } = usePopularArticles(10, filters);

  if (!data?.length) {
    return (
      <div className="py-12 text-center text-slate-400 dark:text-slate-500">
        Немає даних про популярні статті
      </div>
    );
  }

  const getLanguageEmoji = (lang: string) => {
    const emojis: Record<string, string> = {
      ro: "🇷🇴",
      sk: "🇸🇰",
      hu: "🇭🇺",
    };
    return emojis[lang] || "🌍";
  };

  const getScoreColor = (score: number) => {
    if (score >= 0.8) return "text-emerald-600";
    if (score >= 0.6) return "text-blue-600";
    if (score >= 0.4) return "text-amber-600";
    return "text-red-600";
  };

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 dark:bg-slate-100 dark:bg-slate-800 dark:border-slate-300 dark:border-slate-700">
          <tr>
            <th className="px-6 py-4 text-left font-medium">Назва</th>
            <th className="px-6 py-4 text-left font-medium">Джерело</th>
            <th className="px-6 py-4 text-center font-medium">Мова</th>
            <th className="px-6 py-4 text-right font-medium">Прочитано</th>
            <th className="px-6 py-4 text-right font-medium">👍 / 👎</th>
            <th className="px-6 py-4 text-right font-medium">Score</th>
            <th className="px-6 py-4 text-right font-medium">Вплив</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
          {data.map((article: any, idx: number) => (
            <tr
              key={article.article_id}
              className="hover:bg-slate-50 dark:hover:bg-slate-100 dark:bg-slate-800/50"
            >
              <td className="px-6 py-4">
                <a
                  href={`/article/${article.article_id}`}
                  className="font-medium text-blue-600 hover:underline truncate max-w-xs block"
                  title={article.title}
                >
                  {idx + 1}. {article.title.substring(0, 50)}...
                </a>
              </td>
              <td className="px-6 py-4 text-slate-400 dark:text-slate-600 dark:text-slate-400 dark:text-slate-500 dark:text-slate-400">
                {article.source_name}
              </td>
              <td className="px-6 py-4 text-center text-lg">
                {getLanguageEmoji(article.language)}
              </td>
              <td className="px-6 py-4 text-right font-medium">
                <div className="flex items-center justify-end gap-1">
                  <span className="text-lg">👁️</span>
                  {article.read_count}
                </div>
              </td>
              <td className="px-6 py-4 text-right font-medium">
                <span className="text-emerald-600">{article.liked}</span>
                {" / "}
                <span className="text-red-600">{article.disliked}</span>
              </td>
              <td
                className={`px-6 py-4 text-right font-bold ${getScoreColor(article.relevance_score)}`}
              >
                {article.relevance_score.toFixed(2)}
              </td>
              <td className="px-6 py-4 text-right">
                <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-3 py-1 text-xs font-medium text-blue-700 dark:bg-blue-900/50 dark:text-blue-400">
                  <TrendingUp className="h-3 w-3" />
                  {article.engagement_score.toFixed(0)}%
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
