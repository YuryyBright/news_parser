// src/pages/SourcesPage.tsx
import { useState } from "react";
import { Plus, Play, Trash2, Database } from "lucide-react";
import {
  useSources,
  useCreateSource,
  useDeactivateSource,
  useTriggerSource,
} from "../hooks/useSources";
import { cn } from "../lib/utils";
import type { SourceType } from "../api/types";

export const SourcesPage = () => {
  const [showForm, setShowForm] = useState(false);
  const { data: sources = [], isLoading } = useSources(false);
  const create = useCreateSource();
  const deactivate = useDeactivateSource();
  const trigger = useTriggerSource();

  const [form, setForm] = useState({
    name: "",
    url: "",
    source_type: "rss" as SourceType,
    fetch_interval_seconds: 300,
  });

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await create.mutateAsync(form);
    setForm({
      name: "",
      url: "",
      source_type: "rss",
      fetch_interval_seconds: 300,
    });
    setShowForm(false);
  };

  const inputClass = cn(
    "px-3 py-2 rounded-lg border text-sm w-full",
    "bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700",
    "text-slate-900 dark:text-white placeholder-slate-400",
    "focus:outline-none focus:ring-2 focus:ring-blue-500",
  );

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            Джерела
          </h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm mt-0.5">
            {sources.length} джерел
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-500 hover:bg-blue-600 text-white text-sm font-medium transition-colors"
        >
          <Plus className="w-4 h-4" />
          Додати джерело
        </button>
      </div>

      {/* Add form */}
      {showForm && (
        <form
          onSubmit={handleCreate}
          className="mb-6 p-5 rounded-xl border bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800"
        >
          <h3 className="font-semibold text-slate-900 dark:text-white mb-4">
            Нове джерело
          </h3>
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Назва</label>
              <input
                value={form.name}
                onChange={(e) =>
                  setForm((f) => ({ ...f, name: e.target.value }))
                }
                placeholder="BBC News"
                required
                className={inputClass}
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">URL</label>
              <input
                value={form.url}
                onChange={(e) =>
                  setForm((f) => ({ ...f, url: e.target.value }))
                }
                placeholder="https://feeds.bbci.co.uk/news/rss.xml"
                required
                type="url"
                className={inputClass}
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Тип</label>
              <select
                value={form.source_type}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    source_type: e.target.value as SourceType,
                  }))
                }
                className={inputClass}
              >
                {["rss", "web", "api", "telegram"].map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">
                Інтервал (сек)
              </label>
              <input
                value={form.fetch_interval_seconds}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    fetch_interval_seconds: parseInt(e.target.value),
                  }))
                }
                type="number"
                min={60}
                className={inputClass}
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={create.isPending}
              className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white text-sm rounded-lg font-medium disabled:opacity-50"
            >
              {create.isPending ? "Додаємо..." : "Додати"}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-4 py-2 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-sm rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              Скасувати
            </button>
          </div>
        </form>
      )}

      {/* Sources table */}
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
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
                <th className="text-left px-4 py-3 font-medium text-slate-500 dark:text-slate-400">
                  Назва
                </th>
                <th className="text-left px-4 py-3 font-medium text-slate-500 dark:text-slate-400">
                  Тип
                </th>
                <th className="text-left px-4 py-3 font-medium text-slate-500 dark:text-slate-400">
                  Інтервал
                </th>
                <th className="text-left px-4 py-3 font-medium text-slate-500 dark:text-slate-400">
                  Статус
                </th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {sources.map((src) => (
                <tr
                  key={src.id}
                  className={cn(
                    "transition-colors",
                    !src.is_active && "opacity-50",
                  )}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-900 dark:text-white">
                      {src.name}
                    </div>
                    <div className="text-xs text-slate-400 truncate max-w-xs">
                      {src.url}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 text-xs font-mono border border-slate-200 dark:border-slate-700">
                      {src.source_type}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-500 dark:text-slate-400">
                    {src.fetch_interval_seconds}с
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={cn(
                        "px-2 py-0.5 rounded-md text-xs font-medium border",
                        src.is_active
                          ? "text-emerald-600 bg-emerald-50 dark:bg-emerald-950 dark:text-emerald-400 border-emerald-200"
                          : "text-slate-400 bg-slate-50 dark:bg-slate-800 border-slate-200",
                      )}
                    >
                      {src.is_active ? "Активне" : "Неактивне"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2 justify-end">
                      <button
                        onClick={() => trigger.mutate(src.id)}
                        disabled={trigger.isPending}
                        title="Запустити парсинг"
                        className="p-1.5 rounded-lg text-slate-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-950 transition-colors disabled:opacity-50"
                      >
                        <Play className="w-4 h-4" />
                      </button>
                      {src.is_active && (
                        <button
                          onClick={() => deactivate.mutate(src.id)}
                          disabled={deactivate.isPending}
                          title="Деактивувати"
                          className="p-1.5 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950 transition-colors disabled:opacity-50"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {sources.length === 0 && (
            <div className="text-center py-16 text-slate-400">
              <Database className="w-10 h-10 mx-auto mb-3" />
              <p>Джерел ще немає</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
