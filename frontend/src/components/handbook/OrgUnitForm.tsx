// src/components/handbook/OrgUnitForm.tsx
/**
 * OrgUnitForm — форма створення/редагування підрозділу.
 * Поля: назва, коротка назва, тип, батьківський підрозділ,
 *       опис, правова основа, дати дії, ресурси, статус.
 */
import { useState } from "react";
import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query";
import { handbookApi } from "../../api/handbook";
import type { OrgUnit, ResourceLink } from "../../api/handbook";
import { useHandbookStore } from "../../store/useHandbookStore";
import {
  Field,
  Input,
  Textarea,
  Select,
  Toggle,
  DateRangePicker,
  SectionDivider,
  SubmitButton,
  inputCls,
} from "./ui";
import { ResourcesEditor } from "./ContactsEditor";

// ── Constants ─────────────────────────────────────────────────────────────────

const UNIT_TYPES = [
  { value: "ministry", label: "Міністерство" },
  { value: "department", label: "Департамент" },
  { value: "division", label: "Відділ" },
  { value: "sector", label: "Сектор" },
  { value: "post", label: "Посада" },
  { value: "agency", label: "Агентство" },
  { value: "service", label: "Служба" },
  { value: "command", label: "Командування" },
  { value: "committee", label: "Комітет" },
  { value: "directorate", label: "Управління" },
];

function flattenOrgUnits(
  units: OrgUnit[],
  depth = 0,
  excludeId?: string,
): { value: string; label: string }[] {
  const result: { value: string; label: string }[] = [];
  for (const u of units) {
    if (u.id === excludeId) continue;
    result.push({
      value: u.id,
      label: "\u3000".repeat(depth) + (u.short_name || u.name),
    });
    if (u.children?.length) {
      result.push(...flattenOrgUnits(u.children, depth + 1, excludeId));
    }
  }
  return result;
}

// ── Component ─────────────────────────────────────────────────────────────────

interface Props {
  data?: Record<string, unknown> | null;
  onSuccess: () => void;
}

export const OrgUnitForm = ({ data, onSuccess }: Props) => {
  const qc = useQueryClient();
  const { activeCountryId } = useHandbookStore();
  const isEdit = !!data?.id;
  // Prefer data.country_id (edit mode), fall back to store's activeCountryId (create mode)
  const countryId = (data?.country_id as string) || activeCountryId || "";

  const [name, setName] = useState((data?.name as string) ?? "");
  const [shortName, setShortName] = useState(
    (data?.short_name as string) ?? "",
  );
  const [unitType, setUnitType] = useState(
    (data?.unit_type as string) ?? "department",
  );
  const [parentId, setParentId] = useState((data?.parent_id as string) ?? "");
  const [sortOrder, setSortOrder] = useState(
    String((data?.sort_order as number) ?? 0),
  );
  const [leaderId, setLeaderId] = useState((data?.leader_id as string) ?? "");
  const [leaderTitle, setLeaderTitle] = useState(
    (data?.leader_title as string) ?? "Керівник",
  );
  const [description, setDescription] = useState(
    (data?.description as string) ?? "",
  );
  const [legalBasis, setLegalBasis] = useState(
    (data?.legal_basis as string) ?? "",
  );
  const [isActive, setIsActive] = useState(
    (data?.is_active as boolean) ?? true,
  );
  const [validFrom, setValidFrom] = useState(
    data?.valid_from ? (data.valid_from as string).slice(0, 10) : "",
  );
  const [validTo, setValidTo] = useState(
    data?.valid_to ? (data.valid_to as string).slice(0, 10) : "",
  );
  const [resources, setResources] = useState<ResourceLink[]>(
    (data?.resources as ResourceLink[]) ?? [],
  );
  const { data: countryDetail } = useQuery({
    queryKey: ["handbook-country", countryId],
    // Припускаю, що getCountry повертає об'єкт з полем org_units
    queryFn: () => handbookApi.getCountry(countryId),
    enabled: !!countryId,
  });
  const parentOptions = countryDetail?.org_units
    ? flattenOrgUnits(countryDetail.org_units, 0, data?.id as string)
    : [];
  // Load country detail to build parent selector
  const { data: persons } = useQuery({
    queryKey: ["handbook-persons", countryId],
    queryFn: () => handbookApi.listPersons(countryId),
    enabled: !!countryId,
  });

  const personOptions = persons
    ? persons.map((p: any) => ({
        value: p.id,
        label: `${p.last_name} ${p.first_name} ${p.patronymic || ""}`.trim(),
      }))
    : [];

  const { mutate, isPending, isSuccess, error } = useMutation({
    mutationFn: () => {
      const payload = {
        name: name.trim(),
        short_name: shortName.trim() || undefined,
        unit_type: unitType,
        parent_id: parentId || undefined,
        country_id: countryId,
        sort_order: Number(sortOrder) || 0,
        leader_id: leaderId || undefined,
        leader_title: leaderTitle.trim() || undefined,
        description: description.trim() || undefined,
        legal_basis: legalBasis.trim() || undefined,
        is_active: isActive,
        valid_from: validFrom ? new Date(validFrom).toISOString() : undefined,
        valid_to: validTo ? new Date(validTo).toISOString() : undefined,
        resources,
      };
      if (isEdit) return handbookApi.updateOrgUnit(data!.id as string, payload);
      return handbookApi.createOrgUnit(payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["handbook-country", countryId] });
      qc.invalidateQueries({ queryKey: ["handbook-org-tree", countryId] });
      setTimeout(onSuccess, 800);
    },
  });

  return (
    <div className="space-y-4">
      {/* Name block */}
      <div className="grid grid-cols-3 gap-3">
        <div className="col-span-2">
          <Field label="Повна назва" required>
            <Input
              value={name}
              onChange={setName}
              placeholder="Департамент стратегічного планування"
              autoCapitalized
            />
          </Field>
        </div>
        <Field label="Скорочення">
          <Input value={shortName} onChange={setShortName} placeholder="ДСП" />
        </Field>
      </div>

      {/* Type + Sort order */}
      <div className="grid grid-cols-2 gap-3">
        <Field label="Тип" required>
          <Select
            value={unitType}
            onChange={setUnitType}
            options={UNIT_TYPES}
            placeholder="— оберіть тип —"
          />
        </Field>
        <Field label="Порядок сортування">
          <input
            type="number"
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value)}
            min={0}
            className={inputCls}
          />
        </Field>
      </div>

      {/* Parent */}
      <Field label="Вищий підрозділ">
        <Select
          value={parentId}
          onChange={setParentId}
          options={parentOptions}
          placeholder="— верхній рівень —"
        />
      </Field>

      <SectionDivider label="Опис" />
      {/* === БЛОК КЕРІВНИЦТВА === */}
      <SectionDivider label="Керівництво" />

      <div className="grid grid-cols-2 gap-3">
        <Field label="Особа керівника">
          <Select
            value={leaderId}
            onChange={setLeaderId}
            options={personOptions}
            placeholder="— вакантно —"
          />
        </Field>
        <Field label="Назва посади">
          <Input
            value={leaderTitle}
            onChange={setLeaderTitle}
            placeholder="Керівник, Директор, Міністр..."
          />
        </Field>
      </div>
      {/* ======================== */}
      <Field label="Опис">
        <Textarea
          value={description}
          onChange={setDescription}
          placeholder="Короткий опис підрозділу…"
          rows={3}
        />
      </Field>

      <Field label="Правова основа">
        <Textarea
          value={legalBasis}
          onChange={setLegalBasis}
          placeholder="Постанова КМУ №… від …"
          rows={2}
        />
      </Field>

      <SectionDivider label="Терміни дії" />

      <DateRangePicker
        startDate={validFrom}
        endDate={validTo}
        onStartChange={setValidFrom}
        onEndChange={setValidTo}
        labelStart="Діє з"
        labelEnd="Діє по"
      />

      <SectionDivider label="Ресурси" />
      <ResourcesEditor resources={resources} onChange={setResources} />

      <div className="pt-1">
        <Toggle
          label="Активний підрозділ"
          value={isActive}
          onChange={setIsActive}
        />
      </div>

      <SubmitButton
        isPending={isPending}
        isSuccess={isSuccess}
        error={error as Error | null}
        isEdit={isEdit}
        onSubmit={() => mutate()}
        disabled={!name}
        label="Додати підрозділ"
        editLabel="Зберегти зміни"
      />
    </div>
  );
};
