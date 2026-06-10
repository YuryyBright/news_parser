// src/components/handbook/ContactsEditor.tsx
/**
 * ContactsEditor — редактор контактів персони (email, phone, telegram, custom).
 * ResourcesEditor — редактор ресурсів (посилання, документи, регуляції, відео).
 */
import { useState } from "react";
import {
  Mail,
  Phone,
  MessageCircle,
  Link2,
  Plus,
  Trash2,
  ChevronDown,
  FileText,
  Video,
  BookOpen,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { inputCls } from "./ui";
import type { ResourceLink } from "../../api/handbook";

// ── Contacts ──────────────────────────────────────────────────────────────────

const CONTACT_TYPES = [
  {
    value: "email",
    label: "Email",
    icon: Mail,
    placeholder: "name@example.com",
  },
  { value: "phone", label: "Телефон", icon: Phone, placeholder: "+380…" },
  {
    value: "telegram",
    label: "Telegram",
    icon: MessageCircle,
    placeholder: "@username",
  },
  { value: "other", label: "Інше", icon: Link2, placeholder: "…" },
];

function getContactTypeIcon(type: string) {
  const cfg = CONTACT_TYPES.find((c) => c.value === type);
  const Icon = cfg?.icon ?? Link2;
  return <Icon className="w-3.5 h-3.5" />;
}

interface ContactEntry {
  type: string;
  value: string;
}

function dictToEntries(contacts: Record<string, string>): ContactEntry[] {
  return Object.entries(contacts).map(([type, value]) => ({ type, value }));
}

function entriesToDict(entries: ContactEntry[]): Record<string, string> {
  const result: Record<string, string> = {};
  entries.forEach(({ type, value }, idx) => {
    // deduplicate keys by appending index if type repeats
    const key =
      entries.filter((e, i) => e.type === type && i < idx).length > 0
        ? `${type}_${idx}`
        : type;
    if (value.trim()) result[key] = value;
  });
  return result;
}

export const ContactsEditor = ({
  contacts,
  onChange,
}: {
  contacts: Record<string, string>;
  onChange: (c: Record<string, string>) => void;
}) => {
  const [entries, setEntries] = useState<ContactEntry[]>(() =>
    dictToEntries(contacts),
  );

  const update = (next: ContactEntry[]) => {
    setEntries(next);
    onChange(entriesToDict(next));
  };

  const add = () => update([...entries, { type: "email", value: "" }]);

  const remove = (idx: number) => update(entries.filter((_, i) => i !== idx));

  const setType = (idx: number, type: string) =>
    update(entries.map((e, i) => (i === idx ? { ...e, type } : e)));

  const setValue = (idx: number, value: string) =>
    update(entries.map((e, i) => (i === idx ? { ...e, value } : e)));

  return (
    <div className="space-y-2">
      {entries.map((entry, idx) => {
        const cfg =
          CONTACT_TYPES.find((c) => c.value === entry.type) ?? CONTACT_TYPES[3];
        return (
          <div key={idx} className="flex items-center gap-2">
            {/* Type select */}
            <div className="relative flex-shrink-0">
              <div className="flex items-center gap-1.5 px-2.5 py-2 rounded-lg bg-white dark:bg-slate-100 dark:bg-slate-800/60 border border-slate-300 dark:border-slate-700 text-slate-400 dark:text-slate-500">
                {getContactTypeIcon(entry.type)}
              </div>
              <select
                value={entry.type}
                onChange={(e) => setType(idx, e.target.value)}
                className="absolute inset-0 opacity-0 cursor-pointer w-full"
              >
                {CONTACT_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            {/* Value input */}
            <input
              type={entry.type === "email" ? "email" : "text"}
              value={entry.value}
              onChange={(e) => setValue(idx, e.target.value)}
              placeholder={cfg.placeholder}
              className={cn(inputCls, "flex-1")}
            />
            {/* Remove */}
            <button
              type="button"
              onClick={() => remove(idx)}
              className="p-1.5 rounded-lg text-slate-400 dark:text-slate-600 hover:text-red-400 hover:bg-red-500/10 transition-colors flex-shrink-0"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        );
      })}

      <button
        type="button"
        onClick={add}
        className="flex items-center gap-1.5 text-xs text-slate-400 dark:text-slate-500 hover:text-slate-700 dark:text-slate-300 transition-colors mt-1"
      >
        <Plus className="w-3.5 h-3.5" />
        Додати контакт
      </button>
    </div>
  );
};

// ── Resources ─────────────────────────────────────────────────────────────────

const RESOURCE_TYPES = [
  { value: "link", label: "Посилання", icon: Link2 },
  { value: "document", label: "Документ", icon: FileText },
  { value: "regulation", label: "НПА", icon: BookOpen },
  { value: "video", label: "Відео", icon: Video },
];

function getResourceIcon(type: string) {
  const cfg = RESOURCE_TYPES.find((r) => r.value === type);
  const Icon = cfg?.icon ?? Link2;
  return <Icon className="w-3.5 h-3.5" />;
}

export const ResourcesEditor = ({
  resources,
  onChange,
}: {
  resources: ResourceLink[];
  onChange: (r: ResourceLink[]) => void;
}) => {
  const add = () =>
    onChange([...resources, { url: "", title: "", resource_type: "link" }]);

  const remove = (idx: number) =>
    onChange(resources.filter((_, i) => i !== idx));

  const update = (idx: number, patch: Partial<ResourceLink>) =>
    onChange(resources.map((r, i) => (i === idx ? { ...r, ...patch } : r)));

  return (
    <div className="space-y-3">
      {resources.map((r, idx) => (
        <div
          key={idx}
          className="p-3 rounded-lg bg-slate-50/80 dark:bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 space-y-2"
        >
          <div className="flex items-center gap-2">
            {/* Type */}
            <div className="relative">
              <div className="flex items-center gap-1 px-2 py-1.5 rounded bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-400 dark:text-slate-500 text-xs">
                {getResourceIcon(r.resource_type)}
                <span>
                  {RESOURCE_TYPES.find((t) => t.value === r.resource_type)
                    ?.label ?? r.resource_type}
                </span>
                <ChevronDown className="w-3 h-3" />
              </div>
              <select
                value={r.resource_type}
                onChange={(e) =>
                  update(idx, {
                    resource_type: e.target
                      .value as ResourceLink["resource_type"],
                  })
                }
                className="absolute inset-0 opacity-0 cursor-pointer w-full"
              >
                {RESOURCE_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex-1" />
            <button
              type="button"
              onClick={() => remove(idx)}
              className="p-1 rounded text-slate-400 dark:text-slate-600 hover:text-red-400 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
          <input
            type="text"
            value={r.title}
            onChange={(e) => update(idx, { title: e.target.value })}
            placeholder="Назва ресурсу"
            className={inputCls}
          />
          <input
            type="url"
            value={r.url}
            onChange={(e) => update(idx, { url: e.target.value })}
            placeholder="https://…"
            className={inputCls}
          />
        </div>
      ))}

      <button
        type="button"
        onClick={add}
        className="flex items-center gap-1.5 text-xs text-slate-400 dark:text-slate-500 hover:text-slate-700 dark:text-slate-300 transition-colors"
      >
        <Plus className="w-3.5 h-3.5" />
        Додати ресурс
      </button>
    </div>
  );
};
