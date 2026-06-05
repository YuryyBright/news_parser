// src/pages/HandbookPage.tsx
import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Globe2,
  Building2,
  Users,
  Search,
  Plus,
  ChevronRight,
  ChevronDown,
  Link2,
  Edit3,
  Trash2,
  ArrowRight,
  BookOpen,
  MapPin,
  ExternalLink,
  Clock,
  X,
  Table2,
  Network,
  Loader2,
} from "lucide-react";
import { cn, formatDate } from "../lib/utils";
import { handbookApi, buildTree, fullName } from "../api/handbook";
import type {
  OrgUnit,
  Person,
  NewsLink,
  ChangeLogEntry,
} from "../api/handbook";
import { useHandbookStore } from "../store/useHandbookStore";
import { HandbookFormModal } from "../components/handbook/HandbookFormModal";
import { PersonDrawer } from "../components/handbook/PersonDrawer";
import { EventFormModal } from "../components/handbook/EventFormModal";
import { OrgChart } from "../components/handbook/OrgChart";
import { useArticlesStore } from "../store/useArticlesStore";
import { ArticleDrawer } from "../components/articles/ArticleDrawer";

// ── Constants ────────────────────────────────────────────────────────────────

const UNIT_TYPE_LABELS: Record<string, string> = {
  ministry: "Міністерство",
  department: "Департамент",
  division: "Відділ",
  sector: "Сектор",
  post: "Посада",
  agency: "Агентство",
  service: "Служба",
  command: "Командування",
};

const UNIT_TYPE_COLORS: Record<string, string> = {
  ministry: "bg-accent-bg text-accent border-violet-500/25",
  department: "bg-blue-500/15 text-blue-400 border-blue-500/25",
  division: "bg-sky-500/15 text-sky-400 border-sky-500/25",
  sector: "bg-teal-500/15 text-teal-400 border-teal-500/25",
  agency: "bg-amber-500/15 text-amber-400 border-amber-500/25",
  service: "bg-orange-500/15 text-orange-400 border-orange-500/25",
  command: "bg-red-500/15 text-red-400 border-red-500/25",
  post: "bg-zinc-500/15 text-zinc-400 border-zinc-500/25",
};

// ── Sub-components ───────────────────────────────────────────────────────────

const UnitBadge = ({ type }: { type: string }) => (
  <span
    className={cn(
      "inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border",
      UNIT_TYPE_COLORS[type] ??
        "bg-zinc-500/15 text-zinc-400 border-zinc-500/25",
    )}
  >
    {UNIT_TYPE_LABELS[type] ?? type}
  </span>
);

const ChangeLogItem = ({ entry }: { entry: ChangeLogEntry }) => (
  <div className="flex items-start gap-2 py-2 border-b border-slate-200 dark:border-slate-200/60 dark:border-slate-800/60 last:border-0">
    <div
      className={cn(
        "mt-0.5 flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px]",
        entry.action === "created"
          ? "bg-emerald-500/20 text-emerald-400"
          : entry.action === "deleted"
            ? "bg-red-500/20 text-red-400"
            : "bg-blue-500/20 text-blue-400",
      )}
    >
      {entry.action === "created"
        ? "+"
        : entry.action === "deleted"
          ? "−"
          : "↻"}
    </div>
    <div className="flex-1 min-w-0">
      <p className="text-xs text-slate-700 dark:text-slate-300">
        <span className="font-medium text-slate-900 dark:text-white">
          {entry.changed_by}
        </span>
        {" · "}
        {entry.action === "created"
          ? "створив"
          : entry.action === "deleted"
            ? "видалив"
            : "змінив"}
        {entry.field_name && (
          <span className="text-slate-400 dark:text-slate-500 dark:text-slate-400">
            {" "}
            поле «{entry.field_name}»
          </span>
        )}
      </p>
      {entry.diff && Object.keys(entry.diff).length > 0 && (
        <div className="mt-0.5 space-y-0.5">
          {Object.entries(entry.diff)
            .slice(0, 3)
            .map(([key, val]) => (
              <p
                key={key}
                className="text-[11px] text-slate-400 dark:text-slate-500 font-mono truncate"
              >
                {key}:{" "}
                <span className="text-red-400 line-through">
                  {String((val as any)?.old ?? "—").slice(0, 40)}
                </span>
                {" → "}
                <span className="text-emerald-400">
                  {String((val as any)?.new ?? "—").slice(0, 40)}
                </span>
              </p>
            ))}
        </div>
      )}
      <p className="text-[10px] text-slate-400 dark:text-slate-600 mt-0.5">
        {formatDate(entry.created_at)}
      </p>
    </div>
  </div>
);

const PersonCard = ({
  person,
  compact = false,
  onClick,
}: {
  person: Person;
  compact?: boolean;
  onClick?: () => void;
}) => (
  <div
    onClick={onClick}
    className={cn(
      "flex items-center gap-3 p-3 rounded-lg border border-slate-200 dark:border-slate-200/60 dark:border-slate-800/60",
      "bg-slate-50 dark:bg-slate-900/40 hover:bg-white dark:bg-slate-100 dark:bg-slate-800/60 transition-colors",
      onClick && "cursor-pointer",
    )}
  >
    <div className="flex-shrink-0 w-9 h-9 rounded-full overflow-hidden bg-slate-700 flex items-center justify-center">
      {person.photo_url ? (
        <img
          src={person.photo_url}
          alt={fullName(person)}
          className="w-full h-full object-cover"
        />
      ) : (
        <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
          {person.first_name[0]}
          {person.last_name[0]}
        </span>
      )}
    </div>
    <div className="flex-1 min-w-0">
      <p className="text-sm font-medium text-slate-900 dark:text-white truncate">
        {fullName(person)}
      </p>
      {person.position_title && (
        <p className="text-xs text-slate-400 dark:text-slate-500 dark:text-slate-400 truncate">
          {person.position_title}
        </p>
      )}
      {!compact && person.rank && (
        <p className="text-[11px] text-amber-400 truncate">{person.rank}</p>
      )}
    </div>
    {!person.is_active && (
      <span className="flex-shrink-0 text-[10px] text-slate-400 dark:text-slate-500 italic">
        неактивний
      </span>
    )}
  </div>
);

// ── OrgTree node ──────────────────────────────────────────────────────────────

const OrgTreeNode = ({
  unit,
  depth = 0,
  activeId,
  onSelect,
}: {
  unit: OrgUnit;
  depth?: number;
  activeId: string | null;
  onSelect: (unit: OrgUnit) => void;
}) => {
  const { expandedNodes, toggleNode } = useHandbookStore();
  const isExpanded = expandedNodes.has(unit.id);
  const hasChildren = unit.children.length > 0;
  const isActive = activeId === unit.id;

  return (
    <div>
      <div
        className={cn(
          "group flex items-center gap-1.5 py-1.5 px-2 rounded-md cursor-pointer transition-all",
          "hover:bg-white dark:bg-slate-100 dark:bg-slate-800/60",
          isActive &&
            "bg-slate-100 dark:bg-slate-800 border-l-2 border-blue-500",
        )}
        style={{ paddingLeft: `${8 + depth * 20}px` }}
        onClick={() => onSelect(unit)}
      >
        <button
          onClick={(e) => {
            e.stopPropagation();
            toggleNode(unit.id);
          }}
          className={cn(
            "flex-shrink-0 w-4 h-4 rounded flex items-center justify-center",
            "text-slate-400 dark:text-slate-500 hover:text-slate-900 dark:text-white transition-colors",
            !hasChildren && "opacity-0 pointer-events-none",
          )}
        >
          {isExpanded ? (
            <ChevronDown className="w-3 h-3" />
          ) : (
            <ChevronRight className="w-3 h-3" />
          )}
        </button>
        <Building2
          className={cn(
            "w-3.5 h-3.5 flex-shrink-0",
            isActive ? "text-blue-400" : "text-slate-400 dark:text-slate-500",
          )}
        />
        <span
          className={cn(
            "flex-1 text-sm truncate",
            isActive
              ? "text-slate-900 dark:text-white font-medium"
              : "text-slate-700 dark:text-slate-300",
          )}
        >
          {unit.short_name || unit.name}
        </span>
        <div className="flex-shrink-0 flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
          <UnitBadge type={unit.unit_type} />
          {unit.persons.length > 0 && (
            <span className="text-[10px] text-slate-400 dark:text-slate-500">
              {unit.persons.length}👤
            </span>
          )}
        </div>
      </div>
      {isExpanded && hasChildren && (
        <div>
          {unit.children
            .sort(
              (a, b) =>
                a.sort_order - b.sort_order || a.name.localeCompare(b.name),
            )
            .map((child) => (
              <OrgTreeNode
                key={child.id}
                unit={child}
                depth={depth + 1}
                activeId={activeId}
                onSelect={onSelect}
              />
            ))}
        </div>
      )}
    </div>
  );
};

// ── OrgUnit detail panel ──────────────────────────────────────────────────────

const OrgUnitDetail = ({
  unit,
  onEdit,
  onDelete,
  onAddPerson,
  onSelectPerson,
}: {
  unit: OrgUnit;
  onEdit: () => void;
  onDelete: () => void;
  onAddPerson: () => void;
  onSelectPerson: (person: Person) => void;
}) => {
  const { activeCountryId } = useHandbookStore();
  const { data: countryDetail } = useQuery({
    queryKey: ["handbook-country", activeCountryId],
    queryFn: () => handbookApi.getCountry(activeCountryId!),
    enabled: !!activeCountryId,
  });
  const [tab, setTab] = useState<
    "info" | "persons" | "structure" | "news" | "log"
  >("info");
  const leader = unit.persons[0] ?? null;

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-200/60 dark:border-slate-800/60 flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <UnitBadge type={unit.unit_type} />
            {!unit.is_active && (
              <span className="text-[10px] text-slate-400 dark:text-slate-500 italic">
                неактивна
              </span>
            )}
          </div>
          <h2 className="text-base font-semibold text-slate-900 dark:text-white leading-snug">
            {unit.name}
          </h2>
          {unit.valid_from && (
            <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5 font-mono">
              {unit.valid_from ? `від ${formatDate(unit.valid_from)}` : ""}
              {unit.valid_to ? ` до ${formatDate(unit.valid_to)}` : ""}
            </p>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={onEdit}
            className="p-1.5 rounded-md text-slate-400 dark:text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:text-white hover:bg-slate-700 transition-colors"
          >
            <Edit3 className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={onDelete}
            className="p-1.5 rounded-md text-slate-400 dark:text-slate-500 dark:text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 dark:border-slate-200/60 dark:border-slate-800/60 px-2 overflow-x-auto">
        {(["info", "persons", "structure", "news", "log"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "px-3 py-2 text-xs font-medium transition-colors border-b-2 -mb-px whitespace-nowrap",
              tab === t
                ? "text-blue-400 border-blue-500"
                : "text-slate-400 dark:text-slate-500 border-transparent hover:text-slate-700 dark:text-slate-300",
            )}
          >
            {
              {
                info: "Інфо",
                persons: `Персони (${unit.persons.length})`,
                structure: "Структура",
                news: "Новини",
                log: "Зміни",
              }[t]
            }
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Info tab */}
        {tab === "info" && (
          <div className="p-3 space-y-3">
            {leader && (
              <div
                onClick={() => onSelectPerson(leader)}
                className="flex items-center gap-3 p-3 rounded-xl border border-slate-300 dark:border-slate-700/60 bg-slate-50/80 dark:bg-slate-50 dark:bg-slate-900/60 hover:bg-slate-100 dark:bg-slate-800/70 cursor-pointer transition-colors group"
              >
                <div className="flex-shrink-0 w-12 h-12 rounded-full overflow-hidden bg-slate-700 ring-2 ring-slate-600 group-hover:ring-blue-500/50 transition-all">
                  {leader.photo_url ? (
                    <img
                      src={leader.photo_url}
                      alt={fullName(leader)}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-base font-semibold text-slate-700 dark:text-slate-300 bg-gradient-to-br from-slate-700 to-slate-800">
                      {leader.first_name?.[0]}
                      {leader.last_name?.[0]}
                    </div>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-slate-900 dark:text-white truncate group-hover:text-blue-300 transition-colors">
                    {fullName(leader)}
                  </p>
                  {leader.position_title && (
                    <p className="text-xs text-slate-400 dark:text-slate-500 dark:text-slate-400 truncate mt-0.5">
                      {leader.position_title}
                    </p>
                  )}
                  {leader.rank && (
                    <p className="text-[11px] text-amber-400/90 truncate mt-0.5 font-mono">
                      {leader.rank}
                    </p>
                  )}
                </div>
                <ChevronRight className="w-3.5 h-3.5 text-slate-400 dark:text-slate-600 group-hover:text-blue-400 flex-shrink-0 transition-colors" />
              </div>
            )}
            {unit.description && (
              <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                {unit.description}
              </p>
            )}
            {unit.legal_basis && (
              <div className="rounded-lg border border-slate-200 dark:border-slate-200/60 dark:border-slate-800/60 p-3">
                <p className="text-[11px] text-slate-400 dark:text-slate-500 font-mono mb-1">
                  ПРАВОВА ОСНОВА
                </p>
                <p className="text-xs text-slate-700 dark:text-slate-300">
                  {unit.legal_basis}
                </p>
              </div>
            )}
            {unit.resources.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-[11px] text-slate-400 dark:text-slate-500 font-mono">
                  РЕСУРСИ
                </p>
                {unit.resources.map((r, i) => (
                  <a
                    key={i}
                    href={r.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-xs text-blue-400 hover:text-blue-300 transition-colors"
                  >
                    <ExternalLink className="w-3 h-3 flex-shrink-0" />
                    {r.title}
                  </a>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Persons tab */}
        {tab === "persons" && (
          <div className="p-3 space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-slate-200 dark:border-slate-800/40">
              <p className="text-[11px] font-mono text-slate-400 dark:text-slate-500 uppercase">
                Складові кадри
              </p>
              <button
                onClick={onAddPerson}
                className="flex items-center gap-1 px-2.5 py-1 bg-blue-600 hover:bg-blue-500 text-slate-900 dark:text-white text-xs font-medium rounded-md transition-colors"
              >
                <Plus className="w-3 h-3" />
                <span>Додати персону</span>
              </button>
            </div>
            <div className="space-y-2">
              {unit.persons.length === 0 ? (
                <p className="text-sm text-slate-400 dark:text-slate-500 text-center py-6">
                  Немає персон
                </p>
              ) : (
                unit.persons.map((p) => (
                  <PersonCard
                    key={p.id}
                    person={p}
                    compact
                    onClick={() => onSelectPerson(p)}
                  />
                ))
              )}
            </div>
          </div>
        )}

        {/* Structure tab — OrgChart з підтримкою кліку на персону */}
        {tab === "structure" && (
          <div className="h-full min-h-[480px] p-2">
            <OrgChart
              units={countryDetail?.org_units ?? []}
              selectedId={unit.id}
              onSelect={(u) =>
                useHandbookStore.getState().setActiveOrgUnit(u.id)
              }
              onPersonSelect={onSelectPerson}
              className="h-full min-h-[460px]"
            />
          </div>
        )}

        {/* News tab */}
        {tab === "news" && (
          <div className="p-3 space-y-2">
            {unit.news_links.length === 0 ? (
              <p className="text-sm text-slate-400 dark:text-slate-500 text-center py-6">
                Немає прив'язаних новин
              </p>
            ) : (
              unit.news_links.map((link) => (
                <NewsLinkCard key={link.id} link={link} />
              ))
            )}
          </div>
        )}

        {/* Log tab */}
        {tab === "log" && (
          <div className="p-3">
            {unit.changelog.length === 0 ? (
              <p className="text-sm text-slate-400 dark:text-slate-500 text-center py-6">
                Немає змін
              </p>
            ) : (
              unit.changelog.map((e) => <ChangeLogItem key={e.id} entry={e} />)
            )}
          </div>
        )}
      </div>
    </div>
  );
};

// ── NewsLink card ─────────────────────────────────────────────────────────────

const NewsLinkCard = ({ link }: { link: NewsLink }) => {
  const { setActiveArticle } = useArticlesStore();
  return (
    <article
      onClick={() => {
        if (link.article_id) setActiveArticle(link.article_id);
      }}
      className={cn(
        "flex items-start gap-3 px-3 sm:px-4 py-3 sm:py-4 rounded-xl border cursor-pointer transition-colors group",
        "bg-slate-50 dark:bg-slate-900/40 border-slate-200 dark:border-slate-200/60 dark:border-slate-800/60",
        link.article_id &&
          "hover:bg-white dark:bg-slate-100 dark:bg-slate-800/60 hover:border-blue-500/30 active:bg-slate-100 dark:bg-slate-800",
        !link.article_id && "cursor-default",
      )}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1.5">
          <Link2 className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500 group-hover:text-blue-400 transition-colors flex-shrink-0" />
          <span className="text-[11px] text-slate-400 dark:text-slate-500 dark:text-slate-400 font-mono truncate group-hover:text-slate-700 dark:text-slate-300 transition-colors">
            {link.article_id
              ? `Стаття: ${link.article_id.slice(0, 8)}…`
              : `Новина: ${link.generated_news_id?.slice(0, 8)}…`}
          </span>
          <span className="ml-auto flex items-center gap-1 text-[10px] text-slate-400 dark:text-slate-500 flex-shrink-0">
            <Clock className="w-3 h-3" />
            {formatDate(link.created_at)}
          </span>
        </div>
        {link.excerpt && (
          <blockquote className="text-sm text-slate-700 dark:text-slate-300 leading-snug line-clamp-3 italic border-l-2 border-slate-300 dark:border-slate-700 pl-2.5 mt-2 group-hover:border-blue-500/50 transition-colors">
            «{link.excerpt}»
          </blockquote>
        )}
        {link.note && (
          <div className="mt-2.5 flex items-center gap-1.5">
            <span className="px-2 py-1 rounded-md text-[10px] font-medium bg-white dark:bg-slate-100 dark:bg-slate-800/60 text-slate-400 dark:text-slate-500 dark:text-slate-400 border border-slate-300 dark:border-slate-700/50">
              <span className="text-slate-400 dark:text-slate-500 mr-1">
                Примітка:
              </span>
              {link.note}
            </span>
          </div>
        )}
      </div>
      <div
        className="flex-shrink-0 flex items-center gap-0.5 mt-0.5"
        onClick={(e) => e.stopPropagation()}
      >
        {link.article_id && (
          <button
            title="Відкрити статтю"
            onClick={() => setActiveArticle(link.article_id!)}
            className={cn(
              "p-1.5 rounded-md transition-all",
              "sm:opacity-0 sm:group-hover:opacity-100",
              "text-slate-400 dark:text-slate-500 dark:text-slate-400 hover:text-blue-400 hover:bg-slate-100 dark:bg-slate-800",
            )}
          >
            <ExternalLink className="w-4 h-4" />
          </button>
        )}
      </div>
    </article>
  );
};

// ── Search overlay ────────────────────────────────────────────────────────────

const SearchOverlay = ({ onClose }: { onClose: () => void }) => {
  const [q, setQ] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const { setActiveCountry, setActiveOrgUnit } = useHandbookStore();

  const { data, isLoading } = useQuery({
    queryKey: ["handbook-search", q],
    queryFn: () => handbookApi.search(q),
    enabled: q.trim().length >= 2,
  });

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const ICONS: Record<string, typeof Globe2> = {
    country: Globe2,
    org_unit: Building2,
    person: Users,
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/20 dark:bg-black/60 backdrop-blur-sm flex items-start justify-center pt-24 px-4">
      <div className="w-full max-w-lg bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-xl shadow-2xl overflow-hidden">
        <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-200 dark:border-slate-800">
          <Search className="w-4 h-4 text-slate-400 dark:text-slate-500 dark:text-slate-400 flex-shrink-0" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Пошук країн, структур, персон…"
            className="flex-1 bg-transparent text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 text-sm outline-none"
          />
          {isLoading && (
            <Loader2 className="w-4 h-4 text-slate-400 dark:text-slate-500 animate-spin flex-shrink-0" />
          )}
          <button
            onClick={onClose}
            className="p-1 text-slate-400 dark:text-slate-500 hover:text-slate-900 dark:text-white"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="max-h-80 overflow-y-auto">
          {data?.items.length === 0 && q.length >= 2 && (
            <p className="text-sm text-slate-400 dark:text-slate-500 text-center py-8">
              Нічого не знайдено
            </p>
          )}
          {data?.items.map((item) => {
            const Icon = ICONS[item.entity_type] ?? BookOpen;
            return (
              <button
                key={item.id}
                onClick={() => {
                  if (item.entity_type === "country") setActiveCountry(item.id);
                  else if (item.entity_type === "org_unit")
                    setActiveOrgUnit(item.id);
                  onClose();
                }}
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white dark:bg-slate-100 dark:bg-slate-800/60 transition-colors text-left"
              >
                <div className="w-7 h-7 rounded-lg bg-slate-100 dark:bg-slate-800 flex items-center justify-center flex-shrink-0">
                  <Icon className="w-4 h-4 text-slate-400 dark:text-slate-500 dark:text-slate-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-slate-900 dark:text-white truncate">
                    {item.title}
                  </p>
                  {item.subtitle && (
                    <p className="text-xs text-slate-400 dark:text-slate-500 truncate">
                      {item.subtitle}
                    </p>
                  )}
                </div>
                {item.country_code && (
                  <span className="flex-shrink-0 text-[10px] font-mono text-slate-400 dark:text-slate-500">
                    {item.country_code}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};

// ── Main Page ─────────────────────────────────────────────────────────────────

export const HandbookPage = () => {
  const qc = useQueryClient();
  const {
    activeCountryId,
    activeOrgUnitId,
    setActiveCountry,
    setActiveCountryDetail,
    setActiveOrgUnit,
    view,
    setView,
    expandedNodes,
    expandAll,
    collapseAll,
    isSearchOpen,
    openSearch,
    closeSearch,
    openForm,
    closeForm,
    isFormOpen,
    formEntity,
    formData,
  } = useHandbookStore();

  // ── Local state ──────────────────────────────────────────────────────────────
  const [activePerson, setActivePerson] = useState<Person | null>(null);
  const [eventModalConfig, setEventModalConfig] = useState<{
    personId?: string;
    orgUnitId?: string;
    countryId?: string;
  } | null>(null);

  // ⌘K shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        openSearch();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [openSearch]);

  const { data: countriesData, isLoading: loadingCountries } = useQuery({
    queryKey: ["handbook-countries"],
    queryFn: () => handbookApi.listCountries({ page_size: 100 }),
  });

  const { mutate: deleteUnit } = useMutation({
    mutationFn: (id: string) => handbookApi.deleteOrgUnit(id),
    onSuccess: () => {
      setActiveOrgUnit(null);
      qc.invalidateQueries({ queryKey: ["handbook-country", activeCountryId] });
    },
  });

  const { mutate: deletePerson } = useMutation({
    mutationFn: (id: string) => handbookApi.deletePerson(id),
    onSuccess: () => {
      setActivePerson(null);
      qc.invalidateQueries({ queryKey: ["handbook-country", activeCountryId] });
    },
  });

  const { data: countryDetail, isLoading: loadingDetail } = useQuery({
    queryKey: ["handbook-country", activeCountryId],
    queryFn: () => handbookApi.getCountry(activeCountryId!),
    enabled: !!activeCountryId,
  });

  const { activeArticleId, setActiveArticle } = useArticlesStore();

  useEffect(() => {
    if (countryDetail) setActiveCountryDetail(countryDetail);
  }, [countryDetail]);

  const orgTree = countryDetail ? buildTree(countryDetail.org_units) : [];
  const allIds = countryDetail?.org_units.map((u) => u.id) ?? [];
  const activeUnit = countryDetail?.org_units.find(
    (u) => u.id === activeOrgUnitId,
  );

  const handleAdd = () => {
    if (!activeCountryId) openForm("country");
    else if (activeOrgUnitId)
      openForm("org_unit", {
        country_id: activeCountryId,
        parent_id: activeOrgUnitId,
      });
    else openForm("org_unit", { country_id: activeCountryId });
  };

  return (
    <div className="h-full flex flex-col bg-white dark:bg-slate-950 text-slate-900 dark:text-white">
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-200/60 dark:border-slate-800/60 bg-slate-50 dark:bg-slate-900/80 backdrop-blur-sm flex-shrink-0">
        <div className="flex items-center gap-3">
          <BookOpen className="w-5 h-5 text-blue-400" />
          <h1 className="text-base font-semibold text-slate-900 dark:text-white">
            Довідник
          </h1>
        </div>
        <div className="flex items-center gap-2">
          {activeCountryId && (
            <div className="flex items-center bg-slate-100 dark:bg-slate-800 rounded-lg p-0.5 gap-0.5">
              {(
                [
                  ["tree", Network],
                  ["table", Table2],
                ] as const
              ).map(([v, Icon]) => (
                <button
                  key={v}
                  onClick={() => setView(v)}
                  className={cn(
                    "p-1.5 rounded-md transition-colors",
                    view === v
                      ? "bg-slate-600 text-slate-900 dark:text-white"
                      : "text-slate-400 dark:text-slate-500 hover:text-slate-700 dark:text-slate-300",
                  )}
                >
                  <Icon className="w-3.5 h-3.5" />
                </button>
              ))}
            </div>
          )}
          <button
            onClick={openSearch}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-700 text-slate-400 dark:text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:text-white text-xs transition-colors"
          >
            <Search className="w-3.5 h-3.5" />
            <span>Пошук</span>
            <kbd className="text-[10px] bg-slate-700 px-1.5 py-0.5 rounded font-mono">
              ⌘K
            </kbd>
          </button>
          <button
            onClick={handleAdd}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-slate-900 dark:text-white text-xs font-medium transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Додати
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar: country list */}
        <div className="w-56 border-r border-slate-200 dark:border-slate-200/60 dark:border-slate-800/60 flex flex-col flex-shrink-0 bg-slate-50 dark:bg-slate-900/40">
          <div className="px-3 py-2.5 border-b border-slate-200 dark:border-slate-200/60 dark:border-slate-800/60">
            <p className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-widest">
              Країни
            </p>
          </div>
          <div className="flex-1 overflow-y-auto py-1">
            {loadingCountries ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-4 h-4 animate-spin text-slate-400 dark:text-slate-500" />
              </div>
            ) : (
              countriesData?.items.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setActiveCountry(c.id)}
                  className={cn(
                    "w-full flex items-center gap-2.5 px-3 py-2 transition-colors text-left group",
                    activeCountryId === c.id
                      ? "bg-blue-500/10 text-slate-900 dark:text-white border-l-2 border-blue-500"
                      : "text-slate-400 dark:text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:bg-slate-800/50 hover:text-slate-900 dark:text-white",
                  )}
                >
                  <span className="text-base leading-none">
                    {c.flag_emoji ?? "🏳"}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium truncate">{c.name_uk}</p>
                    <p className="text-[10px] text-slate-400 dark:text-slate-600 font-mono">
                      {c.code}
                    </p>
                  </div>
                  <ArrowRight className="w-3 h-3 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                </button>
              ))
            )}
          </div>
          <div className="px-3 py-2 border-t border-slate-200 dark:border-slate-200/60 dark:border-slate-800/60">
            <button
              onClick={() => openForm("country")}
              className="w-full flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500 hover:text-slate-700 dark:text-slate-300 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              Нова країна
            </button>
          </div>
        </div>

        {/* Main section */}
        {activeCountryId ? (
          <div className="flex-1 flex overflow-hidden">
            {/* Org panel */}
            <div className="w-72 border-r border-slate-200 dark:border-slate-200/60 dark:border-slate-800/60 flex flex-col flex-shrink-0">
              <div className="flex items-center justify-between px-3 py-2.5 border-b border-slate-200 dark:border-slate-200/60 dark:border-slate-800/60">
                <p className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-widest">
                  Структура
                </p>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => expandAll(allIds)}
                    className="text-[10px] text-slate-400 dark:text-slate-500 hover:text-slate-700 dark:text-slate-300 px-1.5 py-0.5 rounded transition-colors"
                  >
                    розкрити всі
                  </button>
                  <span className="text-slate-700">·</span>
                  <button
                    onClick={collapseAll}
                    className="text-[10px] text-slate-400 dark:text-slate-500 hover:text-slate-700 dark:text-slate-300 px-1.5 py-0.5 rounded transition-colors"
                  >
                    згорнути
                  </button>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto py-1">
                {loadingDetail ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-4 h-4 animate-spin text-slate-400 dark:text-slate-500" />
                  </div>
                ) : view === "tree" ? (
                  orgTree.map((unit) => (
                    <OrgTreeNode
                      key={unit.id}
                      unit={unit}
                      activeId={activeOrgUnitId}
                      onSelect={(u) => setActiveOrgUnit(u.id)}
                    />
                  ))
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead className="sticky top-0 bg-slate-50 dark:bg-slate-900">
                        <tr className="text-slate-400 dark:text-slate-500 text-[10px] font-mono uppercase">
                          <th className="px-3 py-2 text-left">Назва</th>
                          <th className="px-3 py-2 text-left">Тип</th>
                        </tr>
                      </thead>
                      <tbody>
                        {countryDetail?.org_units.map((u) => (
                          <tr
                            key={u.id}
                            onClick={() => setActiveOrgUnit(u.id)}
                            className={cn(
                              "border-t border-slate-200 dark:border-slate-800/40 cursor-pointer transition-colors",
                              activeOrgUnitId === u.id
                                ? "bg-blue-50/10"
                                : "hover:bg-slate-100/60 dark:bg-slate-100 dark:bg-slate-800/40",
                            )}
                          >
                            <td
                              className="px-3 py-2 text-slate-700 dark:text-slate-300"
                              style={{ paddingLeft: `${12 + u.level * 16}px` }}
                            >
                              {u.short_name || u.name}
                            </td>
                            <td className="px-3 py-2">
                              <UnitBadge type={u.unit_type} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
              <div className="px-3 py-2 border-t border-slate-200 dark:border-slate-200/60 dark:border-slate-800/60">
                <button
                  onClick={() =>
                    openForm("org_unit", { country_id: activeCountryId })
                  }
                  className="w-full flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500 hover:text-slate-700 dark:text-slate-300 transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Додати структуру
                </button>
              </div>
            </div>

            {/* Detail panel */}
            <div className="flex-1 overflow-hidden">
              {activeUnit ? (
                <OrgUnitDetail
                  unit={activeUnit}
                  onEdit={() => openForm("org_unit", { ...activeUnit })}
                  onDelete={() => {
                    if (confirm(`Видалити «${activeUnit.name}»?`))
                      deleteUnit(activeUnit.id);
                  }}
                  onAddPerson={() =>
                    openForm("person", {
                      org_unit_id: activeUnit.id,
                      country_id: activeCountryId,
                    })
                  }
                  onSelectPerson={setActivePerson}
                />
              ) : countryDetail ? (
                <div className="h-full overflow-y-auto p-4 space-y-4">
                  <div className="flex items-start gap-4">
                    <span className="text-5xl">
                      {countryDetail.flag_emoji ?? "🏳"}
                    </span>
                    <div>
                      <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                        {countryDetail.name_uk}
                      </h2>
                      <p className="text-slate-400 dark:text-slate-500 dark:text-slate-400 text-sm">
                        {countryDetail.name_en}
                      </p>
                      {countryDetail.capital && (
                        <p className="flex items-center gap-1 text-xs text-slate-400 dark:text-slate-500 mt-1">
                          <MapPin className="w-3 h-3" />
                          {countryDetail.capital}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    {[
                      {
                        label: "Структури",
                        value: countryDetail.org_units.length,
                        icon: Building2,
                      },
                      {
                        label: "Персони",
                        value: countryDetail.persons_count,
                        icon: Users,
                      },
                      {
                        label: "Новини",
                        value: countryDetail.news_links.length,
                        icon: Link2,
                      },
                    ].map(({ label, value, icon: Icon }) => (
                      <div
                        key={label}
                        className="rounded-lg border border-slate-200 dark:border-slate-200/60 dark:border-slate-800/60 bg-slate-50 dark:bg-slate-900/40 p-3"
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <Icon className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500" />
                          <p className="text-[10px] text-slate-400 dark:text-slate-500 font-mono uppercase">
                            {label}
                          </p>
                        </div>
                        <p className="text-xl font-bold text-slate-900 dark:text-white">
                          {value}
                        </p>
                      </div>
                    ))}
                  </div>
                  {countryDetail.description && (
                    <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                      {countryDetail.description}
                    </p>
                  )}
                  {countryDetail.resources.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-widest">
                        Ресурси
                      </p>
                      {countryDetail.resources.map((r, i) => (
                        <a
                          key={i}
                          href={r.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-2 text-sm text-blue-400 hover:text-blue-300 transition-colors"
                        >
                          <ExternalLink className="w-3.5 h-3.5 flex-shrink-0" />
                          {r.title}
                        </a>
                      ))}
                    </div>
                  )}
                  {countryDetail.changelog.length > 0 && (
                    <div className="space-y-1">
                      <p className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-widest">
                        Останні зміни
                      </p>
                      {countryDetail.changelog.slice(0, 5).map((e) => (
                        <ChangeLogItem key={e.id} entry={e} />
                      ))}
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center gap-4 text-center px-8">
            <div className="w-16 h-16 rounded-2xl bg-white dark:bg-slate-100 dark:bg-slate-800/60 flex items-center justify-center">
              <Globe2 className="w-8 h-8 text-slate-400 dark:text-slate-500" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-1">
                Оберіть країну
              </h2>
              <p className="text-sm text-slate-400 dark:text-slate-500">
                Виберіть країну зі списку або скористайтесь пошуком,
                <br />
                щоб переглянути організаційну структуру.
              </p>
            </div>
            <button
              onClick={openSearch}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-sm transition-colors"
            >
              <Search className="w-4 h-4" />
              Пошук по довіднику
            </button>
          </div>
        )}
      </div>

      {/* Overlays */}
      {isSearchOpen && <SearchOverlay onClose={closeSearch} />}

      {isFormOpen && (
        <HandbookFormModal
          entity={formEntity}
          data={formData}
          onClose={closeForm}
        />
      )}

      {/* PersonDrawer — відкривається при кліку на персону (з картки або з OrgChart) */}
      <PersonDrawer
        person={activePerson}
        onClose={() => setActivePerson(null)}
        onEdit={(p) => {
          setActivePerson(null);
          openForm("person", { ...p, country_id: activeCountryId });
        }}
        onDelete={(p) => {
          if (confirm(`Видалити «${fullName(p)}»?`)) deletePerson(p.id);
        }}
        onAddEvent={(personId) =>
          setEventModalConfig({
            personId,
            countryId: activeCountryId ?? undefined,
          })
        }
      />

      {eventModalConfig && (
        <EventFormModal
          personId={eventModalConfig.personId}
          orgUnitId={eventModalConfig.orgUnitId}
          countryId={eventModalConfig.countryId}
          onClose={() => setEventModalConfig(null)}
        />
      )}

      <ArticleDrawer
        articleId={activeArticleId}
        onClose={() => setActiveArticle(null)}
      />
    </div>
  );
};

export default HandbookPage;
