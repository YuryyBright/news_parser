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

export const articlesApi = {
  list: async (filters: ArticleFilter = {}): Promise<Article[]> => {
    const { data } = await client.get("/articles/", { params: filters });
    return data;
  },

  get: async (id: string): Promise<ArticleDetail> => {
    const { data } = await client.get(`/articles/${id}`);
    return data;
  },

  create: async (payload: CreateArticlePayload): Promise<ArticleDetail> => {
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
