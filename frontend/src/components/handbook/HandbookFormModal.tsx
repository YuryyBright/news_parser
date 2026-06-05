// src/components/handbook/HandbookFormModal.tsx
/**
 * HandbookFormModal — модальна обгортка для форм довідника.
 * Рендерить CountryForm | OrgUnitForm | PersonForm залежно від entity.
 */
import { useEffect, useRef } from "react";
import { X, Globe2, Building2, Users } from "lucide-react";
import { CountryForm } from "./CountryForm";
import { OrgUnitForm } from "./OrgUnitForm";
import { PersonForm } from "./PersonForm";

type EntityType = "country" | "org_unit" | "person";

interface Props {
  entity: EntityType | null;
  data?: Record<string, unknown> | null;
  onClose: () => void;
}

const ENTITY_CONFIG: Record<
  EntityType,
  { label: string; editLabel: string; icon: typeof Globe2; iconColor: string }
> = {
  country: {
    label: "Нова країна",
    editLabel: "Редагувати країну",
    icon: Globe2,
    iconColor: "bg-emerald-500/15 border-emerald-500/25 text-emerald-400",
  },
  org_unit: {
    label: "Новий підрозділ",
    editLabel: "Редагувати підрозділ",
    icon: Building2,
    iconColor: "bg-blue-500/15 border-blue-500/25 text-blue-400",
  },
  person: {
    label: "Нова персона",
    editLabel: "Редагувати персону",
    icon: Users,
    iconColor: "bg-violet-500/15 border-violet-500/25 text-violet-400",
  },
};

export const HandbookFormModal = ({ entity, data, onClose }: Props) => {
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  if (!entity) return null;

  const cfg = ENTITY_CONFIG[entity];
  const Icon = cfg.icon;
  const isEdit = !!data?.id;

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 bg-black/20 dark:bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
      onMouseDown={(e) => {
        if (e.target === overlayRef.current) onClose();
      }}
    >
      <div className="w-full max-w-xl bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-800 flex-shrink-0">
          <div className="flex items-center gap-2.5">
            <div
              className={`w-7 h-7 rounded-lg border flex items-center justify-center ${cfg.iconColor}`}
            >
              <Icon className="w-4 h-4" />
            </div>
            <h2 className="text-sm font-semibold text-slate-900 dark:text-white">
              {isEdit ? cfg.editLabel : cfg.label}
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
        <div className="flex-1 overflow-y-auto p-4">
          {entity === "country" && (
            <CountryForm data={data} onSuccess={onClose} />
          )}
          {entity === "org_unit" && (
            <OrgUnitForm data={data} onSuccess={onClose} />
          )}
          {entity === "person" && (
            <PersonForm data={data} onSuccess={onClose} />
          )}
        </div>
      </div>
    </div>
  );
};
