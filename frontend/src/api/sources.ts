// src/api/sources.ts
import { client } from "./client";
import type {
  Source,
  CreateSourcePayload,
  TaskListResponse,
  Task,
  TriggerResponse,
} from "./types";

export const sourcesApi = {
  list: async (activeOnly = true): Promise<Source[]> => {
    const { data } = await client.get("/sources/", {
      params: { active_only: activeOnly },
    });
    return data;
  },

  create: async (payload: CreateSourcePayload): Promise<Source> => {
    const { data } = await client.post("/sources/", payload);
    return data;
  },

  deactivate: async (id: string): Promise<void> => {
    await client.delete(`/sources/${id}`);
  },

  trigger: async (id: string): Promise<TriggerResponse> => {
    const { data } = await client.post(`/sources/${id}/trigger`);
    return data;
  },

  listTasks: async (params?: {
    task_name?: string;
    status?: string;
    limit?: number;
  }): Promise<TaskListResponse> => {
    const { data } = await client.get("/sources/tasks/", { params });
    return data;
  },

  getTask: async (taskId: string): Promise<Task> => {
    const { data } = await client.get(`/sources/tasks/${taskId}`);
    return data;
  },

  cancelTask: async (
    taskId: string,
  ): Promise<{ task_id: string; status: string }> => {
    const { data } = await client.delete(`/sources/tasks/${taskId}`);
    return data;
  },
};
