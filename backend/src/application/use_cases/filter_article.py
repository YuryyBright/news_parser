# application/use_cases/filter_article.py
"""
FilterArticleUseCase — застосувати relevance-фільтр і перевести статтю
в стан ACCEPTED або REJECTED через state-machine методи aggregate.

Це application service: він оркеструє доменні об'єкти,
але сама логіка фільтрації (ваги, threshold) живе в domain service
або в infrastructure (scoring service).

DDD-правила:
  ✅ залежить від портів (IArticleRepository, IScoringService)
  ✅ state-machine переходи — через методи aggregate (article.accept / reject)
  ✅ доменна подія ArticleSaved випускається всередині aggregate
  ✅ use case лише orchestrates — не знає про SQL
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from src.domain.knowledge.exceptions import ArticleNotFound
from src.domain.knowledge.repositories import IArticleRepository
from src.application.dtos.article_dto import AcceptArticleCommand, RejectArticleCommand

logger = logging.getLogger(__name__)


# ── Port: зовнішня scoring-логіка (реалізується в infrastructure) ─────────────

class IScoringService(ABC):
    """
    Порт для обчислення relevance score.

    Реалізації:
      - EmbeddingsScoringService   (Chroma cosine similarity)
      - KeywordScoringService      (BM25 / keyword match)
      - CompositeScoringService    (зважена комбінація)
    """
    @abstractmethod
    async def score(self, article_id: UUID, user_profile_id: UUID | None = None) -> float: ...


# ── Result ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FilterResult:
    article_id: UUID
    accepted: bool
    score: float


# ── Use Case ──────────────────────────────────────────────────────────────────

class FilterArticleUseCase:
    """
    Фільтрує одну статтю:
      1. завантажує з репо
      2. отримує score від scoring service
      3. порівнює з threshold
      4. викликає article.accept(score) або article.reject(score)
      5. зберігає aggregate

    Threshold беремо з конфігу, але може передаватися й ззовні
    (для персоналізованих профілів).
    """

    def __init__(
        self,
        article_repo: IArticleRepository,
        scoring_service: IScoringService,
        threshold: float = 0.40,
    ) -> None:
        self._repo = article_repo
        self._scoring = scoring_service
        self._threshold = threshold

    async def execute(
        self,
        article_id: UUID,
        user_profile_id: UUID | None = None,
        threshold: float | None = None,
    ) -> FilterResult:
        article = await self._repo.get(article_id)
        if article is None:
            raise ArticleNotFound(article_id)

        effective_threshold = threshold if threshold is not None else self._threshold

        score = await self._scoring.score(article_id, user_profile_id)

        if score >= effective_threshold:
            article.accept(score)
            logger.info(
                "Article accepted: id=%s score=%.3f threshold=%.2f",
                article_id, score, effective_threshold,
            )
        else:
            article.reject(score)
            logger.info(
                "Article rejected: id=%s score=%.3f threshold=%.2f",
                article_id, score, effective_threshold,
            )

        await self._repo.save(article)

        return FilterResult(
            article_id=article.id,
            accepted=article.is_accepted(),
            score=score,
        )


# ── Batch variant ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BatchFilterResult:
    accepted: list[UUID]
    rejected: list[UUID]
    errors: list[tuple[UUID, str]]


class BatchFilterArticleUseCase:
    """
    Фільтрує список статей.
    Кожна стаття — окрема транзакція: помилка однієї не блокує інші.

    Використання (з worker):
        result = await BatchFilterArticleUseCase(...).execute(article_ids)
        logger.info("accepted=%d rejected=%d errors=%d",
                    len(result.accepted), len(result.rejected), len(result.errors))
    """

    def __init__(
        self,
        article_repo: IArticleRepository,
        scoring_service: IScoringService,
        threshold: float = 0.40,
    ) -> None:
        self._single = FilterArticleUseCase(article_repo, scoring_service, threshold)

    async def execute(
        self,
        article_ids: list[UUID],
        user_profile_id: UUID | None = None,
    ) -> BatchFilterResult:
        accepted: list[UUID] = []
        rejected: list[UUID] = []
        errors: list[tuple[UUID, str]] = []

        for article_id in article_ids:
            try:
                result = await self._single.execute(article_id, user_profile_id)
                (accepted if result.accepted else rejected).append(article_id)
            except ArticleNotFound:
                errors.append((article_id, "not_found"))
            except Exception as exc:  # noqa: BLE001
                logger.exception("Filter failed for article %s: %s", article_id, exc)
                errors.append((article_id, str(exc)))

        return BatchFilterResult(accepted=accepted, rejected=rejected, errors=errors)
