// src/pages/TasksPage.tsx
import {
  XCircle,
  Clock,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { useTasks, useCancelTask } from "../hooks/useSources";
import { cn, formatDateFull } from "../lib/utils";
import type { TaskStatus } from "../api/types";

const STATUS_ICONS: Record<TaskStatus, React.ReactNode> = {
  pending: <Clock className="w-4 h-4 text-amber-500" />,
  in_progress: <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />,
  completed: <CheckCircle2 className="w-4 h-4 text-emerald-500" />,
  failed: <AlertCircle className="w-4 h-4 text-red-500" />,
  cancelled: <XCircle className="w-4 h-4 text-slate-400" />,
};

export const TasksPage = () => {
  const { data, isLoading } = useTasks({ limit: 100 });
  const cancel = useCancelTask();
  const tasks = data?.tasks ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            Фонові задачі
          </h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm mt-0.5">
            {tasks.length} задач · оновлення кожні 10с
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="h-16 bg-slate-100 dark:bg-slate-800 rounded-xl animate-pulse"
            />
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden bg-white dark:bg-slate-900">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50">
                <th className="text-left px-4 py-3 font-medium text-slate-500">
                  Статус
                </th>
                <th className="text-left px-4 py-3 font-medium text-slate-500">
                  Задача
                </th>
                <th className="text-left px-4 py-3 font-medium text-slate-500">
                  Створено
                </th>
                <th className="text-left px-4 py-3 font-medium text-slate-500">
                  Завершено
                </th>
                <th className="text-left px-4 py-3 font-medium text-slate-500">
                  Помилка
                </th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {tasks.map((task) => (
                <tr key={task.task_id}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      {STATUS_ICONS[task.status as TaskStatus]}
                      <span className="text-xs text-slate-500">
                        {task.status}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-mono text-xs text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded">
                      {task.task_name}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-400">
                    {formatDateFull(task.created_at)}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-400">
                    {formatDateFull(task.finished_at)}
                  </td>
                  <td className="px-4 py-3 text-xs text-red-400 max-w-xs truncate">
                    {task.error ?? "—"}
                  </td>
                  <td className="px-4 py-3">
                    {(task.status === "pending" ||
                      task.status === "in_progress") && (
                      <button
                        onClick={() => cancel.mutate(task.task_id)}
                        disabled={cancel.isPending}
                        className="px-2 py-1 rounded text-xs text-red-500 border border-red-200 hover:bg-red-50 dark:hover:bg-red-950 transition-colors disabled:opacity-50"
                      >
                        Скасувати
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {tasks.length === 0 && (
            <div className="text-center py-16 text-slate-400">
              <p>Задач ще немає</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
