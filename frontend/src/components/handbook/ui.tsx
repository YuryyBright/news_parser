// src/components/handbook/ui.tsx
/**
 * Shared UI primitives used across all handbook form components.
 * Field, Input, Textarea, Select, Toggle, DateInput, SectionDivider, SubmitButton
 *
 * 🎨 DARK / LIGHT THEME
 * ─────────────────────
 * Requires tailwind.config.js: { darkMode: 'class' }
 * Add class="dark" to <html> for dark mode (e.g. via next-themes or own hook).
 *
 * SEMANTIC TOKEN MAP (dark → light):
 *   bg-white dark:bg-slate-950        → bg-white
 *   bg-slate-50 dark:bg-slate-900        → bg-slate-50
 *   bg-white dark:bg-slate-100 dark:bg-slate-800/60     → bg-white  (inputs)
 *   bg-slate-100 dark:bg-slate-800        → bg-slate-100
 *   border-slate-200 dark:border-slate-800    → border-slate-200
 *   border-slate-300 dark:border-slate-700    → border-slate-300
 *   text-slate-900 dark:text-white          → text-slate-900
 *   text-slate-700 dark:text-slate-300      → text-slate-700
 *   text-slate-400 dark:text-slate-500 dark:text-slate-400      → text-slate-400 dark:text-slate-500
 *   text-slate-400 dark:text-slate-500      → text-slate-400 dark:text-slate-500 dark:text-slate-400
 *   text-slate-400 dark:text-slate-600      → text-slate-400 dark:text-slate-500 dark:text-slate-400
 *   placeholder-slate-400 dark:placeholder-slate-500 → placeholder-slate-400
 */
import { cn } from "../../lib/utils";
import { Calendar, Loader2, Check, AlertCircle } from "lucide-react";

// ── Field wrapper ─────────────────────────────────────────────────────────────

export const Field = ({
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
    <label
      className="flex items-center gap-1.5 text-[11px] font-mono uppercase tracking-wider
      text-slate-400 dark:text-slate-500 dark:text-slate-400 dark:text-slate-500 dark:text-slate-400"
    >
      {label}
      {required && <span className="text-red-500 dark:text-red-400">*</span>}
      {hint && (
        <span
          className="normal-case font-sans ml-1
          text-slate-400 dark:text-slate-500 dark:text-slate-400 dark:text-slate-400 dark:text-slate-600"
        >
          ({hint})
        </span>
      )}
    </label>
    {children}
  </div>
);

// ── Base input class ──────────────────────────────────────────────────────────
// Used directly in ContactsEditor, CountryForm, EventFormModal — import from here.

export const inputCls = cn(
  "w-full border rounded-lg px-3 py-2 text-sm outline-none transition-colors",
  // Light
  "bg-white border-slate-300 text-slate-900 placeholder-slate-400",
  "focus:border-blue-500 focus:bg-white",
  // Dark
  "dark:bg-white dark:bg-slate-100 dark:bg-slate-800/60 dark:border-slate-300 dark:border-slate-700 dark:text-slate-900 dark:text-white dark:placeholder-slate-400 dark:placeholder-slate-500",
  "dark:focus:border-blue-500/50 dark:focus:bg-slate-100 dark:bg-slate-800",
);

// ── Auto-capitalize first letter ──────────────────────────────────────────────

export function autoCapitalize(val: string): string {
  if (!val) return val;
  return val.charAt(0).toUpperCase() + val.slice(1);
}

// ── Input ─────────────────────────────────────────────────────────────────────

export const Input = ({
  value,
  onChange,
  placeholder,
  type = "text",
  autoCapitalized,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  autoCapitalized?: boolean;
  disabled?: boolean;
}) => (
  <input
    type={type}
    value={value}
    disabled={disabled}
    onChange={(e) => {
      const v = e.target.value;
      onChange(autoCapitalized ? autoCapitalize(v) : v);
    }}
    placeholder={placeholder}
    className={cn(inputCls, disabled && "opacity-60 cursor-not-allowed")}
  />
);

// ── Textarea ──────────────────────────────────────────────────────────────────

export const Textarea = ({
  value,
  onChange,
  placeholder,
  rows = 3,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  rows?: number;
}) => (
  <textarea
    value={value}
    onChange={(e) => onChange(e.target.value)}
    placeholder={placeholder}
    rows={rows}
    className={cn(inputCls, "resize-none")}
  />
);

// ── Select ────────────────────────────────────────────────────────────────────

export const Select = ({
  value,
  onChange,
  options,
  placeholder,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  placeholder?: string;
  disabled?: boolean;
}) => (
  <select
    value={value}
    disabled={disabled}
    onChange={(e) => onChange(e.target.value)}
    className={cn(inputCls, disabled && "opacity-60 cursor-not-allowed")}
  >
    <option value="">{placeholder ?? "— оберіть —"}</option>
    {options.map((o) => (
      <option key={o.value} value={o.value}>
        {o.label}
      </option>
    ))}
  </select>
);

// ── Toggle ────────────────────────────────────────────────────────────────────

export const Toggle = ({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) => (
  <button
    type="button"
    onClick={() => onChange(!value)}
    className="flex items-center gap-2.5 group"
  >
    <div
      className={cn(
        "w-9 h-5 rounded-full transition-colors relative",
        value ? "bg-blue-600" : "bg-slate-300 dark:bg-slate-700",
      )}
    >
      <div
        className={cn(
          "absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform",
          value ? "translate-x-4" : "translate-x-0.5",
        )}
      />
    </div>
    <span
      className="text-sm transition-colors
      text-slate-700 group-hover:text-slate-900
      dark:text-slate-700 dark:text-slate-300 dark:group-hover:text-slate-900 dark:text-white"
    >
      {label}
    </span>
  </button>
);

// ── DateInput ─────────────────────────────────────────────────────────────────

export const DateInput = ({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) => (
  <div className="relative">
    <input
      type="date"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={cn(inputCls, "pr-8")}
    />
    <Calendar
      className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 pointer-events-none
      text-slate-400 dark:text-slate-500 dark:text-slate-400 dark:text-slate-400 dark:text-slate-500"
    />
  </div>
);

// ── DateRangePicker ───────────────────────────────────────────────────────────

export const DateRangePicker = ({
  startDate,
  endDate,
  onStartChange,
  onEndChange,
  labelStart = "З",
  labelEnd = "По",
}: {
  startDate: string;
  endDate: string;
  onStartChange: (v: string) => void;
  onEndChange: (v: string) => void;
  labelStart?: string;
  labelEnd?: string;
}) => (
  <div className="flex items-end gap-2">
    <Field label={labelStart}>
      <DateInput value={startDate} onChange={onStartChange} />
    </Field>
    <span
      className="mb-2 text-sm pb-0.5
      text-slate-400 dark:text-slate-500 dark:text-slate-400 dark:text-slate-400 dark:text-slate-500"
    >
      —
    </span>
    <Field label={labelEnd}>
      <DateInput value={endDate} onChange={onEndChange} />
    </Field>
  </div>
);

// ── SectionDivider ────────────────────────────────────────────────────────────

export const SectionDivider = ({ label }: { label: string }) => (
  <div className="flex items-center gap-3 py-1">
    <span
      className="text-[10px] font-mono uppercase tracking-widest whitespace-nowrap
      text-slate-400 dark:text-slate-500 dark:text-slate-400 dark:text-slate-400 dark:text-slate-500"
    >
      {label}
    </span>
    <div
      className="flex-1 h-px
      bg-slate-200 dark:bg-slate-100 dark:bg-slate-800"
    />
  </div>
);

// ── SubmitButton ──────────────────────────────────────────────────────────────

export const SubmitButton = ({
  isPending,
  isSuccess,
  error,
  isEdit,
  onSubmit,
  disabled,
  label,
  editLabel,
}: {
  isPending: boolean;
  isSuccess: boolean;
  error: Error | null;
  isEdit: boolean;
  onSubmit: () => void;
  disabled?: boolean;
  label?: string;
  editLabel?: string;
}) => (
  <div className="space-y-2 pt-2">
    {error && (
      <div
        className="flex items-center gap-2 px-3 py-2 rounded-lg
        bg-red-50 border border-red-200 text-red-600
        dark:bg-red-500/10 dark:border-red-500/20 dark:text-red-400"
      >
        <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
        <p className="text-xs">{error.message}</p>
      </div>
    )}
    <button
      type="button"
      onClick={onSubmit}
      disabled={isPending || isSuccess || disabled}
      className={cn(
        "w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all",
        isSuccess
          ? "bg-emerald-500/20 text-emerald-600 border border-emerald-500/30 dark:text-emerald-400"
          : "bg-blue-600 hover:bg-blue-500 text-slate-900 dark:text-white",
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
        (editLabel ?? "Зберегти зміни")
      ) : (
        (label ?? "Зберегти")
      )}
    </button>
  </div>
);

// ── Pagination ────────────────────────────────────────────────────────────────

export const Pagination = ({
  page,
  pages,
  total,
  pageSize,
  onPage,
}: {
  page: number;
  pages: number;
  total: number;
  pageSize: number;
  onPage: (p: number) => void;
}) => {
  if (pages <= 1) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <div
      className="flex items-center justify-between px-3 py-2 border-t
      border-slate-200 dark:border-slate-200 dark:border-slate-200/60 dark:border-slate-800/60"
    >
      <span
        className="text-[11px] font-mono
        text-slate-400 dark:text-slate-500 dark:text-slate-400 dark:text-slate-400 dark:text-slate-500"
      >
        {from}–{to} з {total}
      </span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPage(page - 1)}
          disabled={page <= 1}
          className="px-2 py-1 rounded text-xs transition-colors
            text-slate-400 dark:text-slate-500 hover:text-slate-900 hover:bg-slate-100
            dark:text-slate-400 dark:text-slate-500 dark:text-slate-400 dark:hover:text-slate-900 dark:text-white dark:hover:bg-slate-100 dark:bg-slate-800
            disabled:opacity-40 disabled:cursor-not-allowed"
        >
          ‹
        </button>
        {Array.from({ length: Math.min(pages, 7) }, (_, i) => {
          const p =
            pages <= 7
              ? i + 1
              : page <= 4
                ? i + 1
                : page >= pages - 3
                  ? pages - 6 + i
                  : page - 3 + i;
          return (
            <button
              key={p}
              onClick={() => onPage(p)}
              className={cn(
                "w-6 h-6 rounded text-xs font-mono transition-colors",
                p === page
                  ? "bg-blue-600 text-slate-900 dark:text-white"
                  : "text-slate-400 dark:text-slate-500 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-400 dark:text-slate-500 dark:text-slate-400 dark:hover:text-slate-900 dark:text-white dark:hover:bg-slate-100 dark:bg-slate-800",
              )}
            >
              {p}
            </button>
          );
        })}
        <button
          onClick={() => onPage(page + 1)}
          disabled={page >= pages}
          className="px-2 py-1 rounded text-xs transition-colors
            text-slate-400 dark:text-slate-500 hover:text-slate-900 hover:bg-slate-100
            dark:text-slate-400 dark:text-slate-500 dark:text-slate-400 dark:hover:text-slate-900 dark:text-white dark:hover:bg-slate-100 dark:bg-slate-800
            disabled:opacity-40 disabled:cursor-not-allowed"
        >
          ›
        </button>
      </div>
    </div>
  );
};
