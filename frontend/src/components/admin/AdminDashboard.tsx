// src/components/admin/AdminDashboard.tsx
import { useAdminOverview } from "../../hooks/useAdmin";
import { TimeSeriesChart } from "./TimeSeriesChart";
import { LanguagePieChart } from "./LanguagePieChart";
import { TopTagsChart } from "./TopTagsChart";
import { ScoreHistogram } from "./ScoreHistogram";
import { SourcesTable } from "./SourcesTable";
import { ArticleStatusChart } from "./ArticleStatusChart";
import { PopularArticlesTable } from "./PopularArticlesTable";
import { UserStatsGrid } from "./UserStatsGrid";
import { useAdminStore } from "../../store/useAdminStore";
import {
  Calendar,
  Users,
  TrendingUp,
  BarChart3,
  Globe,
  Tag,
  Flame,
  PieChart,
  Activity,
  FileText,
  CircleCheck,
  CircleX,
  Eye,
  ThumbsUp,
  Radio,
  Zap,
  RefreshCw,
  ChevronDown,
} from "lucide-react";

// ─── helpers ────────────────────────────────────────────────────────────────

function fmt(n: number | undefined | null): string {
  if (n === undefined || n === null) return "—";
  const abs = Math.abs(n);
  if (abs >= 1_000_000)
    return (n / 1_000_000).toFixed(1).replace(/\.0$/, "") + "M";
  if (abs >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, "") + "K";
  return String(n);
}

function fmtPct(n: number | undefined | null): string {
  if (n === undefined || n === null) return "—";
  return n.toFixed(1) + "%";
}

// ─── KPI Card ────────────────────────────────────────────────────────────────

interface KpiCardProps {
  label: string;
  value: string | number;
  sub?: string;
  badge?: { text: string; color: "green" | "red" | "blue" | "amber" | "slate" };
  icon: React.ReactNode;
  accent?: string;
}

const BADGE: Record<string, string> = {
  green:
    "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
  red: "bg-red-50 text-red-600 dark:bg-red-900/40 dark:text-red-300",
  blue: "bg-blue-50 text-blue-600 dark:bg-blue-900/40 dark:text-blue-300",
  amber: "bg-amber-50 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  slate:
    "bg-slate-100 text-slate-400 dark:text-slate-600 dark:bg-slate-700 dark:text-slate-700 dark:text-slate-300",
};

function KpiCard({
  label,
  value,
  sub,
  badge,
  icon,
  accent = "blue",
}: KpiCardProps) {
  const accentMap: Record<string, string> = {
    blue: "text-blue-500",
    green: "text-emerald-500",
    amber: "text-amber-500",
    red: "text-red-500",
    purple: "text-violet-500",
  };
  return (
    <div className="group relative flex flex-col gap-3 rounded-2xl border border-slate-100 bg-white p-5 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md hover:shadow-slate-100 dark:border-slate-300 dark:border-slate-700/60 dark:bg-slate-50 dark:bg-slate-900 dark:hover:shadow-none">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-widest text-slate-400 dark:text-slate-500 dark:text-slate-400 dark:text-slate-400 dark:text-slate-500">
          {label}
        </span>
        <span
          className={`shrink-0 [&>svg]:h-4 [&>svg]:w-4 ${accentMap[accent] ?? accentMap.blue} opacity-60 transition-opacity group-hover:opacity-100`}
        >
          {icon}
        </span>
      </div>
      <div className="flex items-end justify-between gap-2">
        <span className="text-[26px] font-semibold leading-none tracking-tight text-slate-900 dark:text-slate-900 dark:text-white">
          {typeof value === "number" ? fmt(value) : value}
        </span>
        {badge && (
          <span
            className={`inline-block rounded-full px-2.5 py-0.5 text-[11px] font-medium ${BADGE[badge.color]}`}
          >
            {badge.text}
          </span>
        )}
      </div>
      {sub && (
        <span className="text-xs text-slate-400 dark:text-slate-500 dark:text-slate-400 dark:text-slate-400 dark:text-slate-500">
          {sub}
        </span>
      )}
    </div>
  );
}

// ─── Section label ────────────────────────────────────────────────────────────

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-widest text-slate-400 dark:text-slate-500 dark:text-slate-400 dark:text-slate-400 dark:text-slate-500 before:h-px before:w-4 before:bg-current before:opacity-40 after:h-px after:flex-1 after:bg-current after:opacity-20">
      {children}
    </p>
  );
}

// ─── Panel ────────────────────────────────────────────────────────────────────

interface PanelProps {
  title: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  noPadding?: boolean;
}

function Panel({
  title,
  icon,
  children,
  className = "",
  noPadding = false,
}: PanelProps) {
  return (
    <div
      className={`overflow-hidden rounded-2xl border border-slate-100 bg-white dark:border-slate-300 dark:border-slate-700/60 dark:bg-slate-50 dark:bg-slate-900 ${className}`}
    >
      <div
        className={`flex items-center gap-2 border-b border-slate-100 px-5 py-4 dark:border-slate-300 dark:border-slate-700/60`}
      >
        {icon && (
          <span className="shrink-0 [&>svg]:h-4 [&>svg]:w-4 [&>svg]:text-slate-400 dark:text-slate-500 dark:text-slate-400 dark:[&>svg]:text-slate-400 dark:text-slate-500">
            {icon}
          </span>
        )}
        <h2 className="text-sm font-medium text-slate-700 dark:text-slate-700 dark:text-slate-300">
          {title}
        </h2>
      </div>
      <div className={noPadding ? "" : "p-5"}>{children}</div>
    </div>
  );
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-xl bg-slate-100 dark:bg-slate-100 dark:bg-slate-800 ${className}`}
    />
  );
}

// ─── Active filter pills ──────────────────────────────────────────────────────

function FilterPill({
  label,
  onRemove,
}: {
  label: string;
  onRemove: () => void;
}) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700 dark:border-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
      {label}
      <button
        onClick={onRemove}
        className="ml-0.5 rounded-full hover:text-blue-900 dark:hover:text-blue-100"
      >
        ×
      </button>
    </span>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export const AdminDashboard = () => {
  const { fromDate, toDate, language, setDateRange, setLanguage, reset } =
    useAdminStore();
  const filters = {
    from_date: fromDate ?? undefined,
    to_date: toDate ?? undefined,
    language: language ?? undefined,
  };

  const { data: overview, isLoading, refetch } = useAdminOverview(filters);

  const hasFilters = !!(fromDate || toDate || language);

  const likedTotal =
    (overview?.liked_feedback ?? 0) + (overview?.disliked_feedback ?? 0);
  const likedPct =
    likedTotal > 0 ? ((overview?.liked_feedback ?? 0) / likedTotal) * 100 : 0;

  return (
    <div className="space-y-8 pb-16">
      {/* ── Header ── */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-900 dark:text-slate-900 dark:text-white">
            Аналітика системи
          </h1>
          <p className="mt-0.5 text-sm text-slate-400 dark:text-slate-500 dark:text-slate-400 dark:text-slate-500 dark:text-slate-400">
            Контент, користувачі та джерела
          </p>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Date range */}
          <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm dark:border-slate-300 dark:border-slate-700 dark:bg-slate-50 dark:bg-slate-900">
            <Calendar className="h-3.5 w-3.5 shrink-0 text-slate-400 dark:text-slate-500 dark:text-slate-400" />
            <input
              type="date"
              value={fromDate ?? ""}
              onChange={(e) => setDateRange(e.target.value || null, toDate)}
              className="w-[120px] bg-transparent text-sm focus:outline-none dark:text-slate-200"
            />
            <span className="text-slate-700 dark:text-slate-300 dark:text-slate-400 dark:text-slate-600">
              —
            </span>
            <input
              type="date"
              value={toDate ?? ""}
              onChange={(e) => setDateRange(fromDate, e.target.value || null)}
              className="w-[120px] bg-transparent text-sm focus:outline-none dark:text-slate-200"
            />
          </div>

          {/* Language */}
          <div className="relative flex items-center">
            <Globe className="pointer-events-none absolute left-3 h-3.5 w-3.5 text-slate-400 dark:text-slate-500 dark:text-slate-400" />
            <select
              value={language ?? ""}
              onChange={(e) => setLanguage(e.target.value || null)}
              className="appearance-none rounded-xl border border-slate-200 bg-white py-2 pl-8 pr-7 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-slate-300 dark:border-slate-700 dark:bg-slate-50 dark:bg-slate-900 dark:text-slate-200"
            >
              <option value="">Всі мови</option>
              <option value="ro">🇷🇴 Română</option>
              <option value="sk">🇸🇰 Slovenčina</option>
              <option value="hu">🇭🇺 Magyar</option>
            </select>
            <ChevronDown className="pointer-events-none absolute right-2 h-3 w-3 text-slate-400 dark:text-slate-500 dark:text-slate-400" />
          </div>

          {/* Reset */}
          {hasFilters && (
            <button
              onClick={reset}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-400 dark:text-slate-500 shadow-sm hover:bg-slate-50 active:scale-95 dark:border-slate-300 dark:border-slate-700 dark:bg-slate-50 dark:bg-slate-900 dark:text-slate-400 dark:text-slate-500 dark:text-slate-400 dark:hover:bg-slate-100 dark:bg-slate-800"
            >
              <RefreshCw className="h-3 w-3" />
              Скинути
            </button>
          )}
        </div>
      </div>

      {/* Active filter pills */}
      {hasFilters && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-slate-400 dark:text-slate-500 dark:text-slate-400">
            Фільтри:
          </span>
          {fromDate && (
            <FilterPill
              label={`від ${fromDate}`}
              onRemove={() => setDateRange(null, toDate)}
            />
          )}
          {toDate && (
            <FilterPill
              label={`до ${toDate}`}
              onRemove={() => setDateRange(fromDate, null)}
            />
          )}
          {language && (
            <FilterPill
              label={
                { ro: "🇷🇴 Română", sk: "🇸🇰 Slovenčina", hu: "🇭🇺 Magyar" }[
                  language
                ] ?? language
              }
              onRemove={() => setLanguage(null)}
            />
          )}
        </div>
      )}

      {/* ── KPI sections ── */}
      {isLoading ? (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-[100px]" />
            ))}
          </div>
        </div>
      ) : overview ? (
        <>
          <div className="space-y-3">
            <SectionLabel>Статті</SectionLabel>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <KpiCard
                label="Всього"
                value={overview.total_articles}
                icon={<FileText />}
                accent="blue"
              />
              <KpiCard
                label="Прийнято"
                value={overview.accepted_articles}
                badge={{
                  text: fmtPct(overview.acceptance_rate),
                  color: "green",
                }}
                icon={<CircleCheck />}
                accent="green"
              />
              <KpiCard
                label="Відхилено"
                value={overview.rejected_articles}
                badge={{ text: fmtPct(overview.rejection_rate), color: "red" }}
                icon={<CircleX />}
                accent="red"
              />
              <KpiCard
                label="Джерела"
                value={`${overview.active_sources}/${overview.total_sources}`}
                sub="активних"
                icon={<Globe />}
                accent="purple"
              />
            </div>
          </div>

          <div className="space-y-3">
            <SectionLabel>Користувачі</SectionLabel>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <KpiCard
                label="Всього"
                value={overview.total_users}
                icon={<Users />}
                accent="blue"
              />
              <KpiCard
                label="Активних сьогодні"
                value={overview.active_users_today}
                sub="DAU"
                icon={<Activity />}
                accent="green"
              />
              <KpiCard
                label="Нових сьогодні"
                value={overview.new_users_today}
                icon={<Zap />}
                accent="amber"
              />
              <KpiCard
                label="Engagement"
                value={fmtPct(overview.engagement_rate)}
                icon={<Flame />}
                badge={{
                  text: overview.engagement_rate >= 50 ? "High" : "Low",
                  color: overview.engagement_rate >= 50 ? "green" : "amber",
                }}
                accent="amber"
              />
            </div>
          </div>

          <div className="space-y-3">
            <SectionLabel>Якість контенту</SectionLabel>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <KpiCard
                label="Avg score"
                value={(overview.avg_relevance_score ?? 0).toFixed(2)}
                sub="relevance"
                icon={<BarChart3 />}
                accent="blue"
              />
              <KpiCard
                label="Лайки / Дизлайки"
                value={`${fmt(overview.liked_feedback)} / ${fmt(overview.disliked_feedback)}`}
                badge={{ text: fmtPct(likedPct) + " +", color: "green" }}
                icon={<ThumbsUp />}
                accent="green"
              />
              <KpiCard
                label="Прочитань"
                value={overview.total_read_actions}
                icon={<Eye />}
                accent="blue"
              />
              <KpiCard
                label="Генерацій новин"
                value={overview.generated_news_count}
                icon={<Radio />}
                accent="purple"
              />
            </div>
          </div>
        </>
      ) : null}

      {/* ── Time series ── */}
      <Panel title="Динаміка за часом" icon={<TrendingUp />}>
        <TimeSeriesChart filters={filters} />
      </Panel>

      {/* ── Language & Status ── */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Розподіл за мовами" icon={<Globe />}>
          <LanguagePieChart filters={filters} />
        </Panel>
        <Panel title="Статус статей" icon={<PieChart />}>
          <ArticleStatusChart filters={filters} />
        </Panel>
      </div>

      {/* ── Tags & Score ── */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Топ тегів" icon={<Tag />}>
          <TopTagsChart filters={filters} />
        </Panel>
        <Panel title="Гістограма Relevance Score" icon={<BarChart3 />}>
          <ScoreHistogram filters={filters} />
        </Panel>
      </div>

      {/* ── Sources ── */}
      <Panel title="Продуктивність джерел" icon={<Radio />} noPadding>
        <SourcesTable filters={filters} />
      </Panel>

      {/* ── Popular articles ── */}
      <Panel title="Популярні статті" icon={<Flame />} noPadding>
        <PopularArticlesTable filters={filters} />
      </Panel>

      {/* ── User stats ── */}
      <Panel title="Детальна аналітика користувачів" icon={<Users />}>
        <UserStatsGrid filters={filters} />
      </Panel>
    </div>
  );
};
