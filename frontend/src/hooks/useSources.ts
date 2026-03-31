// src/hooks/useSources.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { sourcesApi } from "../api";
import type { CreateSourcePayload } from "../api/types";

export const useSources = (activeOnly = true) =>
  useQuery({
    queryKey: ["sources", activeOnly],
    queryFn: () => sourcesApi.list(activeOnly),
    staleTime: 2 * 60_000,
  });

export const useCreateSource = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateSourcePayload) => sourcesApi.create(payload),
    onSuccess: (src) => {
      toast.success(`Джерело "${src.name}" додано`);
      qc.invalidateQueries({ queryKey: ["sources"] });
    },
    onError: (err: any) => {
      if (err?.response?.status === 409) toast.error("Це джерело вже існує");
    },
  });
};

export const useDeactivateSource = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => sourcesApi.deactivate(id),
    onSuccess: () => {
      toast.success("Джерело деактивовано");
      qc.invalidateQueries({ queryKey: ["sources"] });
    },
  });
};

export const useTriggerSource = () =>
  useMutation({
    mutationFn: (id: string) => sourcesApi.trigger(id),
    onSuccess: (res) =>
      toast.success(`Задачу поставлено в чергу: ${res.task_id}`),
  });

export const useTasks = (params?: {
  task_name?: string;
  status?: string;
  limit?: number;
}) =>
  useQuery({
    queryKey: ["tasks", params],
    queryFn: () => sourcesApi.listTasks(params),
    refetchInterval: 10_000, // авто-оновлення кожні 10 сек
  });

export const useCancelTask = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => sourcesApi.cancelTask(taskId),
    onSuccess: () => {
      toast.success("Задачу скасовано");
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
    onError: (err: any) => {
      if (err?.response?.status === 409)
        toast.error("Задачу вже не можна скасувати");
    },
  });
};
