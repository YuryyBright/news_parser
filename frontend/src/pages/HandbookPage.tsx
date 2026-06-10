// src/pages/HandbookPage.tsx
import { useState, useEffect, useRef, useCallback, useMemo } from "react";
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
  Country,
  NewsLink,
  ChangeLogEntry,
  SearchResult,
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
          <span className="text-slate-400 dark:text-slate-500">
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
      "bg-slate-50 dark:bg-slate-900/40 hover:bg-white dark:hover:bg-slate-800/60 transition-colors",
      onClick && "cursor-pointer",
    )}
  >
    <div className="flex-shrink-0 w-9 h-9 rounded-full overflow-hidden bg-slate-200 dark:bg-slate-700 flex items-center justify-center">
      {person.photo_url ? (
        <img
          src={person.photo_url}
          alt={fullName(person)}
          className="w-full h-full object-cover"
        />
      ) : (
        <span className="text-sm font-medium text-slate-500 dark:text-slate-300">
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
        <p className="text-xs text-slate-400 dark:text-slate-500 truncate">
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

// ── Utilities ────────────────────────────────────────────────────────────────

/** All ancestor ids from root to direct parent */
function getAncestorIds(units: OrgUnit[], targetId: string): string[] {
  const byId = new Map(units.map((u) => [u.id, u]));
  const ancestors: string[] = [];
  let current = byId.get(targetId);
  while (current?.parent_id) {
    ancestors.unshift(current.parent_id);
    current = byId.get(current.parent_id);
  }
  return ancestors;
}

/** Full ancestor path as names: ["Міністерство оборони", "Генеральний штаб"] */
function getAncestorPath(units: OrgUnit[], targetId: string): OrgUnit[] {
  const byId = new Map(units.map((u) => [u.id, u]));
  const path: OrgUnit[] = [];
  let current = byId.get(targetId);
  while (current?.parent_id) {
    const parent = byId.get(current.parent_id);
    if (parent) path.unshift(parent);
    current = parent;
  }
  return path;
}

/** Highlight matched substrings in text, returns JSX spans */
function HighlightMatch({
  text,
  query,
  className,
}: {
  text: string;
  query: string;
  className?: string;
}) {
  if (!query.trim()) return <span className={className}>{text}</span>;

  // Build regex from query tokens for partial/fuzzy highlighting
  const tokens = query.trim().split(/\s+/).filter(Boolean);

  // FIXED: Closed the character class properly and fixed the replacement string
  const pattern = tokens
    .map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("|");

  const regex = new RegExp(`(${pattern})`, "gi");
  const parts = text.split(regex);

  return (
    <span className={className}>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <mark
            key={i}
            className="bg-blue-500/40 text-white rounded-sm px-0.5 not-italic font-semibold"
          >
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </span>
  );
}

/** Score how well a string matches the query (0–1) */
function matchScore(text: string, query: string): number {
  if (!text || !query) return 0;
  const t = text.toLowerCase();
  const q = query.toLowerCase().trim();
  if (t.includes(q)) return 1;
  const tokens = q.split(/\s+/);
  const matched = tokens.filter((tok) => t.includes(tok)).length;
  return matched / tokens.length;
}

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
  const nodeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isActive && nodeRef.current) {
      nodeRef.current.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [isActive]);

  return (
    <div>
      <div
        ref={nodeRef}
        className={cn(
          "group flex items-center gap-1.5 py-1.5 px-2 rounded-md cursor-pointer transition-all",
          "hover:bg-white dark:hover:bg-slate-800/60",
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
            className="p-1.5 rounded-md text-slate-400 dark:text-slate-500 hover:text-slate-900 dark:text-white hover:bg-slate-700 transition-colors"
          >
            <Edit3 className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={onDelete}
            className="p-1.5 rounded-md text-slate-400 dark:text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
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
                    <div className="w-full h-full flex items-center justify-center text-base font-semibold text-slate-500 dark:text-slate-300 bg-gradient-to-br from-slate-200 to-slate-300 dark:from-slate-700 dark:to-slate-800">
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
                    <p className="text-xs text-slate-400 dark:text-slate-500 truncate mt-0.5">
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
              units={buildTree(countryDetail?.org_units ?? [])}
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
          "hover:bg-white dark:hover:bg-slate-800/60 hover:border-blue-500/30 active:bg-slate-100 dark:active:bg-slate-800",
        !link.article_id && "cursor-default",
      )}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1.5">
          <Link2 className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500 group-hover:text-blue-400 transition-colors flex-shrink-0" />
          <span className="text-[11px] text-slate-400 dark:text-slate-500 font-mono truncate group-hover:text-slate-700 dark:text-slate-300 transition-colors">
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
            <span className="px-2 py-1 rounded-md text-[10px] font-medium bg-white dark:bg-slate-800/60 text-slate-400 dark:text-slate-500 border border-slate-300 dark:border-slate-700/50">
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
              "text-slate-400 dark:text-slate-500 hover:text-blue-400 hover:bg-slate-100 dark:bg-slate-800",
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

const SearchOverlay = ({
  onClose,
  countries,
}: {
  onClose: () => void;
  countries: Country[];
}) => {
  const [q, setQ] = useState("");
  const [focusedIdx, setFocusedIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const { setActiveCountry, setActiveOrgUnit, expandNode } = useHandbookStore();

  const { data, isLoading } = useQuery({
    queryKey: ["handbook-search", q],
    queryFn: () => handbookApi.search(q),
    enabled: q.trim().length >= 2,
  });

  // Client-side score & sort — keeps only items with score > 0.4
  const items = useMemo<SearchResult[]>(() => {
    const raw = data?.items ?? [];
    if (!q.trim()) return raw;
    return raw
      .map((item) => ({
        item,
        score: Math.max(
          matchScore(item.title, q),
          matchScore(item.subtitle ?? "", q),
          matchScore(item.country_name ?? "", q),
        ),
      }))
      .filter(({ score }) => score > 0)
      .sort((a, b) => b.score - a.score)
      .map(({ item }) => item);
  }, [data, q]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);
  useEffect(() => {
    setFocusedIdx(0);
  }, [items.length]);

  // Map country code → Country object
  const countriesByCode = useMemo(
    () => new Map(countries.map((c) => [c.code, c])),
    [countries],
  );

  const findCountryId = useCallback(
    (code: string | undefined) =>
      code ? (countriesByCode.get(code)?.id ?? null) : null,
    [countriesByCode],
  );

  // Build full hierarchy breadcrumb for an org_unit using already-loaded tree
  const buildHierarchy = useCallback(
    (item: SearchResult): string[] => {
      const country = item.country_code
        ? countriesByCode.get(item.country_code)
        : null;
      const crumbs: string[] = [];
      if (country) {
        crumbs.push(
          country.flag_emoji
            ? `${country.flag_emoji} ${country.name_uk}`
            : country.name_uk,
        );
      }
      if (item.entity_type === "org_unit") {
        // Try to resolve ancestor names from the loaded country tree
        const allUnits =
          useHandbookStore.getState().activeCountry?.org_units ?? [];
        const byId = new Map(allUnits.map((u) => [u.id, u]));
        const target = byId.get(item.id);
        if (target) {
          // Walk ancestors
          const ancestors = getAncestorPath(allUnits, item.id);
          ancestors.forEach((a) => crumbs.push(a.short_name || a.name));
        } else if (item.subtitle) {
          // Fallback: subtitle from API (unit_type)
          crumbs.push(item.subtitle);
        }
      } else if (item.entity_type === "person" && item.subtitle) {
        crumbs.push(item.subtitle);
      }
      return crumbs;
    },
    [countriesByCode],
  );

  const handleSelect = useCallback(
    async (item: SearchResult) => {
      const countryId = findCountryId(item.country_code);

      if (item.entity_type === "country") {
        setActiveCountry(item.id);
      } else if (item.entity_type === "org_unit") {
        if (
          countryId &&
          countryId !== useHandbookStore.getState().activeCountryId
        ) {
          setActiveCountry(countryId);
          await new Promise((r) => setTimeout(r, 450));
        }
        const allUnits =
          useHandbookStore.getState().activeCountry?.org_units ?? [];
        const ancestors = getAncestorIds(allUnits, item.id);
        ancestors.forEach(expandNode);
        setActiveOrgUnit(item.id);
      } else if (item.entity_type === "person") {
        if (countryId) setActiveCountry(countryId);
        useHandbookStore.getState().setActivePerson(item.id);
      }
      onClose();
    },
    [findCountryId, setActiveCountry, setActiveOrgUnit, expandNode, onClose],
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setFocusedIdx((i) => Math.min(i + 1, items.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setFocusedIdx((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && items[focusedIdx]) {
      handleSelect(items[focusedIdx]);
    } else if (e.key === "Escape") {
      onClose();
    }
  };

  useEffect(() => {
    const el = listRef.current?.children[focusedIdx] as HTMLElement | undefined;
    el?.scrollIntoView({ block: "nearest" });
  }, [focusedIdx]);

  const ICONS: Record<string, typeof Globe2> = {
    country: Globe2,
    org_unit: Building2,
    person: Users,
  };

  const ENTITY_COLORS: Record<string, string> = {
    country: "text-emerald-400",
    org_unit: "text-blue-400",
    person: "text-violet-400",
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/30 dark:bg-black/60 backdrop-blur-sm flex items-start justify-center pt-20 px-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="w-full max-w-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl shadow-2xl overflow-hidden">
        {/* Input */}
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-slate-200 dark:border-slate-800">
          <Search className="w-4 h-4 text-slate-400 dark:text-slate-500 flex-shrink-0" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
            }}
            onKeyDown={handleKeyDown}
            placeholder="Пошук країн, структур, персон…"
            className="flex-1 bg-transparent text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 text-sm outline-none"
          />
          {isLoading && (
            <Loader2 className="w-4 h-4 text-slate-400 dark:text-slate-500 animate-spin flex-shrink-0" />
          )}
          {q && !isLoading && (
            <button
              onClick={() => setQ("")}
              className="p-0.5 rounded text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
          <button
            onClick={onClose}
            className="p-1 rounded text-slate-400 dark:text-slate-500 hover:text-slate-900 dark:hover:text-white border border-slate-200 dark:border-slate-700 text-[10px] font-mono px-1.5"
          >
            Esc
          </button>
        </div>

        {/* Results */}
        <div
          ref={listRef}
          className="max-h-[420px] overflow-y-auto divide-y divide-slate-100 dark:divide-slate-800/60"
        >
          {items.length === 0 && q.length >= 2 && !isLoading && (
            <div className="flex flex-col items-center gap-2 py-10 text-slate-400 dark:text-slate-500">
              <Search className="w-6 h-6 opacity-40" />
              <p className="text-sm">Нічого не знайдено для «{q}»</p>
            </div>
          )}
          {q.length < 2 && (
            <div className="px-4 py-6 text-center text-slate-400 dark:text-slate-600 text-xs">
              Введіть мінімум 2 символи для пошуку
            </div>
          )}
          {items.map((item, idx) => {
            const Icon = ICONS[item.entity_type] ?? BookOpen;
            const isFocused = idx === focusedIdx;
            const hierarchy = buildHierarchy(item);
            return (
              <button
                key={item.id}
                onMouseEnter={() => setFocusedIdx(idx)}
                onClick={() => handleSelect(item)}
                className={cn(
                  "w-full flex items-start gap-3 px-4 py-3 transition-colors text-left group",
                  isFocused
                    ? "bg-blue-50 dark:bg-slate-800/70"
                    : "hover:bg-slate-50 dark:hover:bg-slate-800/40",
                )}
              >
                {/* Icon */}
                <div
                  className={cn(
                    "mt-0.5 w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 transition-colors",
                    isFocused
                      ? "bg-blue-500/20"
                      : "bg-slate-100 dark:bg-slate-800",
                  )}
                >
                  <Icon
                    className={cn(
                      "w-3.5 h-3.5",
                      ENTITY_COLORS[item.entity_type] ?? "text-slate-400",
                    )}
                  />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  {/* Title with match highlight */}
                  <HighlightMatch
                    text={item.title}
                    query={q}
                    className="block text-sm font-medium text-slate-900 dark:text-white truncate"
                  />

                  {/* Full hierarchy breadcrumb */}
                  {hierarchy.length > 0 && (
                    <div className="flex items-center flex-wrap gap-0.5 mt-1">
                      {hierarchy.map((crumb, ci) => (
                        <span key={ci} className="flex items-center gap-0.5">
                          {ci > 0 && (
                            <ChevronRight className="w-3 h-3 text-slate-300 dark:text-slate-600 flex-shrink-0" />
                          )}
                          <HighlightMatch
                            text={crumb}
                            query={q}
                            className="text-[11px] text-slate-400 dark:text-slate-500 font-mono whitespace-nowrap"
                          />
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Match score indicator — subtle bar */}
                  {q.trim() &&
                    (() => {
                      const score = Math.max(
                        matchScore(item.title, q),
                        matchScore(item.subtitle ?? "", q),
                      );
                      return score < 1 && score > 0.3 ? (
                        <div className="mt-1.5 flex items-center gap-1.5">
                          <div className="h-0.5 w-12 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-blue-400 rounded-full"
                              style={{ width: `${Math.round(score * 100)}%` }}
                            />
                          </div>
                          <span className="text-[10px] text-slate-400 dark:text-slate-600 font-mono">
                            {Math.round(score * 100)}%
                          </span>
                        </div>
                      ) : null;
                    })()}
                </div>

                {/* Enter hint */}
                {isFocused && (
                  <kbd className="flex-shrink-0 self-center text-[10px] bg-slate-200 dark:bg-slate-700 text-slate-500 dark:text-slate-400 px-1.5 py-0.5 rounded font-mono">
                    ↵
                  </kbd>
                )}
              </button>
            );
          })}
        </div>

        {/* Footer */}
        {items.length > 0 && (
          <div className="px-4 py-2 border-t border-slate-100 dark:border-slate-800 flex items-center gap-4 text-[10px] text-slate-400 dark:text-slate-600 font-mono">
            <span className="flex items-center gap-1">
              ↑↓ <span>навігація</span>
            </span>
            <span className="flex items-center gap-1">
              ↵ <span>вибрати</span>
            </span>
            <span className="flex items-center gap-1">
              Esc <span>закрити</span>
            </span>
            <span className="ml-auto">
              {items.length} результат
              {items.length === 1 ? "" : items.length < 5 ? "и" : "ів"}
            </span>
          </div>
        )}
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
    activePersonId,
    setActiveCountry,
    setActiveCountryDetail,
    setActiveOrgUnit,
    setActivePerson: setActivePersonId,
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

  // When search sets activePersonId in store → resolve the Person object from tree
  useEffect(() => {
    if (!activePersonId) return;
    handbookApi
      .getPerson(activePersonId)
      .then((person) => {
        setActivePerson(person);
        setActivePersonId(null);
      })
      .catch(() => setActivePersonId(null));
  }, [activePersonId]);
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
    <div className="flex h-full flex-col bg-white text-slate-900 dark:bg-slate-950 dark:text-white">
      {/* Top bar */}
      <div className="flex flex-shrink-0 items-center justify-between border-b border-slate-200 bg-slate-50 px-4 py-3 backdrop-blur-sm dark:border-slate-800/60 dark:bg-slate-900/80">
        <div className="flex items-center gap-3">
          <BookOpen className="h-5 w-5 text-blue-400" />
          <h1 className="text-base font-semibold text-slate-900 dark:text-white">
            Довідник
          </h1>
        </div>

        <div className="flex items-center gap-2">
          {activeCountryId && (
            <div className="flex items-center gap-0.5 rounded-lg bg-slate-100 p-0.5 dark:bg-slate-800">
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
                    "rounded-md p-1.5 transition-colors",
                    view === v
                      ? "bg-white text-slate-900 shadow-sm dark:bg-slate-600 dark:text-white"
                      : "text-slate-400 hover:text-slate-700 dark:text-slate-500 dark:hover:text-slate-300",
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                </button>
              ))}
            </div>
          )}

          <button
            onClick={openSearch}
            className="flex items-center gap-2 rounded-lg bg-slate-100 px-3 py-1.5 text-xs text-slate-400 transition-colors hover:bg-slate-200 hover:text-slate-900 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-slate-700 dark:hover:text-white"
          >
            <Search className="h-3.5 w-3.5" />
            <span>Пошук</span>
            <kbd className="rounded bg-slate-700 px-1.5 py-0.5 font-mono text-[10px] text-white">
              ⌘K
            </kbd>
          </button>

          <button
            onClick={handleAdd}
            className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-500"
          >
            <Plus className="h-3.5 w-3.5" />
            Додати
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar: country list */}
        <div className="flex w-56 flex-shrink-0 flex-col border-r border-slate-200 bg-slate-50 dark:border-slate-800/60 dark:bg-slate-900/40">
          <div className="border-b border-slate-200 px-3 py-2.5 dark:border-slate-800/60">
            <p className="font-mono text-[10px] uppercase tracking-widest text-slate-400 dark:text-slate-500">
              Країни
            </p>
          </div>
          <div className="flex-1 overflow-y-auto py-1">
            {loadingCountries ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-4 w-4 animate-spin text-slate-400 dark:text-slate-500" />
              </div>
            ) : (
              countriesData?.items.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setActiveCountry(c.id)}
                  className={cn(
                    "group flex w-full items-center gap-2.5 px-3 py-2 text-left transition-colors",
                    activeCountryId === c.id
                      ? "border-l-2 border-blue-500 bg-blue-500/10 text-slate-900 dark:text-white"
                      : "text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800/50 dark:hover:text-white",
                  )}
                >
                  <span className="text-base leading-none">
                    {c.flag_emoji ?? "🏳"}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium">{c.name_uk}</p>
                    <p className="font-mono text-[10px] text-slate-400 dark:text-slate-500">
                      {c.code}
                    </p>
                  </div>
                  <ArrowRight className="h-3 w-3 flex-shrink-0 opacity-0 transition-opacity group-hover:opacity-100" />
                </button>
              ))
            )}
          </div>
          <div className="border-t border-slate-200 px-3 py-2 dark:border-slate-800/60">
            <button
              onClick={() => openForm("country")}
              className="flex w-full items-center gap-2 text-xs text-slate-500 transition-colors hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300"
            >
              <Plus className="h-3.5 w-3.5" />
              Нова країна
            </button>
          </div>
        </div>

        {/* Main section */}
        {activeCountryId ? (
          <div className="flex flex-1 overflow-hidden">
            {/* Org panel */}
            <div className="flex w-72 flex-shrink-0 flex-col border-r border-slate-200 dark:border-slate-800/60">
              <div className="flex items-center justify-between border-b border-slate-200 px-3 py-2.5 dark:border-slate-800/60">
                <p className="font-mono text-[10px] uppercase tracking-widest text-slate-400 dark:text-slate-500">
                  Структура
                </p>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => expandAll(allIds)}
                    className="rounded px-1.5 py-0.5 text-[10px] text-slate-500 transition-colors hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300"
                  >
                    розкрити всі
                  </button>
                  <span className="text-slate-400 dark:text-slate-600">·</span>
                  <button
                    onClick={collapseAll}
                    className="rounded px-1.5 py-0.5 text-[10px] text-slate-500 transition-colors hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300"
                  >
                    згорнути
                  </button>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto py-1">
                {loadingDetail ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-4 w-4 animate-spin text-slate-400 dark:text-slate-500" />
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
                        <tr className="font-mono text-[10px] uppercase text-slate-500 dark:text-slate-400">
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
                              "cursor-pointer border-t border-slate-200 transition-colors dark:border-slate-800/40",
                              activeOrgUnitId === u.id
                                ? "bg-blue-50/10"
                                : "hover:bg-slate-100/60 dark:hover:bg-slate-800/40",
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
              <div className="border-t border-slate-200 px-3 py-2 dark:border-slate-800/60">
                <button
                  onClick={() =>
                    openForm("org_unit", { country_id: activeCountryId })
                  }
                  className="flex w-full items-center gap-2 text-xs text-slate-500 transition-colors hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300"
                >
                  <Plus className="h-3.5 w-3.5" />
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
                <div className="h-full space-y-4 overflow-y-auto p-4">
                  <div className="flex items-start gap-4">
                    <span className="text-5xl">
                      {countryDetail.flag_emoji ?? "🏳"}
                    </span>
                    <div>
                      <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                        {countryDetail.name_uk}
                      </h2>
                      <p className="text-sm text-slate-500 dark:text-slate-400">
                        {countryDetail.name_en}
                      </p>
                      {countryDetail.capital && (
                        <p className="mt-1 flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
                          <MapPin className="h-3 w-3" />
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
                        className="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-800/60 dark:bg-slate-900/40"
                      >
                        <div className="mb-1 flex items-center gap-2">
                          <Icon className="h-3.5 w-3.5 text-slate-400 dark:text-slate-500" />
                          <p className="font-mono text-[10px] uppercase text-slate-500 dark:text-slate-400">
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
                    <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-300">
                      {countryDetail.description}
                    </p>
                  )}

                  {countryDetail.resources.length > 0 && (
                    <div className="space-y-2">
                      <p className="font-mono text-[10px] uppercase tracking-widest text-slate-400 dark:text-slate-500">
                        Ресурси
                      </p>
                      {countryDetail.resources.map((r, i) => (
                        <a
                          key={i}
                          href={r.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-2 text-sm text-blue-500 transition-colors hover:text-blue-600 dark:text-blue-400 dark:hover:text-blue-300"
                        >
                          <ExternalLink className="h-3.5 w-3.5 flex-shrink-0" />
                          {r.title}
                        </a>
                      ))}
                    </div>
                  )}

                  {countryDetail.changelog.length > 0 && (
                    <div className="space-y-1">
                      <p className="font-mono text-[10px] uppercase tracking-widest text-slate-400 dark:text-slate-500">
                        Останні зміни
                      </p>
                      {countryDetail.changelog.slice(0, 5).map((e) => (
                        <ChangeLogItem key={e.id} entry={e} />
                      ))}
                    </div>
                  )}

                  {/* Add person at country level */}
                  <div className="border-t border-slate-200 pt-2 dark:border-slate-800">
                    <button
                      onClick={() =>
                        openForm("person", { country_id: activeCountryId })
                      }
                      className="flex w-full items-center justify-center gap-2 rounded-lg border border-violet-500/20 bg-violet-500/10 px-3 py-2 text-xs font-medium text-violet-600 transition-colors hover:bg-violet-500/20 dark:text-violet-400 dark:hover:bg-violet-500/15"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      Додати персону до країни
                    </button>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        ) : (
          <div className="flex flex-1 flex-col items-center justify-center gap-4 px-8 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-50 dark:bg-slate-800/60">
              <Globe2 className="h-8 w-8 text-slate-400 dark:text-slate-500" />
            </div>
            <div>
              <h2 className="mb-1 text-lg font-semibold text-slate-900 dark:text-white">
                Оберіть країну
              </h2>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Виберіть країну зі списку або скористайтесь пошуком,
                <br />
                щоб переглянути організаційну структуру.
              </p>
            </div>
            <button
              onClick={openSearch}
              className="flex items-center gap-2 rounded-lg bg-slate-100 px-4 py-2 text-sm text-slate-700 transition-colors hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
            >
              <Search className="h-4 w-4" />
              Пошук по довіднику
            </button>
          </div>
        )}
      </div>

      {/* Overlays */}
      {isSearchOpen && (
        <SearchOverlay
          countries={countriesData?.items ?? []}
          onClose={closeSearch}
        />
      )}

      {isFormOpen && (
        <HandbookFormModal
          entity={formEntity}
          data={formData}
          onClose={closeForm}
        />
      )}

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
