# infrastructure/config/settings.py
from __future__ import annotations
from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DATABASE__", extra="ignore")
    url: str = "sqlite+aiosqlite:///./data/news_parser.db"


class ChromaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CHROMA__", extra="ignore")
    host: str = "localhost"
    port: int = 8000
    persist_dir: str = "./data/chroma"
    collection_articles: str = "article_embeddings"
    collection_criteria: str = "criteria_embeddings"


class EmbeddingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EMBEDDING__", extra="ignore")
    model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    dimensions: int = 384
    batch_size: int = 64
    normalize: bool = True


class FilterWeightsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FILTERING__WEIGHTS__", extra="ignore")
    embedding: float = 0.60
    keyword: float   = 0.25
    feedback: float  = 0.15

    @field_validator("feedback", mode="after")
    @classmethod
    def weights_sum_to_one(cls, v, info):
        vals = info.data
        total = vals.get("embedding", 0) + vals.get("keyword", 0) + v
        if abs(total - 1.0) > 1e-4:
            raise ValueError(f"Weights must sum to 1.0, got {total}")
        return v


class FeedbackBoostSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FILTERING__FEEDBACK__", extra="ignore")
    min_count_for_boost: int   = 10
    boost_embedding: float     = 0.55
    boost_keyword: float       = 0.20
    boost_feedback: float      = 0.25


class FilteringSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FILTERING__", extra="ignore")
    default_threshold: float        = 0.40
    cold_start_phrases_count: int   = 8
    weights: FilterWeightsSettings  = Field(default_factory=FilterWeightsSettings)
    feedback: FeedbackBoostSettings = Field(default_factory=FeedbackBoostSettings)


class DeduplicationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEDUP__", extra="ignore")
    minhash_threshold: float = 0.85
    minhash_num_perm: int    = 128


class FeedSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FEED__", extra="ignore")
    max_items: int               = 50
    recency_decay_hours: float   = 24.0
    snapshot_ttl_minutes: int    = 30


class TaskQueueSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TASK_QUEUE__", extra="ignore")
    backend: str = "background"          # "celery" | "background"
    celery_broker: str          = "redis://localhost:6379/0"
    celery_result_backend: str  = "redis://localhost:6379/1"

    @property
    def use_celery(self) -> bool:
        return self.backend == "celery"


class WorkersSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WORKERS__", extra="ignore")
    fetch_interval_seconds: int  = 300
    max_retries: int             = 3
    pipeline_concurrency: int    = 4


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AUTH__", extra="ignore")
    secret_key: str                    = "change-me"
    algorithm: str                     = "HS256"
    access_token_expire_minutes: int   = 60
    refresh_token_expire_days: int     = 30


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM__", extra="ignore")
    provider: str   = "anthropic"
    api_key: str    = ""
    model: str      = "claude-haiku-4-5-20251001"
    max_tokens: int = 512


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str   = "development"
    app_debug: bool = False

    database:      DatabaseSettings      = Field(default_factory=DatabaseSettings)
    chroma:        ChromaSettings        = Field(default_factory=ChromaSettings)
    embedding:     EmbeddingSettings     = Field(default_factory=EmbeddingSettings)
    filtering:     FilteringSettings     = Field(default_factory=FilteringSettings)
    dedup:         DeduplicationSettings = Field(default_factory=DeduplicationSettings)
    feed:          FeedSettings          = Field(default_factory=FeedSettings)
    task_queue:    TaskQueueSettings     = Field(default_factory=TaskQueueSettings)
    workers:       WorkersSettings       = Field(default_factory=WorkersSettings)
    auth:          AuthSettings          = Field(default_factory=AuthSettings)
    llm:           LLMSettings          = Field(default_factory=LLMSettings)

    # Shortcut — єдиний рядок для всього коду
    @property
    def vector_dim(self) -> int:
        return self.embedding.dimensions

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()