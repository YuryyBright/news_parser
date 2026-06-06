// src/components/handbook/PersonDrawer.tsx
/**
 * PersonDrawer — повна картка персони з вкладками:
 *   - Профіль (фото, біо, контакти, ресурси)
 *   - Новини (прив'язані статті + фрагменти)
 *   - Заходи (events — зустрічі, виступи, переговори)
 *   - Журнал змін
 */
import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  X,
  ChevronLeft,
  ExternalLink,
  Mail,
  Phone,
  MessageCircle,
  Calendar,
  Link2,
  FileText,
  Clock,
  Edit3,
  Trash2,
  Plus,
  Globe2,
  Activity,
  UserCheck,
  UserX,
  BookOpen,
  Newspaper,
  CalendarDays,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { cn, formatDate, formatDateFull } from "../../lib/utils";
import { handbookApi, fullName } from "../../api/handbook";
import type {
  Person,
  NewsLink,
  ChangeLogEntry,
  HandbookEvent,
} from "../../api/handbook";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Props {
  person: Person | null;
  onClose: () => void;
  onEdit?: (person: Person) => void;
  onDelete?: (person: Person) => void;
  onAddEvent?: (personId: string) => void;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const EVENT_TYPE_CONFIG: Record<
  string,
  { label: string; color: string; icon: typeof Calendar }
> = {
  meeting: {
    label: "Зустріч",
    color: "bg-blue-500/15 text-blue-400 border-blue-500/25",
    icon: Calendar,
  },
  speech: {
    label: "Виступ",
    color: "bg-accent-bg text-accent border-violet-500/25",
    icon: Activity,
  },
  negotiation: {
    label: "Переговори",
    color: "bg-amber-500/15 text-amber-400 border-amber-500/25",
    icon: MessageCircle,
  },
  press: {
    label: "Прес-конф.",
    color: "bg-sky-500/15 text-sky-400 border-sky-500/25",
    icon: Newspaper,
  },
  travel: {
    label: "Поїздка",
    color: "bg-teal-500/15 text-teal-400 border-teal-500/25",
    icon: Globe2,
  },
  appointment: {
    label: "Призначення",
    color: "bg-emerald-500/15 text-emerald-400 border-emerald-500/25",
    icon: UserCheck,
  },
  dismissal: {
    label: "Звільнення",
    color: "bg-red-500/15 text-red-400 border-red-500/25",
    icon: UserX,
  },
};

const ContactIcon = ({ type }: { type: string }) => {
  if (type === "email") return <Mail className="w-3.5 h-3.5" />;
  if (type === "phone") return <Phone className="w-3.5 h-3.5" />;
  if (type === "telegram") return <MessageCircle className="w-3.5 h-3.5" />;
  return <Link2 className="w-3.5 h-3.5" />;
};

const contactHref = (type: string, value: string) => {
  if (type === "email") return `mailto:${value}`;
  if (type === "phone") return `tel:${value}`;
  if (type === "telegram") return `https://t.me/${value.replace("@", "")}`;
  return value;
};

// ── Tab components ────────────────────────────────────────────────────────────

const ProfileTab = ({ person }: { person: Person }) => (
  <div className="space-y-5">
    {/* Bio */}
    {person.bio && (
      <div className="space-y-1.5">
        <p className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-widest">
          Біографія
        </p>
        <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-wrap">
          {person.bio}
        </p>
      </div>
    )}

    {/* Appointment dates */}
    {(person.date_appointed || person.date_dismissed) && (
      <div className="grid grid-cols-2 gap-3">
        {person.date_appointed && (
          <div className="rounded-lg border border-slate-200 dark:border-slate-200/60 dark:border-slate-800/60 bg-slate-50 dark:bg-slate-900/40 p-3">
            <p className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase mb-1">
              Призначений
            </p>
            <p className="text-sm text-emerald-400 font-medium">
              {formatDate(person.date_appointed)}
            </p>
          </div>
        )}
        {person.date_dismissed && (
          <div className="rounded-lg border border-slate-200 dark:border-slate-200/60 dark:border-slate-800/60 bg-slate-50 dark:bg-slate-900/40 p-3">
            <p className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase mb-1">
              Звільнений
            </p>
            <p className="text-sm text-red-400 font-medium">
              {formatDate(person.date_dismissed)}
            </p>
          </div>
        )}
      </div>
    )}

    {/* Contacts */}
    {person.contacts && Object.keys(person.contacts).length > 0 && (
      <div className="space-y-2">
        <p className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-widest">
          Контакти
        </p>
        <div className="space-y-1.5">
          {Object.entries(person.contacts).map(([type, value]) => (
            <a
              key={type}
              href={contactHref(type, value)}
              target={
                type !== "email" && type !== "phone" ? "_blank" : undefined
              }
              rel="noopener noreferrer"
              className="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-slate-100/60 dark:bg-slate-100 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-200/60 dark:border-slate-800/60 hover:border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:bg-slate-800/80 transition-all group"
            >
              <span className="text-slate-400 dark:text-slate-500 group-hover:text-slate-400 dark:text-slate-500 dark:text-slate-400 transition-colors">
                <ContactIcon type={type} />
              </span>
              <span className="text-xs text-slate-700 dark:text-slate-300 group-hover:text-slate-900 dark:text-white transition-colors flex-1">
                {value}
              </span>
              <ExternalLink className="w-3 h-3 text-slate-400 dark:text-slate-600 group-hover:text-slate-400 dark:text-slate-500 dark:text-slate-400 transition-colors" />
            </a>
          ))}
        </div>
      </div>
    )}

    {/* Resources */}
    {person.resources && person.resources.length > 0 && (
      <div className="space-y-2">
        <p className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-widest">
          Ресурси
        </p>
        <div className="space-y-1.5">
          {person.resources.map((r, i) => (
            <a
              key={i}
              href={r.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-slate-100/60 dark:bg-slate-100 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-200/60 dark:border-slate-800/60 hover:border-blue-500/30 hover:bg-blue-500/5 transition-all group"
            >
              <FileText className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500 group-hover:text-blue-400 transition-colors flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs text-slate-700 dark:text-slate-300 group-hover:text-slate-900 dark:text-white transition-colors truncate">
                  {r.title}
                </p>
                <p className="text-[10px] text-slate-400 dark:text-slate-600">
                  {r.resource_type}
                </p>
              </div>
              <ExternalLink className="w-3 h-3 text-slate-400 dark:text-slate-600 group-hover:text-blue-400 transition-colors" />
            </a>
          ))}
        </div>
      </div>
    )}

    {/* Meta */}
    <div className="pt-2 border-t border-slate-200 dark:border-slate-200/60 dark:border-slate-800/60 flex items-center gap-4 text-[11px] text-slate-400 dark:text-slate-600">
      <span className="flex items-center gap-1">
        <Clock className="w-3 h-3" />
        Додано {formatDate(person.created_at)}
      </span>
      <span className="flex items-center gap-1">
        <Clock className="w-3 h-3" />
        Оновлено {formatDate(person.updated_at)}
      </span>
    </div>
  </div>
);

const NewsTab = ({ person }: { person: Person }) => {
  if (!person.news_links || person.news_links.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-white dark:bg-slate-100 dark:bg-slate-800/60 flex items-center justify-center">
          <Newspaper className="w-5 h-5 text-slate-400 dark:text-slate-600" />
        </div>
        <div>
          <p className="text-sm text-slate-400 dark:text-slate-500 dark:text-slate-400">
            Немає прив'язаних новин
          </p>
          <p className="text-xs text-slate-400 dark:text-slate-600 mt-0.5">
            Прив'яжіть статті через кнопку «Довідник» у читалці
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {person.news_links.map((link) => (
        <NewsLinkCard key={link.id} link={link} />
      ))}
    </div>
  );
};

const NewsLinkCard = ({ link }: { link: NewsLink }) => (
  <div className="rounded-lg border border-slate-200 dark:border-slate-200/60 dark:border-slate-800/60 bg-slate-50 dark:bg-slate-900/40 p-3 space-y-2">
    <div className="flex items-start gap-2">
      <div className="w-6 h-6 rounded-md bg-violet-500/15 flex items-center justify-center flex-shrink-0 mt-0.5">
        <BookOpen className="w-3.5 h-3.5 text-violet-400" />
      </div>
      <div className="flex-1 min-w-0">
        {link.note && (
          <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
            {link.note}
          </p>
        )}
        {link.excerpt && (
          <blockquote className="mt-1.5 pl-2 border-l-2 border-violet-500/40 text-[11px] text-slate-400 dark:text-slate-500 dark:text-slate-400 italic line-clamp-3">
            {link.excerpt}
          </blockquote>
        )}
        <div className="flex items-center gap-2 mt-1.5">
          <span className="text-[10px] text-slate-400 dark:text-slate-600 font-mono">
            {formatDate(link.created_at)}
          </span>
          {link.pinned_by && (
            <span className="text-[10px] text-slate-400 dark:text-slate-600">
              · {link.pinned_by}
            </span>
          )}
        </div>
      </div>
    </div>
  </div>
);

const EventsTab = ({
  person,
  onAddEvent,
}: {
  person: Person;
  onAddEvent?: () => void;
}) => {
  const { data: events, isLoading } = useQuery<HandbookEvent[]>({
    queryKey: ["person-events", person.id],
    queryFn: () => handbookApi.getPersonEvents(person.id).catch(() => []),
    staleTime: 60_000,
  });
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-5 h-5 border-2 border-slate-300 dark:border-slate-700 border-t-violet-500 rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {onAddEvent && (
        <button
          onClick={onAddEvent}
          className="w-full flex items-center justify-center gap-2 py-2 rounded-lg border border-dashed border-slate-300 dark:border-slate-700 text-xs text-slate-400 dark:text-slate-500 hover:text-slate-700 dark:text-slate-300 hover:border-slate-400 dark:hover:border-slate-600 transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          Додати захід
        </button>
      )}

      {!events?.length ? (
        <div className="flex flex-col items-center justify-center py-10 text-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-white dark:bg-slate-100 dark:bg-slate-800/60 flex items-center justify-center">
            <CalendarDays className="w-5 h-5 text-slate-400 dark:text-slate-600" />
          </div>
          <div>
            <p className="text-sm text-slate-400 dark:text-slate-500 dark:text-slate-400">
              Заходи не зафіксовані
            </p>
            <p className="text-xs text-slate-400 dark:text-slate-600 mt-0.5">
              Додайте зустрічі, виступи або переговори
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {events.map((event) => {
            const cfg = EVENT_TYPE_CONFIG[event.event_type] ?? {
              label: event.event_type,
              color: "bg-zinc-500/15 text-zinc-400 border-zinc-500/25",
              icon: Calendar,
            };
            const Icon = cfg.icon;
            return (
              <div
                key={event.id}
                className="rounded-lg border border-slate-200 dark:border-slate-200/60 dark:border-slate-800/60 bg-slate-50 dark:bg-slate-900/40 p-3 space-y-1.5"
              >
                <div className="flex items-start gap-2.5">
                  <div className="w-7 h-7 rounded-lg bg-slate-100 dark:bg-slate-800 flex items-center justify-center flex-shrink-0">
                    <Icon className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500 dark:text-slate-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span
                        className={cn(
                          "inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border",
                          cfg.color,
                        )}
                      >
                        {cfg.label}
                      </span>
                      <span className="text-[11px] text-slate-400 dark:text-slate-500 font-mono">
                        {formatDate(event.date)}
                      </span>
                    </div>
                    <p className="text-sm text-slate-900 dark:text-white mt-1 leading-snug">
                      {event.title}
                    </p>
                    {event.location && (
                      <p className="text-xs text-slate-400 dark:text-slate-500 flex items-center gap-1 mt-0.5">
                        <Globe2 className="w-3 h-3" />
                        {event.location}
                      </p>
                    )}
                    {event.description && (
                      <p className="text-xs text-slate-400 dark:text-slate-500 dark:text-slate-400 mt-1 leading-relaxed line-clamp-2">
                        {event.description}
                      </p>
                    )}
                    {event.participants && event.participants.length > 0 && (
                      <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-1">
                        Учасники: {event.participants.join(", ")}
                      </p>
                    )}
                  </div>
                  {event.source_url && (
                    <a
                      href={event.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-shrink-0 p-1 rounded text-slate-400 dark:text-slate-600 hover:text-blue-400 transition-colors"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

const ChangelogTab = ({ person }: { person: Person }) => {
  if (!person.changelog || person.changelog.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center gap-3">
        <p className="text-sm text-slate-400 dark:text-slate-500">
          Журнал порожній
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-0">
      {person.changelog.map((entry) => (
        <ChangelogEntry key={entry.id} entry={entry} />
      ))}
    </div>
  );
};

const ChangelogEntry = ({ entry }: { entry: ChangeLogEntry }) => (
  <div className="flex items-start gap-2.5 py-2.5 border-b border-slate-200 dark:border-slate-800/50 last:border-0">
    <div
      className={cn(
        "mt-0.5 flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold",
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
            «{entry.field_name}»
          </span>
        )}
      </p>
      {entry.diff && Object.keys(entry.diff).length > 0 && (
        <div className="mt-1 space-y-0.5">
          {Object.entries(entry.diff)
            .slice(0, 3)
            .map(([key, val]) => (
              <p
                key={key}
                className="text-[11px] font-mono text-slate-400 dark:text-slate-600 truncate"
              >
                {key}:{" "}
                <span className="text-red-400/80 line-through">
                  {String((val as any)?.old ?? "—").slice(0, 35)}
                </span>
                {" → "}
                <span className="text-emerald-400/80">
                  {String((val as any)?.new ?? "—").slice(0, 35)}
                </span>
              </p>
            ))}
        </div>
      )}
      <p className="text-[10px] text-slate-400 dark:text-slate-600 mt-0.5">
        {formatDateFull(entry.created_at)}
      </p>
    </div>
  </div>
);

// ── Main component ────────────────────────────────────────────────────────────

type TabKey = "profile" | "news" | "events" | "changelog";

const TABS: { key: TabKey; label: string; icon: typeof BookOpen }[] = [
  { key: "profile", label: "Профіль", icon: UserCheck },
  { key: "news", label: "Новини", icon: Newspaper },
  { key: "events", label: "Заходи", icon: CalendarDays },
  { key: "changelog", label: "Журнал", icon: Clock },
];

export const PersonDrawer = ({
  person,
  onClose,
  onEdit,
  onDelete,
  onAddEvent,
}: Props) => {
  const [activeTab, setActiveTab] = useState<TabKey>("profile");

  return (
    <AnimatePresence>
      {person && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/40 z-40 backdrop-blur-sm hidden md:block"
            onClick={onClose}
          />

          {/* Drawer */}
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 280 }}
            className={cn(
              "fixed inset-0 z-50 flex flex-col",
              "md:left-auto md:right-0 md:inset-y-0 md:w-full md:max-w-xl",
              "bg-white dark:bg-slate-950 border-l border-slate-200 dark:border-slate-800",
              "shadow-2xl",
            )}
          >
            {/* Header */}
            <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-200 dark:border-slate-800 flex-shrink-0">
              <button
                onClick={onClose}
                className="md:hidden p-1.5 -ml-1 rounded-lg text-slate-400 dark:text-slate-500 hover:text-slate-900 dark:text-white hover:bg-slate-100 dark:bg-slate-800 transition-colors"
              >
                <ChevronLeft className="w-5 h-5" />
              </button>

              {/* Avatar */}
              <div className="flex-shrink-0 w-10 h-10 rounded-xl overflow-hidden bg-slate-100 dark:bg-slate-800 flex items-center justify-center">
                {person.photo_url ? (
                  <img
                    src={person.photo_url}
                    alt={fullName(person)}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <span className="text-sm font-bold text-slate-700 dark:text-slate-300">
                    {person.first_name?.[0]}
                    {person.last_name?.[0]}
                  </span>
                )}
              </div>

              <div className="flex-1 min-w-0">
                <h2 className="text-sm font-bold text-slate-900 dark:text-white truncate">
                  {fullName(person)}
                </h2>
                {person.position_title && (
                  <p className="text-xs text-slate-400 dark:text-slate-500 dark:text-slate-400 truncate">
                    {person.position_title}
                  </p>
                )}
                {person.rank && (
                  <p className="text-[11px] text-amber-400/80 truncate">
                    {person.rank}
                  </p>
                )}
              </div>

              <div className="flex items-center gap-1 flex-shrink-0">
                {/* Status badge */}
                <span
                  className={cn(
                    "px-2 py-0.5 rounded-full text-[10px] font-medium border",
                    person.is_active
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                      : "bg-zinc-500/10 text-zinc-500 border-zinc-500/20",
                  )}
                >
                  {person.is_active ? "активний" : "неактивний"}
                </span>

                {onEdit && (
                  <button
                    onClick={() => onEdit(person)}
                    className="p-1.5 rounded-lg text-slate-400 dark:text-slate-500 hover:text-slate-900 dark:text-white hover:bg-slate-100 dark:bg-slate-800 transition-colors"
                    title="Редагувати"
                  >
                    <Edit3 className="w-4 h-4" />
                  </button>
                )}
                {onDelete && (
                  <button
                    onClick={() => onDelete(person)}
                    className="p-1.5 rounded-lg text-slate-400 dark:text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                    title="Видалити"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
                <button
                  onClick={onClose}
                  className="hidden md:flex p-1.5 rounded-lg text-slate-400 dark:text-slate-500 hover:text-slate-900 dark:text-white hover:bg-slate-100 dark:bg-slate-800 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Tabs */}
            <div className="flex items-center gap-0.5 px-3 pt-2 pb-0 border-b border-slate-200 dark:border-slate-800 flex-shrink-0 overflow-x-auto">
              {TABS.map((tab) => {
                const Icon = tab.icon;
                const count =
                  tab.key === "news"
                    ? person.news_links?.length
                    : tab.key === "changelog"
                      ? person.changelog?.length
                      : undefined;

                return (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    className={cn(
                      "flex items-center gap-1.5 px-3 py-2 text-xs font-medium whitespace-nowrap",
                      "border-b-2 -mb-px transition-colors",
                      activeTab === tab.key
                        ? "border-blue-500 text-slate-900 dark:text-white"
                        : "border-transparent text-slate-400 dark:text-slate-500 hover:text-slate-700 dark:text-slate-300",
                    )}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    {tab.label}
                    {count != null && count > 0 && (
                      <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-400 dark:text-slate-500 dark:text-slate-400 font-mono">
                        {count}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto overscroll-contain p-4">
              {activeTab === "profile" && <ProfileTab person={person} />}
              {activeTab === "news" && <NewsTab person={person} />}
              {activeTab === "events" && (
                <EventsTab
                  person={person}
                  onAddEvent={
                    onAddEvent ? () => onAddEvent(person.id) : undefined
                  }
                />
              )}
              {activeTab === "changelog" && <ChangelogTab person={person} />}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
};
