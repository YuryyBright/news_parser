// src/components/handbook/CountryForm.tsx
/**
 * CountryForm — форма створення/редагування країни.
 */
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { handbookApi } from "../../api/handbook";
import type { ResourceLink } from "../../api/handbook";
import {
  Field,
  Input,
  Textarea,
  Toggle,
  SectionDivider,
  SubmitButton,
  inputCls,
} from "./ui";
import { ResourcesEditor } from "./ContactsEditor";

interface Props {
  data?: Record<string, unknown> | null;
  onSuccess: () => void;
}

export const CountryForm = ({ data, onSuccess }: Props) => {
  const qc = useQueryClient();
  const isEdit = !!data?.id;

  const [code, setCode] = useState((data?.code as string) ?? "");
  const [nameUk, setNameUk] = useState((data?.name_uk as string) ?? "");
  const [nameEn, setNameEn] = useState((data?.name_en as string) ?? "");
  const [flagEmoji, setFlagEmoji] = useState(
    (data?.flag_emoji as string) ?? "",
  );
  const [capital, setCapital] = useState((data?.capital as string) ?? "");
  const [description, setDescription] = useState(
    (data?.description as string) ?? "",
  );
  const [isActive, setIsActive] = useState(
    (data?.is_active as boolean) ?? true,
  );
  const [resources, setResources] = useState<ResourceLink[]>(
    (data?.resources as ResourceLink[]) ?? [],
  );

  const { mutate, isPending, isSuccess, error } = useMutation({
    mutationFn: () => {
      const payload = {
        code: code.trim().toUpperCase(),
        name_uk: nameUk.trim(),
        name_en: nameEn.trim(),
        flag_emoji: flagEmoji.trim() || undefined,
        capital: capital.trim() || undefined,
        description: description.trim() || undefined,
        is_active: isActive,
        resources,
      };
      if (isEdit) return handbookApi.updateCountry(data!.id as string, payload);
      return handbookApi.createCountry(payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["handbook-countries"] });
      setTimeout(onSuccess, 800);
    },
  });

  return (
    <div className="space-y-4">
      {/* Code + flag */}
      <div className="grid grid-cols-3 gap-3">
        <Field label="Код (ISO)" required>
          <input
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder="UA"
            maxLength={4}
            disabled={isEdit}
            className={inputCls}
          />
        </Field>
        <div className="col-span-2">
          <Field label="Прапор (emoji)">
            <input
              type="text"
              value={flagEmoji}
              onChange={(e) => setFlagEmoji(e.target.value)}
              placeholder="🇺🇦"
              className={inputCls}
            />
          </Field>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Назва (укр)" required>
          <Input
            value={nameUk}
            onChange={setNameUk}
            placeholder="Україна"
            autoCapitalized
          />
        </Field>
        <Field label="Назва (eng)" required>
          <Input value={nameEn} onChange={setNameEn} placeholder="Ukraine" />
        </Field>
      </div>

      <Field label="Столиця">
        <Input
          value={capital}
          onChange={setCapital}
          placeholder="Київ"
          autoCapitalized
        />
      </Field>

      <Field label="Опис">
        <Textarea
          value={description}
          onChange={setDescription}
          placeholder="Короткий опис країни…"
          rows={3}
        />
      </Field>

      <SectionDivider label="Ресурси" />
      <ResourcesEditor resources={resources} onChange={setResources} />

      <div className="pt-1">
        <Toggle label="Активна" value={isActive} onChange={setIsActive} />
      </div>

      <SubmitButton
        isPending={isPending}
        isSuccess={isSuccess}
        error={error as Error | null}
        isEdit={isEdit}
        onSubmit={() => mutate()}
        disabled={!code || !nameUk || !nameEn}
        label="Додати країну"
        editLabel="Зберегти зміни"
      />
    </div>
  );
};
