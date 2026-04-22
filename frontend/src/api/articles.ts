// src/api/articles.ts
import { client } from "./client";
import type {
  Article,
  ArticleDetail,
  ArticleFilter,
  CreateArticlePayload,
  UpdateArticlePayload,
  FeedbackPayload,
  FeedbackResponse,
} from "./types";

export interface ArticleListResponse {
  items: Article[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface SearchResponse {
  query: string;
  total: number;
  items: Article[];
}

export interface IngestUrlPayload {
  url: string;
  source_id?: string;
}

export interface IngestUrlResponse {
  status: string;
  task_id: string;
  url: string;
  message: string;
}

export const articlesApi = {
  list: async (filters: ArticleFilter = {}): Promise<ArticleListResponse> => {
    const { data } = await client.get("/articles/", { params: filters });
    // Backwards compat: якщо старий бекенд повертає масив — обгортаємо
    if (Array.isArray(data)) {
      return {
        items: data,
        total: data.length,
        page: 1,
        page_size: data.length,
        pages: 1,
      };
    }
    return data;
  },

  search: async (
    q: string,
    params?: { language?: string; status?: string; limit?: number },
  ): Promise<SearchResponse> => {
    const { data } = await client.get("/articles/search", {
      params: { q, ...params },
    });
    return data;
  },

  ingestUrl: async (payload: IngestUrlPayload): Promise<IngestUrlResponse> => {
    const { data } = await client.post("/articles/ingest-url", payload);
    return data;
  },

  get: async (id: string): Promise<ArticleDetail> => {
    const { data } = await client.get(`/articles/${id}`);
    return data;
  },

  create: async (payload: CreateArticlePayload): Promise<ArticleDetail> => {
    // Додаємо штучну затримку 3 секунди перед створенням статті
    await new Promise((resolve) => setTimeout(resolve, 3000));
    const { data } = await client.post("/articles/", payload);
    return data;
  },

  update: async (
    id: string,
    payload: UpdateArticlePayload,
  ): Promise<ArticleDetail> => {
    const { data } = await client.patch(`/articles/${id}`, payload);
    return data;
  },

  delete: async (id: string): Promise<void> => {
    await client.delete(`/articles/${id}`);
  },

  addTags: async (id: string, tags: string[]): Promise<{ tags: string[] }> => {
    const { data } = await client.post(`/articles/${id}/tags`, { tags });
    return data;
  },

  expire: async (id: string): Promise<void> => {
    await client.post(`/articles/${id}/expire`);
  },

  feedback: async (
    id: string,
    payload: FeedbackPayload,
  ): Promise<FeedbackResponse> => {
    const { data } = await client.post(`/articles/${id}/feedback`, payload);
    return data;
  },
};
