// src/api/feed.ts
import { client } from "./client";
import type { FeedResponse } from "./types";

export const feedApi = {
  get: async (userId: string): Promise<FeedResponse> => {
    const { data } = await client.get(`/feed/${userId}`);
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
