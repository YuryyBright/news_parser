# infrastructure/embeddings/embedding_service.py
"""
EmbeddingServiceAdapter — реалізує IEmbeddingService.

Використовує sentence-transformers (той самий стек що article_vector_repo.py).
Модель: intfloat/multilingual-e5-small (1024-dim) — збігається з settings.embedding.

Адаптер обгортає НАЯВНИЙ клас EmbeddingService (якщо він є в проекті)
або використовує sentence-transformers напряму.

Lazy initialization: модель завантажується при першому виклику embed(),
не при старті застосунку — зменшує час cold start.

Thread safety: to_thread для синхронного encode().
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import numpy as np

from src.application.ports.rag_ports import IEmbeddingService

logger = logging.getLogger(__name__)


class SentenceTransformerEmbeddingService(IEmbeddingService):
    """
    IEmbeddingService через sentence-transformers.

    Використовується для embed і чанків .docx, і запитів пошуку.
    Та сама модель що і для article_vector_repo → вектори сумісні.

    Args:
        model_name:  назва моделі HuggingFace
        device:      "cpu" | "cuda" | "mps" (auto якщо None)
        batch_size:  кількість рядків за один encode() call
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        device: str | None = None,
        batch_size: int = 64,
    ) -> None:
        self._model_name = model_name
        self._device     = device
        self._batch_size = batch_size
        self._model: Any = None  # lazy init

    def _get_model(self):
        """Lazy load моделі (thread-safe через asyncio.to_thread)."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                raise ImportError(
                    "sentence-transformers is required: "
                    "pip install sentence-transformers"
                )
            logger.info("[embedding] Loading model: %s", self._model_name)
            self._model = SentenceTransformer(self._model_name, device=self._device)
            logger.info(
                "[embedding] Model loaded: %s  device=%s  dim=%d",
                self._model_name,
                self._model.device,
                self._model.get_sentence_embedding_dimension(),
            )
        return self._model

    async def embed(self, texts: list[str]) -> list[np.ndarray]:
        """
        Векторизує список текстів.

        Запускає encode() в окремому thread (не блокує event loop).
        Повертає список numpy array (float32).
        """
        if not texts:
            return []

        def _encode() -> np.ndarray:
            model = self._get_model()
            # intfloat/multilingual-e5 вимагає prefix для passage
            prefixed = [f"passage: {t}" for t in texts]
            return model.encode(
                prefixed,
                batch_size=self._batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )

        matrix: np.ndarray = await asyncio.to_thread(_encode)
        return [matrix[i].astype(np.float32) for i in range(len(matrix))]

    async def embed_one(self, text: str) -> np.ndarray:
        """
        Векторизує один текст (запит пошуку).

        Для запитів використовується prefix "query: " (відповідно до e5 spec).
        """
        def _encode_query() -> np.ndarray:
            model = self._get_model()
            result = model.encode(
                [f"query: {text}"],
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return result[0].astype(np.float32)

        return await asyncio.to_thread(_encode_query)


class ExistingEmbeddingServiceAdapter(IEmbeddingService):
    """
    Адаптер для НАЯВНОГО EmbeddingService в проекті
    (якщо він вже реалізований в infrastructure/embeddings/).

    Якщо в твоєму проекті вже є клас EmbeddingService з методами
    encode() або embed() — підключи його тут замість
    SentenceTransformerEmbeddingService через DI.

    Приклад у container.py:
        embedder = ExistingEmbeddingServiceAdapter(
            existing_service=container.embedding_service()
        )
    """

    def __init__(self, existing_service: Any) -> None:
        self._svc = existing_service

    async def embed(self, texts: list[str]) -> list[np.ndarray]:
        # Адаптуємо під API наявного сервісу
        if hasattr(self._svc, "embed"):
            return await self._svc.embed(texts)
        if hasattr(self._svc, "encode"):
            return await asyncio.to_thread(self._svc.encode, texts)
        raise NotImplementedError(
            f"Cannot adapt {type(self._svc)}: no embed() or encode() method"
        )

    async def embed_one(self, text: str) -> np.ndarray:
        vectors = await self.embed([text])
        return vectors[0]