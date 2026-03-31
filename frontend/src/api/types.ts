// src/api/types.ts
// Типи, похідні від бекенд Pydantic схем (article.py, feed.py, source.py, task.py)

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
  title: string;
  url: string;
  language: string;
  status: ArticleStatus;
  relevance_score: number;
  published_at: string | null;
  created_at: string;
  tags: string[];
}

export interface ArticleDetail extends Article {
  body: string;
  source_id: string | null;
}

export interface ArticleFilter {
  status?: ArticleStatus | null;
  min_score?: number;
  language?: string | null;
  limit?: number;
  offset?: number;
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

// ── Feed ──────────────────────────────────────────────────────────────────────

export interface FeedArticle {
  article_id: string;
  rank: number;
  score: number;
  status: FeedItemStatus;
  title: string;
  url: string;
  relevance_score: number;
  published_at: string | null;
}

export interface FeedResponse {
  snapshot_id: string;
  generated_at: string;
  items: FeedArticle[];
}

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
