# application/use_cases/process_articles.py
"""
ProcessArticlesUseCase — обробляє pending RawArticle → Article.

Pipeline для кожної статті:
  1. Fetch full text              (trafilatura / IArticleContentFetcher)
     → raw.content.body оновлюється одразу, до dedup і scoring
  2. Detect language              (через ILanguageDetector порт)
  3. Встановлюємо content.language перед scoring
     → BM25 і GeoFilter бачать мову для geo-penalty
  4. Score relevance              (через IScoringService порт)
     - CompositeScoringService: BM25+geo pre-filter + Embeddings + geo final
     - Рахується по ПОВНОМУ витягнутому тексту
  5. Dedup check                  (через DeduplicateRawArticleUseCase — MinHash + exact)
     - Exact duplicate (sha256): відкидаємо одразу
     - Near-duplicate (MinHash Jaccard): відкидаємо якщо similarity >= threshold
     - Унікальний: зберігаємо підпис для майбутніх перевірок
     - Перевіряється по ПОВНОМУ витягнутому тексту (до перекладу)
  6. Reject якщо score нижче threshold
  7. Переклад тільки перших TRANSLATE_MAX_CHARS символів body (економія токенів)
  8. Build Article aggregate
  9. Auto-tag якщо accepted       (через ITagger порт → EmbeddingTagger gap-based)
 10. Save Article + mark RawArticle processed
 11. Implicit feedback: якщо accepted → зберегти вектор у профіль
 12. Telegram notify:
       - RAG топ-5 схожих для стилістичного контексту
       - LLM-рерайт в стилі попередніх публікацій
       - відправка підписникам

Fallback: якщо dedup_uc=None — примітивна перевірка по URL/hash.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Any
from uuid import uuid4, UUID

from sqlalchemy.exc import IntegrityError
import asyncio
from src.application.ports.language_detector import ILanguageDetector
from src.application.ports.scoring_service import IScoringService
from src.application.ports.tagger import ITagger
from src.application.ports.translator import ITranslator, TranslationError
from src.application.ports.article_content_fetcher import IArticleContentFetcher
from src.domain.ingestion.entities import RawArticle
from src.domain.ingestion.repositories import IRawArticleRepository
from src.domain.knowledge.entities import Article, Tag
from src.domain.knowledge.repositories import IArticleRepository
from src.domain.knowledge.value_objects import ArticleStatus, ContentHash, PublishedAt
from src.domain.deduplication.services import DeduplicationDomainService
from src.application.ports.telegram_notifier import (
    ITelegramNotifier, ArticleNotification,
)
from src.application.ports.llm_rewriter import ILLMRewriter
logger = logging.getLogger(__name__)

_BATCH_SIZE = 100
MIN_TEXT_LENGTH = 500

# Максимальна кількість символів body, які передаються в перекладач.
# Повний витягнутий текст зберігається в original_body та використовується
# для dedup, scoring і Telegram-нотифікацій — обрізається тільки переклад.
TRANSLATE_MAX_CHARS = 3_000

# ─── Порт для implicit feedback ──────────────────────────────────────────────

class IProfileLearner(ABC):
    @abstractmethod
    async def add_to_profile(
        self,
        article_id: UUID,
        content_text: str,
        score: float,
        tags: list[str],
    ) -> None: ...
    async def remove_from_profile(self, article_id: UUID, content_text: str = None) -> None: ...


# ─── DTO результату ───────────────────────────────────────────────────────────

@dataclass
class ProcessArticlesResult:
    processed: int = 0
    accepted:  int = 0
    rejected:  int = 0
    failed:    int = 0
    dedup_skipped: int = 0
    errors: list[str] = field(default_factory=list)


# ─── Use Case ─────────────────────────────────────────────────────────────────

class ProcessArticlesUseCase:

    def __init__(
        self,
        session_factory: Callable[..., Any],
        raw_repo_factory: Callable[[Any], IRawArticleRepository],
        article_repo_factory: Callable[[Any], IArticleRepository],
        language_detector: ILanguageDetector,
        scoring_service: IScoringService,
        tagger: ITagger,
        profile_learner: IProfileLearner,
        dedup_uc=DeduplicationDomainService,
        batch_size: int = _BATCH_SIZE,
        threshold: float = 0.65,
        translator: ITranslator | None = None,
        target_language: str = "uk",
        telegram_notifier: ITelegramNotifier | None = None,
        telegram_threshold: float = 0.65,
        content_fetcher: IArticleContentFetcher | None = None,
        llm_rewriter: ILLMRewriter | None = None,
        chunk_repo=None,
        generated_news_repo_factory: Callable[[Any], Any] | None = None, # ← ДОДАНО
    ) -> None:
        self._session_factory      = session_factory
        self._raw_repo_factory     = raw_repo_factory
        self._article_repo_factory = article_repo_factory
        self._lang_detector        = language_detector
        self._scoring_service      = scoring_service
        self._tagger               = tagger
        self._profile_learner      = profile_learner
        if callable(dedup_uc) and not hasattr(dedup_uc, "execute"):
            self._dedup_uc_factory = dedup_uc
        else:
            self._dedup_uc_factory = (lambda uc: lambda _session: uc)(dedup_uc) if dedup_uc else None
        self._batch_size           = batch_size
        self._threshold            = threshold
        self._translator           = translator
        self._target_language      = target_language
        self._telegram_notifier    = telegram_notifier
        self._telegram_threshold   = telegram_threshold
        self._content_fetcher      = content_fetcher
        self._llm_rewriter         = llm_rewriter
        self._chunk_repo           = chunk_repo
        self._generated_news_repo_factory = generated_news_repo_factory

    async def execute(self) -> ProcessArticlesResult:
        result = ProcessArticlesResult()

        async with self._session_factory() as session:
            async with session.begin():
                raw_repo = self._raw_repo_factory(session)
                raw_articles = await raw_repo.get_unprocessed(limit=self._batch_size)

        if not raw_articles:
            logger.debug("process_articles: no pending articles")
            return result

        logger.info("process_articles: processing %d articles", len(raw_articles))

        for raw in raw_articles:
            try:
                outcome = await self._run_one(raw)
                result.processed += 1
                if outcome == "accepted":
                    result.accepted += 1
                elif outcome == "dedup":
                    result.dedup_skipped += 1
                else:
                    result.rejected += 1
            except Exception as exc:
                result.failed += 1
                result.errors.append(f"raw_id={raw.id}: {exc}")
                logger.exception("Failed to process raw article %s", raw.id)
            await asyncio.sleep(5)

        logger.info(
            "process_articles done: processed=%d accepted=%d rejected=%d "
            "dedup_skipped=%d failed=%d",
            result.processed, result.accepted, result.rejected,
            result.dedup_skipped, result.failed,
        )
        return result

    async def _run_one(self, raw: RawArticle) -> str:
        """Повертає 'accepted' | 'rejected' | 'dedup' | 'skipped'."""
        async with self._session_factory() as session:
            async with session.begin():
                return await self._process_one(session, raw)

    async def _process_one(self, session, raw: RawArticle) -> str:
        article_repo = self._article_repo_factory(session)
        raw_repo     = self._raw_repo_factory(session)

        if _is_too_old(raw, max_age_days=2):
            await raw_repo.mark_processed(raw.id)
            return "skipped"

        # ── 1. Зберігаємо оригінальний title ─────────────────────────────
        # (body буде перезаписано після fetch — зберігаємо ПІСЛЯ кроку fetch)
        original_title = raw.content.title

        # ── 2. Fetch full text — ПЕРШИЙ крок, до dedup і scoring ─────────
        # Якщо RSS-тіло коротке — витягуємо повний текст зі сторінки.
        # raw.content.body оновлюється на місці, тому всі подальші кроки
        # (dedup, scoring, translate) працюють з одним і тим самим текстом.
        rss_body = raw.content.body or ""
        if len(raw.content.full_text()) < MIN_TEXT_LENGTH:
            fetched_text = await self._fetch_raw_full_text(raw.content.url, rss_body)
            if fetched_text and fetched_text != rss_body:
                _set_attr(raw.content, "body", fetched_text)
                logger.debug(
                    "Full text fetched before dedup/scoring: url=%s rss_chars=%d fetched_chars=%d",
                    raw.content.url, len(rss_body), len(fetched_text),
                )

        # ── 3. Зберігаємо original_body ПІСЛЯ fetch, ДО перекладу ────────
        original_body = raw.content.body

        # ── 4. Detect language ────────────────────────────────────────────
        language = await self._detect_language(raw)
        _inject_language(raw.content, language)

        # ── 5. Dedup по витягнутому тексту (до translate) ─────────────────
        dedup_uc = self._dedup_uc_factory(session) if self._dedup_uc_factory else None
        is_dup, _dup_reason = await self._check_dedup(
            raw, article_repo, raw_repo, dedup_uc,
            original_title=original_title,
            original_body=original_body,   # ← повний витягнутий текст
        )
        if is_dup:
            await raw_repo.mark_processed(raw.id)
            return "dedup"

        # ── 6. Score по витягнутому тексту (до перекладу) ─────────────────
        relevance_score = await self._score(raw)

        # ── 7. Reject якщо score нижче threshold ──────────────────────────
        if relevance_score < self._threshold:
            await raw_repo.mark_processed(raw.id)
            logger.info(
                "Rejected (low score): raw_id=%s url=%s score=%.3f threshold=%.3f",
                raw.id, raw.content.url, relevance_score, self._threshold,
            )
            return "rejected"

        # ── 8. Переклад тільки для прийнятих статей ───────────────────────
        # Перекладається тільки перші TRANSLATE_MAX_CHARS символів body —
        # решта відкидається для економії токенів перекладача.
        # original_body (повний витягнутий текст) зберігається незміненим.
        if self._translator is not None:
            language = await self._translate_content(raw, language)
            _inject_language(raw.content, language)

        # ── 9. Тегування по перекладеному (або оригінальному) тексту ──────
        translated_full_text = raw.content.full_text()
        tag_names = self._tagger.tag(translated_full_text)

        # ── 10. Прийняти і зберегти ───────────────────────────────────────
        article = _build_article(raw, language, original_title, original_body)
        article.accept(relevance_score)

        if tag_names:
            tags = [Tag(name=name, source="auto") for name in tag_names]
            article.add_tags(tags)

        try:
            await article_repo.save(article)
        except IntegrityError:
            # Race condition: інший конкурентний таск вже зберіг цю статтю
            # між нашим dedup-check і save.
            #
            # ВАЖЛИВО: після IntegrityError SQLAlchemy закриває поточну транзакцію.
            # Будь-яка операція в тій самій сесії → InvalidRequestError.
            # Тому mark_processed виконуємо в окремій сесії/транзакції.
            logger.info(
                "Race condition dedup: url=%s content_hash already exists",
                raw.content.url,
            )
            await self._mark_processed_safe(raw.id)
            return "dedup"

        await raw_repo.mark_processed(raw.id)

        logger.info(
            "Accepted: raw_id=%s article=%s lang=%s score=%.3f tags=%s",
            raw.id, article.id, language, relevance_score, tag_names,
        )

        # ── 11. Implicit feedback: зберігаємо вектор у профіль ───────────
        if self._profile_learner is not None and relevance_score >= 0.85:
            try:
                await self._profile_learner.add_to_profile(
                    article_id=article.id,
                    content_text=original_body,   # ← повний витягнутий текст
                    score=relevance_score,
                    tags=tag_names,
                )
            except Exception as exc:
                logger.warning("ProfileLearner failed for article=%s: %s", article.id, exc)

        # ── 12. Telegram notify ───────────────────────────────────────────
        if self._telegram_notifier is None:
            logger.debug("Telegram notifier not set, skipping notify")
            return "accepted"

        if relevance_score >= self._telegram_threshold:
            await self._notify_telegram(
                session=session,
                article=article,
                original_full_text=original_body,   # ← повний витягнутий текст
                relevance_score=relevance_score,
                tag_names=tag_names,
                language=language,
                published_at=article.published_at.value if article.published_at else None,
            )

        return "accepted"

    # ─── Fetch helpers ────────────────────────────────────────────────────────

    async def _fetch_raw_full_text(self, url: str, fallback: str) -> str:
        """
        Витягує повний текст статті перед dedup/scoring.
        Повертає fallback якщо fetcher недоступний або повернув пусто.
        """
        if self._content_fetcher is None:
            return fallback

        if len(fallback) >= MIN_TEXT_LENGTH:
            return fallback

        try:
            fetched = await self._content_fetcher.fetch_full_text(url)
            if fetched and len(fetched) > 200:
                return fetched
        except Exception as exc:
            logger.warning("ContentFetcher failed for url=%s: %s", url, exc)

        return fallback

    # ─── Telegram pipeline ────────────────────────────────────────────────────

    async def _build_similar_articles_context(self, full_text: str) -> str:
        """
        Шукає топ-5 схожих вже збережених Article через chunk_repo
        (той самий підхід що у VerifySearchUseCase.execute).
        Повертає текстовий блок для style_context.
        """
        if self._chunk_repo is None or not full_text:
            return ""

        try:
            from src.infrastructure.ml.embedder import Embedder

            embedder = Embedder.instance()
            query_vec = embedder.encode_query(full_text)
            similar = await self._chunk_repo.query_similar(query_vec, n_results=5)

            if not similar:
                return ""

            parts = []
            for r in similar:
                meta     = getattr(r, "metadata", {}) or {}
                source   = (
                    meta.get("source_file")
                    or meta.get("filename")
                    or meta.get("url")
                    or "невідомо"
                )
                score    = getattr(r, "score", None)
                header   = f"[{source}]" + (f" score={score:.3f}" if score else "")
                parts.append(f"{header}\n{r.text}")

            return "\n\n---\n\n".join(parts)

        except Exception as exc:
            logger.warning("_build_similar_articles_context failed: %s", exc)
            return ""

    async def _notify_telegram(
        self,
        session,
        article: Article,
        original_full_text: str,
        relevance_score: float,
        tag_names: list[str],
        language: str,
        published_at=None,
    ) -> None:
        """
        Повний Telegram pipeline:
        1. RAG топ-5 docx-чанків для стилістичного еталону
        2. Топ-5 схожих збережених статей (як у verify) — додатковий контекст
        3. LLM-рерайт з об'єднаним контекстом
        4. Відправка підписникам
        """
        full_text = original_full_text

        # ── 1. Стилістичний контекст з docx-чанків (RAG) ─────────────────────
        style_context = await self._build_style_context(full_text)

        # ── 2. Схожі збережені статті (verify-підхід) ────────────────────────
        similar_articles_context = await self._build_similar_articles_context(full_text)

        # Об'єднуємо: docx-еталони йдуть першими, схожі статті — після
        combined_context = style_context
        if similar_articles_context:
            separator = "\n\n═══ СХОЖІ СТАТТІ З АРХІВУ ═══\n\n"
            combined_context = (
                f"{style_context}{separator}{similar_articles_context}"
                if style_context
                else similar_articles_context
            )

        # ── 3. LLM-рерайт ────────────────────────────────────────────────────
        rewritten = await self._rewrite_for_telegram(
            title=article.title or "",
            full_text=full_text,
            url=article.url,
            style_context=combined_context,
            published_at=published_at,
        )
        # ── 3.5 Збереження згенерованої новини в БД ──────────────────────────
        if rewritten and self._generated_news_repo_factory:
            try:
                from src.domain.news_generation.entities import GeneratedNews
                
                # Використовуємо ваш фабричний метод create()
                generated_news = GeneratedNews.create(
                    title=article.title or "Без заголовка",
                    body=f"{rewritten}\n\n[Джерело]({article.url})",
                    query="Telegram Rewrite",
                    source_chunks=[], 
                    context_score=relevance_score,
                    model_used="telegram_rewriter",
                    language=language
                )
                
                gen_news_repo = self._generated_news_repo_factory(session)
                await gen_news_repo.save(generated_news)
                logger.info("Saved generated news for article=%s", article.id)
            except Exception as exc:
                logger.error("Failed to save GeneratedNews for article=%s: %s", article.id, exc)
        # ── 4. Відправка ──────────────────────────────────────────────────────
        try:
            notification = ArticleNotification(
                id=article.id,
                title=article.title or "",
                body=article.body or "",
                url=article.url,
                score=relevance_score,
                tags=tag_names,
                language=language,
                published_at=article.published_at.value if article.published_at else None,
                full_text=full_text,
                style_context=combined_context,
                rewritten_text=rewritten,
            )
            await self._telegram_notifier.notify_all(notification)
        except Exception as exc:
            logger.warning("TelegramNotifier failed for article=%s: %s", article.id, exc)

    async def _build_style_context(self, full_text: str) -> str:
        """
        Шукає топ-5 найрелевантніших чанків з RAG для стилістичного контексту.
        """
        if self._chunk_repo is None or not full_text:
            return ""

        try:
            from src.infrastructure.ml.embedder import Embedder
            embedder = Embedder.instance()
            article_vec = embedder.encode_passage(full_text)
            similar = await self._chunk_repo.query_similar(article_vec, n_results=5)
            if not similar:
                return ""
            context = "\n\n---\n\n".join(r.text for r in similar)
            logger.debug(
                "Style context built: %d chunks, total_chars=%d",
                len(similar), len(context),
            )
            return context
        except Exception as exc:
            logger.warning("RAG style context failed: %s", exc)
            return ""

    async def _rewrite_for_telegram(
        self,
        title: str,
        full_text: str,
        url: str,
        style_context: str,
        published_at,
    ) -> str:
        if self._llm_rewriter is None:
            return ""
        return await self._llm_rewriter.rewrite(
            title=title,
            full_text=full_text,
            url=url,
            style_context=style_context,
            published_at=published_at,
        )

    # ─── mark_processed safe ─────────────────────────────────────────────────

    async def _mark_processed_safe(self, raw_id: UUID) -> None:
        """
        Позначає RawArticle як оброблений у НОВІЙ сесії та транзакції.

        Використовується після IntegrityError у _process_one,
        коли поточна транзакція вже закрита SQLAlchemy після rollback.
        """
        try:
            async with self._session_factory() as new_session:
                async with new_session.begin():
                    raw_repo = self._raw_repo_factory(new_session)
                    await raw_repo.mark_processed(raw_id)
        except Exception as exc:
            logger.warning(
                "mark_processed_safe failed for raw_id=%s (non-critical): %s",
                raw_id, exc,
            )

    # ─── Dedup helpers ────────────────────────────────────────────────────────

    async def _check_dedup(self, raw, article_repo, raw_repo, dedup_uc=None,
                            original_title=None, original_body=None):
        if dedup_uc is not None:
            return await self._check_dedup_minhash(
                raw, dedup_uc,
                original_title=original_title,
                original_body=original_body,
            )
        return await self._check_dedup_primitive(raw, article_repo, raw_repo)

    async def _check_dedup_minhash(
        self,
        raw,
        dedup_uc,
        original_title=None,
        original_body=None,
    ) -> tuple[bool, str | None]:
        """MinHash деduplication через DeduplicateRawArticleUseCase."""
        try:
            result = await dedup_uc.execute(
                raw.id,
                original_title=original_title,
                original_body=original_body,
            )
        except Exception as exc:
            logger.warning(
                "Dedup check failed for raw_id=%s, skipping dedup: %s",
                raw.id, exc,
            )
            return False, None

        if result.is_duplicate:
            sim_info = (
                f" similarity={result.similarity:.3f}"
                if result.similarity is not None
                else ""
            )
            logger.info(
                "Dedup reject: url=%s reason=%s existing=%s%s",
                raw.content.url, result.reason, result.existing_id, sim_info,
            )
            return True, str(result.reason)

        return False, None

    async def _check_dedup_primitive(
        self,
        raw: RawArticle,
        article_repo,
        raw_repo,
    ) -> tuple[bool, str | None]:
        """
        Fallback: примітивна дедуплікація по URL і hash.
        Використовується тільки якщо dedup_uc не підключений.
        """
        if await article_repo.get_by_url(raw.content.url):
            logger.debug("Duplicate url=%s, skipping", raw.content.url)
            await raw_repo.mark_deduplicated(raw.id)
            return True, "exact_url"

        if await article_repo.exists_by_hash(raw.content_hash):
            logger.info("Duplicate hash url=%s, skipping", raw.content.url)
            await raw_repo.mark_deduplicated(raw.id)
            return True, "exact_hash"

        return False, None

    # ─── Інші helpers ─────────────────────────────────────────────────────────

    async def _detect_language(self, raw: RawArticle) -> str:
        language_str = raw.content.language
        if not language_str:
            try:
                language_str = await self._lang_detector.detect(raw.content.full_text())
            except Exception as exc:
                logger.warning("Language detection failed for %s: %s", raw.id, exc)
                language_str = "unknown"
        return language_str or "unknown"

    async def _score(self, raw: RawArticle) -> float:
        try:
            return await self._scoring_service.score(raw.content)
        except Exception as exc:
            logger.warning("Scoring failed for %s: %s", raw.id, exc)
            return 0.0

    async def _translate_content(self, raw: RawArticle, language: str) -> str:
        """
        Перекладає title повністю і перші TRANSLATE_MAX_CHARS символів body.
        Повний оригінальний текст зберігається в original_body (поза цим методом).
        """
        if not self._translator.should_translate(language, self._target_language):
            return language

        try:
            # Обрізаємо body до TRANSLATE_MAX_CHARS для економії токенів.
            # Для scoring і dedup body вже використано повністю на попередніх кроках.
            body_to_translate = (raw.content.body or "")[:TRANSLATE_MAX_CHARS]

            title_result = await self._translator.translate(
                raw.content.title or "",
                target_language=self._target_language,
                source_language=language if language != "unknown" else None,
            )
            body_result = await self._translator.translate(
                body_to_translate,
                target_language=self._target_language,
                source_language=language if language != "unknown" else None,
            )

            _set_attr(raw.content, "title", title_result.text)
            _set_attr(raw.content, "body", body_result.text)

            resolved_language = language
            if language == "unknown" and body_result.detected_language:
                resolved_language = body_result.detected_language
                _inject_language(raw.content, resolved_language)

            logger.info(
                "Translated: url=%s lang=%s→%s body_chars=%d (original=%d)",
                raw.content.url, language, self._target_language,
                len(body_to_translate), len(raw.content.body or ""),
            )
            return resolved_language

        except TranslationError as exc:
            logger.warning("Translation skipped for %s: %s", raw.content.url, exc)
            return language


# ─── Module-level helpers ─────────────────────────────────────────────────────

def _set_attr(obj, name: str, value) -> None:
    """Встановлює атрибут об'єкта, обходячи frozen dataclass/VO якщо потрібно."""
    try:
        setattr(obj, name, value)
    except (AttributeError, TypeError):
        object.__setattr__(obj, name, value)


def _inject_language(content, language: str) -> None:
    try:
        existing = getattr(content, "language", None)
        if not existing:
            _set_attr(content, "language", language)
    except Exception as exc:
        logger.debug("Could not inject language into content: %s", exc)


def _is_too_old(raw: RawArticle, max_age_days: int = 7) -> bool:
    """Повертає True якщо стаття старіша за max_age_days."""
    published_at = getattr(raw.content, "published_at", None)
    if not published_at:
        return False

    from datetime import datetime, timezone, timedelta
    if isinstance(published_at, str):
        try:
            from dateutil.parser import parse
            published_at = parse(published_at)
        except Exception:
            return False

    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    return datetime.now(timezone.utc) - published_at > timedelta(days=max_age_days)


def _build_article(
    raw: RawArticle,
    language: str,
    original_title: str | None = None,
    original_body: str | None = None,
) -> Article:
    return Article(
        id=uuid4(),
        source_id=raw.source_id,
        raw_article_id=str(raw.id),
        title=raw.content.title,
        body=raw.content.body,
        original_title=original_title,
        original_body=original_body,
        url=raw.content.url,
        language=language,
        status=ArticleStatus.PENDING,
        relevance_score=0.0,
        content_hash=ContentHash(value=raw.content_hash),
        published_at=PublishedAt(value=raw.content.published_at) if raw.content.published_at else None,
        tags=[],
    )