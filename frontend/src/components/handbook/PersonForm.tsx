// src/components/handbook/PersonForm.tsx
/**
 * PersonForm — форма створення/редагування персони.
 * Включає:
 *  - ПІБ з автокапіталізацією
 *  - посада, звання, структура
 *  - дати призначення/звільнення (DateRangePicker)
 *  - завантаження фото (файл або URL)
 *  - біографія
 *  - контакти, ресурси
 *  - статус активності
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
} from "./ui";
import { PhotoUpload } from "./PhotoUpload";
import { ContactsEditor, ResourcesEditor } from "./ContactsEditor";

// ── Flatten org tree for select ───────────────────────────────────────────────

function flattenOrgUnits(
  units: OrgUnit[],
  depth = 0,
): { value: string; label: string }[] {
  const result: { value: string; label: string }[] = [];
  for (const u of units) {
    result.push({
      value: u.id,
      label: "\u3000".repeat(depth) + (u.short_name || u.name),
    });
    if (u.children?.length) {
      result.push(...flattenOrgUnits(u.children, depth + 1));
    }
  }
  return result;
}

// ── Component ─────────────────────────────────────────────────────────────────

interface Props {
  data?: Record<string, unknown> | null;
  onSuccess: () => void;
}

export const PersonForm = ({ data, onSuccess }: Props) => {
  const qc = useQueryClient();
  const isEdit = !!data?.id;
  // country_id comes from data (edit) OR from the store (create from country/org_unit context)
  const { activeCountryId, activeOrgUnitId } = useHandbookStore();
  const countryId = (data?.country_id as string) || activeCountryId || "";

  // Name
  const [lastName, setLastName] = useState((data?.last_name as string) ?? "");
  const [firstName, setFirstName] = useState(
    (data?.first_name as string) ?? "",
  );
  const [patronymic, setPatronymic] = useState(
    (data?.patronymic as string) ?? "",
  );

  // Professional
  const [rank, setRank] = useState((data?.rank as string) ?? "");
  const [positionTitle, setPositionTitle] = useState(
    (data?.position_title as string) ?? "",
  );
  // Pre-fill org_unit_id from: explicit data prop → active org unit in store
  const [orgUnitId, setOrgUnitId] = useState(
    (data?.org_unit_id as string) ?? activeOrgUnitId ?? "",
  );

  // Dates
  const [dateAppointed, setDateAppointed] = useState(
    data?.date_appointed ? (data.date_appointed as string).slice(0, 10) : "",
  );
  const [dateDismissed, setDateDismissed] = useState(
    data?.date_dismissed ? (data.date_dismissed as string).slice(0, 10) : "",
  );

  // Photo
  const [photoUrl, setPhotoUrl] = useState((data?.photo_url as string) ?? "");

  // Bio
  const [bio, setBio] = useState((data?.bio as string) ?? "");

  // Contacts & Resources
  const [contacts, setContacts] = useState<Record<string, string>>(
    (data?.contacts as Record<string, string>) ?? {},
  );
  const [resources, setResources] = useState<ResourceLink[]>(
    (data?.resources as ResourceLink[]) ?? [],
  );

  // Status
  const [isActive, setIsActive] = useState(
    (data?.is_active as boolean) ?? true,
  );

  // Org unit tree for selector
  const { data: countryDetail } = useQuery({
    queryKey: ["handbook-country", countryId],
    // Припускаю, що getCountry повертає об'єкт з полем org_units
    queryFn: () => handbookApi.getCountry(countryId),
    enabled: !!countryId,
  });

  const unitOptions = countryDetail?.org_units
    ? flattenOrgUnits(countryDetail.org_units)
    : [];

  const { mutate, isPending, isSuccess, error } = useMutation({
    mutationFn: () => {
      const payload = {
        last_name: lastName.trim(),
        first_name: firstName.trim(),
        patronymic: patronymic.trim() || undefined,
        rank: rank.trim() || undefined,
        position_title: positionTitle.trim() || undefined,
        photo_url: photoUrl || undefined,
        bio: bio.trim() || undefined,
        org_unit_id: orgUnitId || undefined,
        country_id: countryId,
        is_active: isActive,
        date_appointed: dateAppointed
          ? new Date(dateAppointed).toISOString()
          : undefined,
        date_dismissed: dateDismissed
          ? new Date(dateDismissed).toISOString()
          : undefined,
        contacts,
        resources,
      };
      if (isEdit) return handbookApi.updatePerson(data!.id as string, payload);
      return handbookApi.createPerson(payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["handbook-country", countryId] });
      qc.invalidateQueries({ queryKey: ["handbook-person", data?.id] });
      setTimeout(onSuccess, 800);
    },
  });

  const fullPreviewName = [lastName, firstName, patronymic]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="space-y-4">
      {/* Name block */}
      <div className="grid grid-cols-3 gap-3">
        <Field label="Прізвище" required>
          <Input
            value={lastName}
            onChange={setLastName}
            placeholder="Іванов"
            autoCapitalized
          />
        </Field>
        <Field label="Ім'я" required>
          <Input
            value={firstName}
            onChange={setFirstName}
            placeholder="Іван"
            autoCapitalized
          />
        </Field>
        <Field label="По батькові">
          <Input
            value={patronymic}
            onChange={setPatronymic}
            placeholder="Іванович"
            autoCapitalized
          />
        </Field>
      </div>

      {/* Preview name */}
      {fullPreviewName && (
        <div className="px-3 py-2 rounded-lg bg-slate-100/60 dark:bg-slate-100 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800">
          <p className="text-xs text-slate-400 dark:text-slate-500">
            Повне ім'я:{" "}
            <span className="text-slate-900 dark:text-white font-medium">
              {fullPreviewName}
            </span>
          </p>
        </div>
      )}

      <SectionDivider label="Посада" />

      <div className="grid grid-cols-2 gap-3">
        <Field label="Посада">
          <Input
            value={positionTitle}
            onChange={setPositionTitle}
            placeholder="Начальник відділу"
            autoCapitalized
          />
        </Field>
        <Field label="Звання / ранг">
          <Input value={rank} onChange={setRank} placeholder="генерал-майор" />
        </Field>
      </div>

      <Field label="Підрозділ">
        <Select
          value={orgUnitId}
          onChange={setOrgUnitId}
          options={unitOptions}
          placeholder="— не вказано —"
        />
      </Field>

      <SectionDivider label="Терміни служби" />

      <DateRangePicker
        startDate={dateAppointed}
        endDate={dateDismissed}
        onStartChange={setDateAppointed}
        onEndChange={setDateDismissed}
        labelStart="Дата призначення"
        labelEnd="Дата звільнення"
      />

      <SectionDivider label="Фото" />

      <PhotoUpload
        value={photoUrl}
        onChange={setPhotoUrl}
        name={fullPreviewName || "Фото"}
      />

      <SectionDivider label="Біографія" />

      <Field label="Довідка">
        <Textarea
          value={bio}
          onChange={setBio}
          placeholder="Коротка довідка про особу…"
          rows={4}
        />
      </Field>

      <SectionDivider label="Контакти" />
      <ContactsEditor contacts={contacts} onChange={setContacts} />

      <SectionDivider label="Ресурси" />
      <ResourcesEditor resources={resources} onChange={setResources} />

      <div className="pt-1">
        <Toggle label="Активний" value={isActive} onChange={setIsActive} />
      </div>

      <SubmitButton
        isPending={isPending}
        isSuccess={isSuccess}
        error={error as Error | null}
        isEdit={isEdit}
        onSubmit={() => mutate()}
        disabled={!lastName || !firstName}
        label="Додати персону"
        editLabel="Зберегти зміни"
      />
    </div>
  );
};
