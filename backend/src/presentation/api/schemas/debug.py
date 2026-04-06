# ═══════════════════════════════════════════════════════════════════════════════
# Request / Response schemas
# ═══════════════════════════════════════════════════════════════════════════════
from __future__ import annotations

import contextlib
import logging
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

class ScoreRequest(BaseModel):
    text: str = Field(..., min_length=10, description="Текст для скорингу")
    language: str = Field(default="uk", description="ISO 639-1 код мови")
    title: str = Field(default="", description="Заголовок (опційно)")


class CompareRequest(BaseModel):
    text_a: str = Field(..., min_length=5)
    text_b: str = Field(..., min_length=5)


class GeoAnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=5)
    language: str = Field(..., description="ISO 639-1 код мови: uk, hu, sk, ro, en")


class ManualAddRequest(BaseModel):
    text: str = Field(..., min_length=10, description="Текст статті для збереження у профіль")
    article_id: UUID | None = Field(default=None, description="UUID статті (генерується якщо не вказано)")
    score: float = Field(default=1.0, ge=0.0, le=1.0, description="Relevance score")
    tags: list[str] = Field(default_factory=list, description="Список тегів")


class FeedbackTraceRequest(BaseModel):
    article_id: UUID = Field(..., description="UUID статті що отримала feedback")
    liked: bool = Field(..., description="true=like, false=dislike")
