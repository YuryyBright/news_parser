# presentation/routers/rag_router.py
"""
RAG Pipeline — FastAPI роутер.

Ендпоінти:
  POST /rag/ingest          — інгестація одного .docx файлу
  POST /rag/ingest/batch    — інгестація всієї директорії (рекурсивно)
  POST /rag/generate        — генерація новини за запитом
  GET  /rag/verify          — перевірка якості векторного пошуку
  GET  /rag/stats           — статистика колекції (кількість чанків)

DI: використовує головний Container (src.config.container.get_container).
container_rag.py більше НЕ потрібен і видалений.
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rag", tags=["RAG Pipeline"])


# ── Pydantic схеми ────────────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    file_path: str = Field(..., description="Абсолютний або відносний шлях до .docx файлу")


class BatchIngestRequest(BaseModel):
    directory: str = Field(..., description="Шлях до директорії з .docx файлами (рекурсивно)")


class GenerateRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Запит — тема новини для генерації")
    language: str = Field("uk", description="Мова фільтрації чанків")


class IngestResponse(BaseModel):
    file_path: str
    status: str
    total_chunks: int
    saved_chunks: int
    skipped_chunks: int
    error: str = ""


class BatchIngestResponse(BaseModel):
    total_files: int
    ok_files: int
    failed_files: int
    total_chunks: int


class GenerateResponse(BaseModel):
    news_id: str
    title: str
    body: str
    status: str
    saved_path: str
    context_chunks_used: int
    context_chunks_found: int
    context_score: float


class VerifyItem(BaseModel):
    chunk_id: str
    text_preview: str
    similarity_score: float
    source: str
    language: str
    char_length: int
    passes_filter: bool


class VerifyResponse(BaseModel):
    query: str
    total_in_db: int
    results: list[VerifyItem]
    would_pass_filter: int


class StatsResponse(BaseModel):
    total_chunks: int
    collection: str = "docx_chunks"


# ── Dependency ────────────────────────────────────────────────────────────────

def get_container():
    """
    FastAPI Depends — повертає головний Container singleton.
    Container вже ініціалізований у lifespan (init_container + init_async).
    """
    from src.config.container import get_container as _get
    return _get()


ContainerDep = Annotated[object, Depends(get_container)]


# ── Ендпоінти ─────────────────────────────────────────────────────────────────

@router.post("/ingest", response_model=IngestResponse, summary="Інгестувати один .docx файл")
async def ingest_file(request: IngestRequest, container: ContainerDep):
    """
    Читає .docx файл, розбиває на чанки, зберігає у ChromaDB.
    Ідемпотентний — повторний виклик перезапише чанки того самого файлу.
    """
    result = await container.ingest_single_uc.execute(request.file_path)
    if result.status == "error":
        raise HTTPException(status_code=422, detail=result.error)
    return IngestResponse(
        file_path=result.file_path,
        status=result.status,
        total_chunks=result.total_chunks,
        saved_chunks=result.saved_chunks,
        skipped_chunks=result.skipped_chunks,
        error=result.error,
    )


@router.post("/ingest/batch", response_model=BatchIngestResponse, summary="Інгестувати директорію")
async def ingest_batch(request: BatchIngestRequest, container: ContainerDep):
    """
    Знаходить всі .docx у вказаній директорії (рекурсивно) і інгестує кожен.
    Помилка в одному файлі не зупиняє обробку решти.
    """
    result = await container.ingest_batch_uc.execute_dir(request.directory)
    return BatchIngestResponse(
        total_files=result.total_files,
        ok_files=result.ok_files,
        failed_files=result.failed_files,
        total_chunks=result.total_chunks,
    )


@router.post("/generate", response_model=GenerateResponse, summary="Згенерувати новину")
async def generate_news(request: GenerateRequest, container: ContainerDep):
    from src.application.use_cases.generate_news import GenerateNewsUseCase

    async with container.db_session() as session:
        news_repo = container.generated_news_repo(session)
        uc = GenerateNewsUseCase(
            embedder=container._rag_embedder,
            chunk_repo=container._chunk_repo,
            llm_client=container._llm_client,
            news_repo=news_repo,
            target_language=request.language,  
        )
        result = await uc.execute(query=request.query)  

    news = result.news
    return GenerateResponse(
        news_id=str(news.id),
        title=news.title,
        body=news.body,
        status=news.status.value,
        saved_path=result.saved_path,
        context_chunks_used=result.context_chunks_used,
        context_chunks_found=result.context_chunks_found,
        context_score=news.context_score,
    )

@router.get("/verify", response_model=VerifyResponse, summary="Перевірити якість пошуку")
async def verify_search(
    container: ContainerDep,
    q: str = Query(..., description="Пошуковий запит для верифікації"),
    top: int = Query(10, ge=1, le=50, description="Кількість результатів"),
    lang: str | None = Query(None, description="Фільтр за мовою (напр. 'uk')"),
):
    """
    Інструмент тестування: повертає топ-N результатів БЕЗ фільтрації по threshold.
    Показує similarity_score, текст, джерело — для ручного налаштування порогу.
    """
    result = await container.verify_uc.execute(query=q, top_n=top, language_filter=lang)

    from domain.news_generation.prompts import SIMILARITY_THRESHOLD, MIN_TEXT_LENGTH

    items = [
        VerifyItem(
            chunk_id=r.chunk_id,
            text_preview=r.text[:300],
            similarity_score=round(r.similarity_score, 4),
            source=r.source,
            language=r.language,
            char_length=len(r.text),
            passes_filter=(
                r.similarity_score >= SIMILARITY_THRESHOLD
                and len(r.text) > MIN_TEXT_LENGTH
            ),
        )
        for r in result.results
    ]

    return VerifyResponse(
        query=q,
        total_in_db=result.total_in_db,
        results=items,
        would_pass_filter=result.would_pass_filter,
    )


@router.get("/stats", response_model=StatsResponse, summary="Статистика колекції")
async def get_stats(container: ContainerDep):
    """Повертає кількість чанків у ChromaDB колекції docx_chunks."""
    total = await container.chunk_repo.count()
    return StatsResponse(total_chunks=total)