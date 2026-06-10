// src/components/handbook/EventFormModal.tsx
/**
 * EventFormModal — створення/редагування заходу персони або структури.
 * Тип заходу: зустріч, виступ, переговори, прес-конф, поїздка, призначення, звільнення.
 * Можна прив'язати до статті або вказати зовнішнє джерело.
 */
import { useState, useEffect, useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  X,
  Loader2,
  Check,
  AlertCircle,
  Calendar,
  Globe2,
  Users,
  Link2,
  CalendarDays,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { handbookApi } from "../../api/handbook";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface EventPayload {
  person_id?: string;
  org_unit_id?: string;
  country_id?: string;
  title: string;
  event_type: string;
  date: string; // ISO datetime
  location?: string;
  description?: string;
  participants?: string[];
  source_url?: string;
  article_id?: string;
}

interface Props {
  personId?: string;
  orgUnitId?: string;
  countryId?: string;
  data?: Partial<EventPayload> & { id?: string };
  onClose: () => void;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const EVENT_TYPES = [
  { value: "meeting", label: "🤝 Зустріч" },
  { value: "speech", label: "🎤 Виступ / Заява" },
  { value: "negotiation", label: "💬 Переговори" },
  { value: "press", label: "📰 Прес-конференція" },
  { value: "travel", label: "✈️ Поїздка / Відрядження" },
  { value: "appointment", label: "✅ Призначення" },
  { value: "dismissal", label: "❌ Звільнення / Відставка" },
  { value: "signing", label: "📝 Підписання документа" },
  { value: "sanction", label: "🚫 Санкція / Обмеження" },
  { value: "other", label: "📋 Інше" },
];

// ── Field helpers ─────────────────────────────────────────────────────────────

const Field = ({
  label,
  required,
  hint,
  children,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  children: React.ReactNode;
}) => (
  <div className="space-y-1.5">
    <label className="flex items-center gap-1 text-[11px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-wider">
      {label}
      {required && <span className="text-red-400">*</span>}
      {hint && (
        <span className="text-slate-400 dark:text-slate-600 normal-case font-sans ml-1">
          ({hint})
        </span>
      )}
    </label>
    {children}
  </div>
);

const inputCls = cn(
  "w-full bg-white dark:bg-slate-100 dark:bg-slate-800/60 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-2",
  "text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 outline-none",
  "focus:border-blue-500/50 focus:bg-slate-100 dark:bg-slate-800 transition-colors",
);

// ── Component ─────────────────────────────────────────────────────────────────

export const EventFormModal = ({
  personId,
  orgUnitId,
  countryId,
  data,
  onClose,
}: Props) => {
  const qc = useQueryClient();
  const overlayRef = useRef<HTMLDivElement>(null);
  const isEdit = !!data?.id;

  const [title, setTitle] = useState(data?.title ?? "");
  const [eventType, setEventType] = useState(data?.event_type ?? "meeting");
  const [date, setDate] = useState(
    data?.date ? data.date.slice(0, 16) : new Date().toISOString().slice(0, 16),
  );
  const [location, setLocation] = useState(data?.location ?? "");
  const [description, setDescription] = useState(data?.description ?? "");
  const [participantsRaw, setParticipantsRaw] = useState(
    (data?.participants ?? []).join(", "),
  );
  const [sourceUrl, setSourceUrl] = useState(data?.source_url ?? "");
  const [articleId, setArticleId] = useState(data?.article_id ?? "");

  // Esc to close
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const { mutate, isPending, isSuccess, error } = useMutation({
    mutationFn: () => {
      const payload: EventPayload = {
        person_id: personId,
        org_unit_id: orgUnitId,
        country_id: countryId,
        title: title.trim(),
        event_type: eventType,
        date: new Date(date).toISOString(),
        location: location.trim() || undefined,
        description: description.trim() || undefined,
        participants: participantsRaw
          ? participantsRaw
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean)
          : undefined,
        source_url: sourceUrl.trim() || undefined,
        article_id: articleId.trim() || undefined,
      };
      if (isEdit) {
        return handbookApi.updateEvent!(data!.id!, payload);
      }
      return handbookApi.createEvent!(payload);
    },
    onSuccess: () => {
      // Інвалідуємо кеш заходів для цієї персони/структури
      if (personId)
        qc.invalidateQueries({ queryKey: ["person-events", personId] });
      if (orgUnitId)
        qc.invalidateQueries({ queryKey: ["org-unit-events", orgUnitId] });
      setTimeout(onClose, 900);
    },
  });

  const canSubmit = title.trim().length > 0 && !!date;

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 bg-black/20 dark:bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
      onMouseDown={(e) => {
        if (e.target === overlayRef.current) onClose();
      }}
    >
      <div className="w-full max-w-lg bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-800 flex-shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-amber-500/15 border border-amber-500/25 flex items-center justify-center">
              <CalendarDays className="w-4 h-4 text-amber-400" />
            </div>
            <h2 className="text-sm font-semibold text-slate-900 dark:text-white">
              {isEdit ? "Редагувати захід" : "Додати захід"}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md text-slate-400 dark:text-slate-500 hover:text-slate-900 dark:text-white hover:bg-slate-100 dark:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Type + Date row */}
          <div className="grid grid-cols-2 gap-3">
            <Field label="Тип заходу" required>
              <select
                value={eventType}
                onChange={(e) => setEventType(e.target.value)}
                className={inputCls}
              >
                {EVENT_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Дата та час" required>
              <input
                type="datetime-local"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className={inputCls}
              />
            </Field>
          </div>

          <Field label="Назва / заголовок" required>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Зустріч із міністром оборони…"
              className={inputCls}
            />
          </Field>

          <Field label="Місце проведення">
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="Київ, Офіс президента"
              className={inputCls}
            />
          </Field>

          <Field label="Опис / деталі">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Детальний опис заходу…"
              rows={3}
              className={cn(inputCls, "resize-none")}
            />
          </Field>

          <Field label="Учасники" hint="через кому">
            <input
              type="text"
              value={participantsRaw}
              onChange={(e) => setParticipantsRaw(e.target.value)}
              placeholder="Іванов І.І., Петров П.П."
              className={inputCls}
            />
          </Field>

          {/* Sources */}
          <div className="grid grid-cols-2 gap-3">
            <Field label="Джерело (URL)">
              <input
                type="url"
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
                placeholder="https://…"
                className={inputCls}
              />
            </Field>
            <Field label="ID статті" hint="якщо з новин">
              <input
                type="text"
                value={articleId}
                onChange={(e) => setArticleId(e.target.value)}
                placeholder="uuid…"
                className={inputCls}
              />
            </Field>
          </div>
        </div>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-slate-200 dark:border-slate-800 flex-shrink-0 space-y-2">
          {error && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20">
              <AlertCircle className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />
              <p className="text-xs text-red-400">{(error as Error).message}</p>
            </div>
          )}
          <button
            onClick={() => mutate()}
            disabled={isPending || isSuccess || !canSubmit}
            className={cn(
              "w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all",
              isSuccess
                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                : "bg-amber-600 hover:bg-amber-500 text-slate-900 dark:text-white",
              "disabled:opacity-60 disabled:cursor-not-allowed",
            )}
          >
            {isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : isSuccess ? (
              <>
                <Check className="w-4 h-4" /> Збережено!
              </>
            ) : isEdit ? (
              "Зберегти зміни"
            ) : (
              "Додати захід"
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
