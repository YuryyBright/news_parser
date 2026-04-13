// src/api/types.ts
// Типи, похідні від бекенд Pydantic схем (article.py, feed.py, source.py, task.py)
export const UserID = "00000000-0000-0000-0000-000000000001";

export type FeedFilter = "all" | "unread" | "read";

export type ArticleStatus =
  | "new"
  | "accepted"
  | "rejected"
  | "expired"
  | "processing";
export type FeedItemStatus = "unread" | "read" | "skipped";
export type TaskStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "failed"
  | "cancelled";
export type SourceType = "rss" | "web" | "api" | "telegram";

// ── Articles ──────────────────────────────────────────────────────────────────

export interface Article {
  id: string;
  article_id: string;
  title: string;
  url: string;
  language: string;
  status: ArticleStatus;
  relevance_score: number;
  published_at: string | null;
  created_at: string;
  tags: string[];
  original_title: string | null;
  original_body: string | null;
  body: string | null;
}

export interface ArticleDetail extends Article {
  body: string;
  source_id: string | null;
}
export type SortBy = "created_at" | "published_at" | "relevance_score";
export type SortDir = "asc" | "desc";
export interface ArticleFilter {
  status?: ArticleStatus;
  min_score?: number;
  language?: string;
  tag?: string;
  date_from?: string; // Add this
  date_to?: string; // Add this
  sort_by?: SortBy;
  sort_dir?: SortDir;
  page?: number;
  page_size?: number;
}

export interface CreateArticlePayload {
  source_id: string;
  title: string;
  body: string;
  url: string;
  language?: string;
  published_at?: string;
}

export interface UpdateArticlePayload {
  title?: string;
  body?: string;
  language?: string;
}

export interface FeedbackPayload {
  user_id: string;
  liked: boolean;
}

export interface FeedbackResponse {
  status: string;
  liked: boolean;
}

/** Статистика вподобань юзера */
export interface PreferencesStats {
  liked: number;
  disliked: number;
  expired: number;
}

// ── Feed ──────────────────────────────────────────────────────────────────────

export interface FeedArticle {
  article_id: string;
  rank: number;
  score: number;
  language: string;
  status: FeedItemStatus;
  title: string;
  url: string;
  relevance_score: number;
  published_at: string | null;
  original_title: string | null;
  original_body: string | null;
}
export interface FeedPageResponse {
  snapshot_id: string;
  generated_at: string;
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
  items: FeedArticle[];
}

export type FeedResponse = FeedPageResponse;
// ── Sources ───────────────────────────────────────────────────────────────────

export interface Source {
  id: string;
  name: string;
  url: string;
  source_type: SourceType;
  fetch_interval_seconds: number;
  is_active: boolean;
  created_at: string;
}

export interface CreateSourcePayload {
  name: string;
  url: string;
  source_type: SourceType;
  fetch_interval_seconds: number;
}

// ── Tasks ─────────────────────────────────────────────────────────────────────

export interface Task {
  task_id: string;
  task_name: string;
  status: TaskStatus;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  kwargs: Record<string, unknown>;
  error: string | null;
  result: unknown;
}

export interface TaskListResponse {
  total: number;
  tasks: Task[];
}

export interface TriggerResponse {
  task_id: string;
  task_name: string;
  status: string;
  message: string;
}

// ── Health ────────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  articles: Record<string, number>;
}
