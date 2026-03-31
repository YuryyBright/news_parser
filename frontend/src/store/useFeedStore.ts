// src/store/useFeedStore.ts
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface FeedStore {
  // В реальному проді — береться з auth, поки хардкод
  userId: string;
  readIds: string[]; // persist як масив (Set не серіалізується)
  feedFilter: "all" | "unread" | "read";
  setFeedFilter: (f: "all" | "unread" | "read") => void;
  markRead: (articleId: string) => void;
  isRead: (articleId: string) => boolean;
}

export const useFeedStore = create<FeedStore>()(
  persist(
    (set, get) => ({
      userId:
        import.meta.env.VITE_DEFAULT_USER_ID ??
        "00000000-0000-0000-0000-000000000001",
      readIds: [],
      feedFilter: "all",

      setFeedFilter: (f) => set({ feedFilter: f }),

      markRead: (articleId) =>
        set((s) => ({
          readIds: s.readIds.includes(articleId)
            ? s.readIds
            : [...s.readIds, articleId],
        })),

      isRead: (articleId) => get().readIds.includes(articleId),
    }),
    {
      name: "feed-store",
      partialize: (s) => ({ readIds: s.readIds, userId: s.userId }),
    },
  ),
);
