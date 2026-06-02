# presentation/api/schemas/generated_news.py
from __future__ import annotations
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel
from typing import Optional


class GeneratedNewsResponse(BaseModel):
    id: UUID
    title: str
    body: str
    query: str
    source_chunks: list[str]

    status: str
    language: str

    created_at: datetime

    model_used: str
    context_score: float

    model_config = {
        "from_attributes": True,
    }


class GeneratedNewsListResponse(BaseModel):
    items: list[GeneratedNewsResponse]
    total: int
    page: int
    page_size: int
    pages: int