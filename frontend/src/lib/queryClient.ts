// src/lib/queryClient.ts
import { QueryClient } from "@tanstack/react-query";

// Переконайтеся, що тут лише ОДИН експорт queryClient
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
});
