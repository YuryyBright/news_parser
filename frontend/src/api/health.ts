// src/api/health.ts
import { client } from "./client";
import type { HealthResponse } from "./types";

export const healthApi = {
  check: async (): Promise<HealthResponse> => {
    const { data } = await client.get("/health/");
    return data;
  },
};
