// src/api/generatedNews.ts
import { client } from "./client";

export interface GeneratedNewsItem {
  id: string;
  title: string;

  body: string;
  query: string;

  source_chunks: string[];
  source_url: string | null;
  status: string;
  language: string;

  created_at: string;

  model_used: string;
  context_score: number;
}

export interface GeneratedNewsListResponse {
  items: GeneratedNewsItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface GeneratedNewsFilter {
  language?: string;
  status?: string;
  q?: string;
  date_from?: string;
  date_to?: string;
  sort_dir?: "asc" | "desc";
  page?: number;
  page_size?: number;
}

export const generatedNewsApi = {
  list: async (
    filters: GeneratedNewsFilter = {},
  ): Promise<GeneratedNewsListResponse> => {
    const { data } = await client.get("/generated-news/", { params: filters });
    return data;
  },

  get: async (id: string): Promise<GeneratedNewsItem> => {
    const { data } = await client.get(`/generated-news/${id}`);
    return data;
  },

  publish: async (id: string): Promise<GeneratedNewsItem> => {
    const { data } = await client.patch(`/generated-news/${id}/publish`);
    return data;
  },
};
