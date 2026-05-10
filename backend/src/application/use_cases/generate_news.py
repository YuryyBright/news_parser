# application/use_cases/generate_news.py
"""
GenerateNewsUseCase — RAG-пайплайн генерації новини.

Кроки:
  A. Embed запиту (IEmbeddingService)
  B. Пошук в ChromaDB (IChunkVectorRepository)
  C. Фільтрація:
       similarity_score >= SIMILARITY_THRESHOLD (0.85)
       AND char_length > MIN_TEXT_LENGTH (150)
       AND language == target_language ("uk")
  D. Формування контексту (build_user_prompt)
  E. LLM Call (ILLMClient → AnthropicClient)
  F. Збереження (IGeneratedNewsStorage → MarkdownStorage)

Якщо після фільтрації нема жодного чанку — повертає GeneratedNews.skipped().

Зв'язок з наявною інфраструктурою:
  - Той самий ArticleVectorRepository (chroma_client.py) для embed
    → але окрема колекція "docx_chunks" (не "articles")
  - IEmbeddingService — той самий SentenceTransformerEmbedder
    або будь-який інший через DI
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from src.application.ports.rag_ports import (
    IChunkVectorRepository,
    IEmbeddingService,
    IGeneratedNewsStorage,
    ILLMClient,
)
from src.domain.news_generation.entities import GeneratedNews, SearchResult
from src.domain.news_generation.prompts import (
    MIN_TEXT_LENGTH,
    SIMILARITY_THRESHOLD,
    SYSTEM_PROMPT,
    TOP_K_RESULTS,
    build_user_prompt,
)

logger = logging.getLogger(__name__)


@dataclass
class GenerateNewsResult:
    news: GeneratedNews
    saved_path: str = ""
    context_chunks_used: int = 0
    context_chunks_found: int = 0


class GenerateNewsUseCase:
    """
    Оркеструє RAG-пайплайн: пошук контексту → генерація → збереження.

    Args:
        embedder:         для векторизації запиту
        chunk_repo:       векторна БД з чанками .docx
        llm_client:       LLM для генерації тексту
        news_storage:     куди зберігати результат
        similarity_threshold: поріг similarity (default 0.85)
        min_text_length:  мінімальна довжина чанку (default 150)
        target_language:  мова для фільтрації чанків (default "uk")
        top_k:            скільки топ-чанків брати в контекст
    """

    def __init__(
        self,
        embedder: IEmbeddingService,
        chunk_repo: IChunkVectorRepository,
        llm_client: ILLMClient,
        news_repo = None, 
        similarity_threshold: float = SIMILARITY_THRESHOLD,
        min_text_length: int = MIN_TEXT_LENGTH,
        target_language: str = "uk",
        top_k: int = TOP_K_RESULTS,
    ) -> None:
        self._embedder   = embedder
        self._repo       = chunk_repo
        self._llm        = llm_client
        self._repo_storage = news_repo
        self._threshold  = similarity_threshold
        self._min_length = min_text_length
        self._language   = target_language
        self._top_k      = top_k

    async def execute(self, query: str) -> GenerateNewsResult:
        """
        Генерує новину за запитом query.

        Returns:
            GenerateNewsResult — містить GeneratedNews і шлях до збереженого файлу.
            Якщо контексту недостатньо — news.status == "skipped".
        """
        logger.info("[generate] Query: %r", query)

        # ── A. Векторизація запиту ────────────────────────────────────────────
        query_vector = await self._embedder.embed_one(query)
        logger.debug("[generate] Query embedded, dim=%d", len(query_vector))

        # ── B. Пошук релевантних чанків ───────────────────────────────────────
        # Шукаємо більше ніж top_k щоб після фільтрації лишилось достатньо
        raw_results = await self._repo.query_similar(
            query_vector=query_vector,
            n_results=self._top_k * 3,
            language_filter=self._language,
        )
        logger.info("[generate] Found %d candidates from vector search", len(raw_results))

        # ── C. Фільтрація (similarity + length + language) ───────────────────
        filtered = self._filter_results(raw_results)
        logger.info(
            "[generate] After filter: %d/%d chunks pass "
            "(threshold=%.2f, min_length=%d, lang=%s)",
            len(filtered), len(raw_results),
            self._threshold, self._min_length, self._language,
        )

        if not filtered:
            logger.warning("[generate] No relevant context found for query: %r", query)
            news = GeneratedNews.skipped(
                query=query,
                reason="Недостатньо релевантного контексту для генерації новини.",
            )
            return GenerateNewsResult(
                news=news,
                context_chunks_found=len(raw_results),
                context_chunks_used=0,
            )

        # Беремо топ-k після фільтрації
        context_chunks = filtered[: self._top_k]

        # ── D. Формування промпту ─────────────────────────────────────────────
        context_texts = [r.text for r in context_chunks]
        user_prompt   = build_user_prompt(query=query, context_chunks=context_texts)

        avg_score = sum(r.similarity_score for r in context_chunks) / len(context_chunks)
        logger.info(
            "[generate] Sending to LLM: %d context chunks, avg_score=%.3f",
            len(context_chunks), avg_score,
        )

        # ── E. LLM Call ───────────────────────────────────────────────────────
        try:
            llm_response = await self._llm.complete(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=8192,
            )
            logger.info(
                "[generate] LLM responded: model=%s tokens_in=%d tokens_out=%d",
                llm_response.model,
                llm_response.input_tokens,
                llm_response.output_tokens,
            )
        except Exception as exc:
            logger.error("[generate] LLM call failed: %s", exc)
            news = GeneratedNews(
                id=__import__("uuid").uuid4(),
                title="",
                body="",
                query=query,
                source_chunks=[r.chunk_id for r in context_chunks],
                status=__import__("domain.news_generation.entities", fromlist=["GenerationStatus"]).GenerationStatus.FAILED,
                context_score=avg_score,
            )
            return GenerateNewsResult(news=news, context_chunks_used=len(context_chunks))

        # Розбиваємо відповідь на заголовок + тіло
        title, body = _parse_llm_response(llm_response.text)

        news = GeneratedNews.create(
            title=title,
            body=body,
            query=query,
            source_chunks=[r.chunk_id for r in context_chunks],
            context_score=avg_score,
            model_used=llm_response.model,
            language=self._language,
        )

        # ── F. Збереження ─────────────────────────────────────────────────────
        try:
            saved_path = ""
            if self._repo_storage is not None:
                saved_path = await self._repo_storage.save(news)
            logger.info("[generate] Saved to: %s", saved_path)
        except Exception as exc:
            logger.error("[generate] Storage failed: %s", exc)
            saved_path = ""

        return GenerateNewsResult(
            news=news,
            saved_path=saved_path,
            context_chunks_found=len(raw_results),
            context_chunks_used=len(context_chunks),
        )

    def _filter_results(self, results: list[SearchResult]) -> list[SearchResult]:
        """
        Залишає лише результати що проходять всі три умови:
          1. similarity_score >= threshold
          2. len(text) > min_text_length
          3. language == target_language (якщо задано)
        """
        filtered = []
        for r in results:
            if r.similarity_score < self._threshold:
                logger.debug(
                    "[generate] Skip chunk=%s: score=%.3f < %.2f",
                    r.chunk_id, r.similarity_score, self._threshold,
                )
                continue
            if len(r.text) <= self._min_length:
                logger.debug(
                    "[generate] Skip chunk=%s: length=%d <= %d",
                    r.chunk_id, len(r.text), self._min_length,
                )
                continue
            if self._language and r.language not in (self._language, "unknown", ""):
                logger.debug(
                    "[generate] Skip chunk=%s: lang=%s != %s",
                    r.chunk_id, r.language, self._language,
                )
                continue
            filtered.append(r)

        return sorted(filtered, key=lambda x: x.similarity_score, reverse=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_llm_response(text: str) -> tuple[str, str]:
    """
    Розбиває відповідь LLM на (заголовок, тіло).

    LLM інструктована писати заголовок першим рядком.
    Якщо структура неочікувана — весь текст іде в body.
    """
    lines = text.strip().splitlines()
    if not lines:
        return "", text

    # Перший непорожній рядок — заголовок
    title = ""
    body_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped:
            # Прибираємо можливі маркери типу "Заголовок:" або "**Title**"
            stripped = stripped.removeprefix("Заголовок:").strip()
            stripped = stripped.strip("*").strip()
            title = stripped
            body_start = i + 1
            break

    # Решта — тіло (пропускаємо порожні рядки на початку)
    body_lines = lines[body_start:]
    body = "\n".join(body_lines).strip()

    return title, body