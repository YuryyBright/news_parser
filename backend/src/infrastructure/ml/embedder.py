# infrastructure/ml/embedder.py
"""
Embedder — тонка обгортка над sentence-transformers.

Чому окремий клас а не прямий виклик SentenceTransformer:
  - Singleton: модель завантажується один раз при старті (важка, ~500MB)
  - Lazy init: не вантажимо при імпорті, тільки при першому виклику
  - Легко замінити на vLLM endpoint — тільки цей файл
  - Дозволяє мокати в тестах без реальної моделі

Модель: intfloat/multilingual-e5-small
  - 118MB, підтримує 100+ мов включно з українською
  - Розмір вектора: 384
  - Prefix: "query: " для запитів, "passage: " для документів
  - https://huggingface.co/intfloat/multilingual-e5-small
"""
from __future__ import annotations

import logging
from functools import lru_cache

import numpy as np

logger = logging.getLogger(__name__)

# Константи моделі
MODEL_NAME = "intfloat/multilingual-e5-small"
EMBEDDING_DIM = 384
MAX_SEQ_LEN = 512  # токени, ~400 слів


class Embedder:
    """
    Синглтон-обгортка над SentenceTransformer.

    Використання:
        embedder = Embedder.instance()
        vec = embedder.encode_passage("текст статті...")
        vec = embedder.encode_query("тема: політика")
    """

    _instance: Embedder | None = None

    def __init__(self) -> None:
        # Відкладаємо імпорт — sentence_transformers важкий
        from sentence_transformers import SentenceTransformer
        logger.info("Loading embedding model: %s", MODEL_NAME)
        self._model = SentenceTransformer(MODEL_NAME)
        logger.info("Embedding model loaded (dim=%d)", EMBEDDING_DIM)

    @classmethod
    def instance(cls) -> "Embedder":
        """Повертає singleton. Перший виклик завантажує модель."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def encode_passage(self, text: str) -> np.ndarray:
        """
        Кодує документ/статтю.
        Prefix "passage: " — обов'язковий для multilingual-e5.
        Truncate до MAX_SEQ_LEN щоб не повільно.
        """
        truncated = self._truncate(text)
        vec = self._model.encode(
            f"passage: {truncated}",
            normalize_embeddings=True,  # L2 norm → cosine = dot product
            show_progress_bar=False,
        )
        return np.array(vec, dtype=np.float32)

    def encode_query(self, text: str) -> np.ndarray:
        """
        Кодує запит/тему/фразу.
        Prefix "query: " — обов'язковий для multilingual-e5.
        """
        vec = self._model.encode(
            f"query: {text}",
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.array(vec, dtype=np.float32)

    def encode_batch(self, texts: list[str], is_query: bool = False) -> np.ndarray:
        """
        Батч-кодування для тегів і профілів.
        Returns: np.ndarray shape (N, EMBEDDING_DIM), dtype=float32.
        """
        prefix = "query: " if is_query else "passage: "
        prefixed = [f"{prefix}{self._truncate(t)}" for t in texts]
        vecs = self._model.encode(
            prefixed,
            normalize_embeddings=True,
            batch_size=32,
            show_progress_bar=False,
        )
        return np.array(vecs, dtype=np.float32)

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """
        Cosine similarity між двома L2-нормованими векторами.
        Оскільки encode_* нормалізує — це просто dot product.
        """
        return float(np.dot(a, b))

    @staticmethod
    def _truncate(text: str, max_chars: int = 1500) -> str:
        """Обрізаємо символами — грубо але швидко перед encode."""
        return text[:max_chars] if len(text) > max_chars else text