// src/api/feed.ts
import { client } from "./client";
import type { FeedPageResponse, FeedFilter } from "./types";

export const feedApi = {
  get: async (
    userId: string,
    params: { offset: number; limit: number; filter: FeedFilter },
  ): Promise<FeedPageResponse> => {
    const { data } = await client.get(`/feed/${userId}`, { params });
    return data;
  },

  markRead: async (
    userId: string,
    articleId: string,
  ): Promise<{ status: string }> => {
    const { data } = await client.patch(`/feed/${userId}/read/${articleId}`);
    return data;
  },
};
