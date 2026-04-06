# presentation/api/routes/embeddings_debug.py
"""
Embeddings Debug Router — діагностика та тестування vector store і scoring pipeline.

ВАЖЛИВО: підключати ТІЛЬКИ у dev/staging середовищах.
  В production вимкнути через settings.app_debug або окремий env-flag.

Endpoints:
  GET  /debug/embeddings/status              — стан pipeline (ініціалізований чи ні)
  GET  /debug/embeddings/profile/count       — кількість векторів у interest_profile
  GET  /debug/embeddings/profile/entries     — список записів (id, score, tags, added_at)
  GET  /debug/embeddings/profile/centroid    — інформація про центроїд
  DELETE /debug/embeddings/profile/{article_id} — видалити вектор з профілю
  DELETE /debug/embeddings/profile           — очистити весь профіль
  POST /debug/embeddings/profile/add         — вручну додати текст у профіль
  POST /debug/embeddings/score               — скорувати довільний текст
  POST /debug/embeddings/compare             — порівняти два тексти (cosine similarity)
  POST /debug/embeddings/geo                 — перевірити geo-фільтр для тексту
  POST /debug/embeddings/feedback-trace      — трасувати що станеться при feedback
  GET  /debug/embeddings/article/{article_id}/profile-check — чи є стаття у профілі

Типова flow діагностики:
  1. GET /status        — переконатись що pipeline ready
  2. GET /profile/count — скільки векторів є
  3. POST /score        — скорувати тестову статтю
  4. POST /feedback-trace — перевірити що лайк справді потрапляє у профіль
"""
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

from src.config.container import Container, get_container
from src.presentation.api.schemas.debug import *
logger = logging.getLogger(__name__)

router = APIRouter()




# ═══════════════════════════════════════════════════════════════════════════════
# Helpers — витягуємо приватні поля з Container
# ═══════════════════════════════════════════════════════════════════════════════

def _get_profile_learner(container: Container):
    """Повертає ProfileLearner або кидає 503 якщо pipeline не ініціалізований."""
    learner = container._profile_learner
    if learner is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Scoring pipeline не ініціалізований. "
                "Переконайтесь що container.init_async() викликано у lifespan."
            ),
        )
    return learner


def _get_scoring(container: Container):
    """Повертає CompositeScoringService або кидає 503."""
    scoring = container._composite_scoring
    if scoring is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CompositeScoringService не ініціалізований.",
        )
    return scoring


def _get_embedder(container: Container):
    """Витягує Embedder з ProfileLearner через приватне поле."""
    learner = _get_profile_learner(container)
    return learner._embedder


def _get_profile_repo(container: Container):
    """Витягує InterestProfileRepository з ProfileLearner."""
    learner = _get_profile_learner(container)
    return learner._profile_repo


def _make_fake_content(text: str, language: str = "uk", title: str = ""):
    """
    Створює мінімальний ParsedContent-подібний об'єкт для тестового скорингу.
    Не імпортує ParsedContent напряму щоб уникнути circular imports.
    """
    class _FakeContent:
        def __init__(self, text: str, lang: str, title: str):
            self._text = text
            self.language = lang
            self.title = title
            self.body = text
            self.url = "debug://test"
            self.published_at = None

        def full_text(self) -> str:
            parts = []
            if self.title:
                parts.append(self.title)
            if self._text:
                parts.append(self._text)
            return "\n\n".join(parts) if parts else self._text

    return _FakeContent(text, language, title)


# ═══════════════════════════════════════════════════════════════════════════════
# GET /status — стан всього pipeline
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/status", summary="Стан scoring pipeline та vector store")
async def pipeline_status(
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """
    Повертає детальний стан pipeline:
      - чи ініціалізований CompositeScoringService
      - чи ініціалізований ProfileLearner
      - кількість векторів у interest_profile
      - розмірність ембеддингів

    Використовуй цей endpoint ПЕРШИМ при діагностиці.
    Якщо profile_learner_ready=false → лайки не зберігаються у ChromaDB.
    """
    result: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "composite_scoring_ready": container._composite_scoring is not None,
        "profile_learner_ready": container._profile_learner is not None,
        "tagger_ready": container._tagger is not None,
        "chroma_client_ready": container._chroma_client is not None,
    }

    # Додаткова інформація якщо pipeline готовий
    if container._profile_learner is not None:
        with contextlib.suppress(Exception):
            profile_repo = _get_profile_repo(container)
            count = await profile_repo.count()
            result["profile_vector_count"] = count
            result["cold_start"] = count == 0

    if container._profile_learner is not None:
        with contextlib.suppress(Exception):
            embedder = _get_embedder(container)
            result["embedding_dimensions"] = getattr(embedder, "_dim", "unknown")
            result["embedding_model"] = getattr(embedder, "_model_name", "unknown")

    # Перевіряємо чи підключений geo_filter до composite
    if container._composite_scoring is not None:
        cs = container._composite_scoring
        result["bm25_min_threshold"] = getattr(cs, "_bm25_min_threshold", "?")
        result["bm25_weight"] = getattr(cs, "_bm25_weight", "?")
        result["embed_weight"] = getattr(cs, "_embed_weight", "?")

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# GET /profile/count
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/profile/count", summary="Кількість векторів у interest_profile")
async def profile_count(
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """
    Повертає кількість збережених векторів у ChromaDB interest_profile.

    count=0 → cold start, embeddings scoring завжди повертає COLD_START_SCORE=0.55.
    """
    profile_repo = _get_profile_repo(container)
    count = await profile_repo.count()
    return {
        "count": count,
        "cold_start": count == 0,
        "max_profile_size": 500,
        "fill_percent": round(count / 500 * 100, 1),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# GET /profile/entries — список всіх записів
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/profile/entries", summary="Список записів у interest_profile")
async def profile_entries(
    limit: int = Query(default=50, ge=1, le=500, description="Максимум записів"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """
    Повертає metadata всіх статей у профілі інтересів (без самих векторів).

    Поля: article_id, score, tags, added_at.
    Корисно щоб побачити які статті реально потрапили у профіль після лайків.
    """
    profile_repo = _get_profile_repo(container)

    col = await profile_repo._get_collection()
    result = await col.get(include=["metadatas"])

    ids = result.get("ids", [])
    metas = result.get("metadatas", []) or []

    entries = [
        {
            "article_id": article_id,
            "score": meta.get("score"),
            "tags": meta.get("tags", "").split(",") if meta.get("tags") else [],
            "added_at": meta.get("added_at"),
        }
        for article_id, meta in zip(ids, metas)
    ]

    # Сортуємо за added_at DESC
    entries.sort(key=lambda x: x.get("added_at") or "", reverse=True)

    return {
        "total": len(entries),
        "showing": min(len(entries), limit),
        "entries": entries[:limit],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# GET /profile/centroid — інформація про центроїд
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/profile/centroid", summary="Інформація про центроїд interest_profile")
async def profile_centroid(
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """
    Повертає статистику центроїда профілю інтересів.

    centroid=null → cold start, профіль порожній.
    norm — має бути ~1.0 (вектор нормалізований).
    top_dims — перші 10 найбільших компонент (для налагодження).
    """
    profile_repo = _get_profile_repo(container)
    centroid = await profile_repo.get_centroid()

    if centroid is None:
        return {
            "exists": False,
            "message": "Профіль порожній (cold start). Додайте статті через лайки або /profile/add.",
        }

    norm = float(np.linalg.norm(centroid))
    top_indices = np.argsort(np.abs(centroid))[-10:][::-1].tolist()

    return {
        "exists": True,
        "dimensions": len(centroid),
        "norm": round(norm, 6),
        "mean": round(float(centroid.mean()), 6),
        "std": round(float(centroid.std()), 6),
        "min": round(float(centroid.min()), 6),
        "max": round(float(centroid.max()), 6),
        "top_10_dim_indices": top_indices,
        "top_10_dim_values": [round(float(centroid[i]), 4) for i in top_indices],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# GET /article/{article_id}/profile-check
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/article/{article_id}/profile-check",
    summary="Перевірити чи є стаття у interest_profile",
)
async def article_profile_check(
    article_id: UUID,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """
    Перевіряє чи збережений вектор статті у ChromaDB після лайку.

    Якщо liked=true але in_profile=false → проблема з ProfileLearner або init_async().
    """
    profile_repo = _get_profile_repo(container)
    in_profile = await profile_repo.contains(article_id)

    result: dict[str, Any] = {
        "article_id": str(article_id),
        "in_profile": in_profile,
    }

    if in_profile:
        # Витягуємо metadata для цієї статті
        col = await profile_repo._get_collection()
        data = await col.get(ids=[str(article_id)], include=["metadatas"])
        if data.get("metadatas"):
            meta = data["metadatas"][0]
            result["score"] = meta.get("score")
            result["tags"] = meta.get("tags", "").split(",") if meta.get("tags") else []
            result["added_at"] = meta.get("added_at")
    else:
        result["hint"] = (
            "Стаття відсутня у профілі. Можливі причини: "
            "(1) feedback ще не відправлено, "
            "(2) pipeline_learner_ready=false (перевір /status), "
            "(3) стаття була disliked і видалена."
        )

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# DELETE /profile/{article_id} — видалити конкретний вектор
# ═══════════════════════════════════════════════════════════════════════════════

@router.delete(
    "/profile/{article_id}",
    summary="Видалити вектор статті з interest_profile",
)
async def delete_from_profile(
    article_id: UUID,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """Видаляє вектор статті з ChromaDB interest_profile."""
    profile_repo = _get_profile_repo(container)
    removed = await profile_repo.remove(article_id)
    return {
        "article_id": str(article_id),
        "removed": removed,
        "message": "Вектор видалено" if removed else "Вектор не знайдено у профілі",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# DELETE /profile — очистити весь профіль
# ═══════════════════════════════════════════════════════════════════════════════

@router.delete("/profile", summary="Повністю очистити interest_profile (скинути до cold start)")
async def clear_profile(
    confirm: bool = Query(..., description="Передай confirm=true для підтвердження"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """
    НЕБЕЗПЕЧНА ОПЕРАЦІЯ: видаляє всі вектори з interest_profile.

    Після очищення система повертається до cold start:
    embeddings scoring завжди повертає 0.55 поки профіль не наповниться.
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Передай ?confirm=true для підтвердження очищення профілю.",
        )

    profile_repo = _get_profile_repo(container)
    col = await profile_repo._get_collection()

    # Отримуємо всі id і видаляємо
    result = await col.get(include=[])
    ids = result.get("ids", [])

    if ids:
        await col.delete(ids=ids)

    return {
        "cleared": True,
        "deleted_count": len(ids),
        "message": f"Видалено {len(ids)} векторів. Профіль у стані cold start.",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# POST /profile/add — вручну додати текст у профіль
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/profile/add", summary="Вручну додати текст до interest_profile")
async def add_to_profile(
    body: ManualAddRequest,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """
    Додає довільний текст у ChromaDB interest_profile.

    Корисно для:
      - ручного seed профілю під час розробки
      - тестування що scoring змінюється після додавання

    article_id генерується автоматично якщо не вказано.
    """
    learner = _get_profile_learner(container)
    article_id = body.article_id or uuid4()

    t0 = time.perf_counter()
    await learner.add_to_profile(
        article_id=article_id,
        content_text=body.text,
        score=body.score,
        tags=body.tags,
    )
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    profile_repo = _get_profile_repo(container)
    new_count = await profile_repo.count()

    return {
        "added": True,
        "article_id": str(article_id),
        "score": body.score,
        "tags": body.tags,
        "profile_count_after": new_count,
        "elapsed_ms": elapsed_ms,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# POST /score — скорувати довільний текст
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/score", summary="Скорувати довільний текст через повний pipeline")
async def score_text(
    body: ScoreRequest,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """
    Запускає повний CompositeScoringService (BM25 + Embeddings + Geo) для тестового тексту.

    Корисно для:
      - перевірки що певна стаття пройде threshold
      - порівняння score до і після наповнення профілю лайками
      - налагодження порогів

    Також окремо повертає BM25, embeddings та geo scores.
    """
    scoring = _get_scoring(container)
    content = _make_fake_content(body.text, body.language, body.title)

    t0 = time.perf_counter()

    # Повний composite score
    final_score = await scoring.score(content)
    elapsed_total = round((time.perf_counter() - t0) * 1000, 1)

    # BM25 окремо
    bm25_score = None
    bm25_ms = 0
    with contextlib.suppress(Exception):
        t1 = time.perf_counter()
        bm25_score = await scoring._bm25.score(content)
        bm25_ms = round((time.perf_counter() - t1) * 1000, 1)

    # Embeddings окремо
    embed_score = None
    embed_ms = 0
    with contextlib.suppress(Exception):
        t2 = time.perf_counter()
        embed_score = await scoring._embeddings.score(content)
        embed_ms = round((time.perf_counter() - t2) * 1000, 1)

    # Geo аналіз
    geo_result = None
    with contextlib.suppress(Exception):
        geo = scoring._geo_filter
        gr = geo.analyze(body.text, body.language)
        geo_result = {
            "multiplier": gr.multiplier,
            "geo_score": round(gr.geo_score, 4),
            "geo_hits": gr.geo_hits,
            "matched_signals": gr.matched_signals,
            "reason": gr.reason,
        }

    # Інформація про профіль для контексту
    profile_count = None
    cold_start = None
    with contextlib.suppress(Exception):
        profile_repo = _get_profile_repo(container)
        profile_count = await profile_repo.count()
        cold_start = profile_count == 0

    from src.config.settings import get_settings
    cfg = get_settings()
    threshold = cfg.filtering.default_threshold

    return {
        "input": {
            "text_length": len(body.text),
            "language": body.language,
            "title": body.title or None,
        },
        "scores": {
            "final": round(final_score, 4),
            "bm25_adjusted": round(bm25_score, 4) if bm25_score is not None else None,
            "embeddings": round(embed_score, 4) if embed_score is not None else None,
            "geo": geo_result,
        },
        "decision": {
            "threshold": threshold,
            "accepted": final_score >= threshold,
            "margin": round(final_score - threshold, 4),
        },
        "profile": {
            "count": profile_count,
            "cold_start": cold_start,
        },
        "timing_ms": {
            "total": elapsed_total,
            "bm25": bm25_ms if bm25_score is not None else None,
            "embeddings": embed_ms if embed_score is not None else None,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# POST /compare — cosine similarity між двома текстами
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/compare", summary="Cosine similarity між двома текстами")
async def compare_texts(
    body: CompareRequest,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """
    Кодує два тексти через Embedder і повертає cosine similarity.

    Корисно для перевірки що схожі тексти справді мають high similarity
    і різні тексти мають low similarity.

    similarity=1.0 → ідентичний зміст
    similarity=0.0 → абсолютно різний зміст
    similarity<0   → теоретично можливо, clip до 0.0 у scoring
    """
    embedder = _get_embedder(container)

    t0 = time.perf_counter()
    vec_a = embedder.encode_passage(body.text_a)
    vec_b = embedder.encode_passage(body.text_b)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    similarity = float(embedder.cosine_similarity(vec_a, vec_b))
    clipped = max(0.0, similarity)

    return {
        "similarity_raw": round(similarity, 4),
        "similarity_clipped": round(clipped, 4),
        "interpretation": _interpret_similarity(clipped),
        "vector_dim": len(vec_a),
        "elapsed_ms": elapsed_ms,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# POST /geo — аналіз geo-фільтру
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/geo", summary="Аналіз GeoRelevanceFilter для тексту")
async def geo_analyze(
    body: GeoAnalyzeRequest,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """
    Запускає GeoRelevanceFilter.analyze() і повертає детальний результат.

    Показує:
      - які гео-сигнали знайдено у тексті
      - geo_score (частка від загальної кількості слів)
      - multiplier що буде застосовано до фінального score
      - причину вибору multiplier

    Корисно для налагодження чому стаття з певної мови отримує penalty.
    """
    scoring = _get_scoring(container)
    geo = scoring._geo_filter

    gr = geo.analyze(body.text, body.language)

    return {
        "language": gr.language,
        "geo_score": round(gr.geo_score, 4),
        "geo_hits": gr.geo_hits,
        "matched_signals": gr.matched_signals,
        "multiplier": gr.multiplier,
        "reason": gr.reason,
        "thresholds": {
            "geo_self_threshold": geo._geo_self_threshold,
            "geo_weak_threshold": geo._geo_weak_threshold,
            "base_multiplier": geo._base_multiplier,
            "foreign_multiplier": geo._foreign_multiplier,
        },
        "word_count": len(body.text.split()),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# POST /feedback-trace — трасувати що станеться при feedback
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/feedback-trace", summary="Трасування: що відбудеться при лайку/дизлайку")
async def feedback_trace(
    body: FeedbackTraceRequest,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """
    Діагностика проблеми "лайк не додається до векторного профілю".

    Перевіряє:
      1. Чи ініціалізований profile_learner
      2. Чи стаття вже є у профілі
      3. Що станеться при liked=true (add_to_profile) або liked=false (remove)
      4. Стан профілю до і після операції

    НЕ виконує реальних змін у БД — тільки перевіряє стан.
    Для реального додавання використовуй /profile/add або POST /articles/{id}/feedback.
    """
    result: dict[str, Any] = {
        "article_id": str(body.article_id),
        "liked": body.liked,
        "checks": {},
    }

    # Перевірка 1: pipeline готовий?
    learner_ready = container._profile_learner is not None
    result["checks"]["pipeline_ready"] = {
        "ok": learner_ready,
        "detail": (
            "ProfileLearner ініціалізований" if learner_ready
            else "⚠️ ProfileLearner = None! init_async() не викликано або завершилось з помилкою. "
                 "Feedback зберігається в PostgreSQL але НЕ у ChromaDB."
        ),
    }

    if not learner_ready:
        result["verdict"] = "BROKEN: лайки не потрапляють у vector store"
        return result

    # Перевірка 2: стаття вже є у профілі?
    profile_repo = _get_profile_repo(container)
    in_profile_before = await profile_repo.contains(body.article_id)
    profile_count_before = await profile_repo.count()

    result["checks"]["current_state"] = {
        "in_profile": in_profile_before,
        "profile_total_count": profile_count_before,
    }

    # Прогноз дії
    if body.liked:
        result["checks"]["expected_action"] = {
            "action": "add_to_profile(score=1.0)",
            "will_add": True,
            "will_update_if_exists": in_profile_before,
            "note": (
                "Вектор буде додано або оновлено з score=1.0. "
                "Центроїд зміниться при наступному get_centroid()."
            ),
        }
    else:
        result["checks"]["expected_action"] = {
            "action": "remove_from_profile()",
            "will_remove": in_profile_before,
            "note": (
                "Вектор буде видалено з профілю (якщо є). "
                "Наступний scoring не враховуватиме цей вектор у центроїді."
                if in_profile_before
                else "Стаття відсутня у профілі — remove() поверне False, нічого не відбудеться."
            ),
        }

    # Перевірка 3: чи є стаття у PostgreSQL (через article repo)
    try:
        async with container.db_session() as session:
            article_repo = container.article_repo(session)
            article = await article_repo.get(body.article_id)
        result["checks"]["article_in_postgres"] = {
            "found": article is not None,
            "status": getattr(article, "status", None) if article else None,
            "relevance_score": getattr(article, "relevance_score", None) if article else None,
        }
        if article is None:
            result["checks"]["article_in_postgres"]["warning"] = (
                "Стаття не знайдена у PostgreSQL — submit_feedback поверне 404."
            )
    except Exception as exc:
        result["checks"]["article_in_postgres"] = {"error": str(exc)}

    result["verdict"] = (
        "OK: pipeline готовий, feedback буде оброблено коректно"
        if learner_ready
        else "BROKEN"
    )

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _interpret_similarity(sim: float) -> str:
    if sim >= 0.90:
        return "дуже висока схожість (майже ідентичний зміст)"
    elif sim >= 0.75:
        return "висока схожість (схожа тема)"
    elif sim >= 0.55:
        return "помірна схожість (пов'язані теми)"
    elif sim >= 0.35:
        return "слабка схожість (частково пов'язані)"
    else:
        return "низька схожість (різний зміст)"