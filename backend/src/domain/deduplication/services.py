# domain/deduplication/dedup_service.py
"""
DeduplicationDomainService — чиста доменна логіка.

Що тут є:
  - перевірка exact duplicate за ContentHash
  - перевірка near-duplicate за MinHash Jaccard
  - валідація мінімальних вимог до контенту

Чого тут НЕМАЄ:
  - SQL запитів (це робота репозиторію)
  - HTTP
  - asyncio (цей сервіс синхронний — обчислення, не I/O)

MinHash — probabilistic структура даних для оцінки Jaccard similarity
між множинами n-грам без порівняння кожного з кожним (O(1) vs O(n)).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .exceptions import InvalidContentError
from .value_objects import ContentHash


# ── MinHash ───────────────────────────────────────────────────────────────────

@dataclass
class MinHashSignature:
    """
    MinHash підпис тексту.

    signature — список з num_perm мінімальних хешів.
    Jaccard(A, B) ≈ |{i: sig_A[i] == sig_B[i]}| / num_perm
    """
    signature: list[int]
    num_perm: int

    def jaccard(self, other: "MinHashSignature") -> float:
        if self.num_perm != other.num_perm:
            raise ValueError(
                f"num_perm mismatch: {self.num_perm} vs {other.num_perm}"
            )
        matches = sum(a == b for a, b in zip(self.signature, other.signature))
        return matches / self.num_perm


class DeduplicationDomainService:
    """
    Чистий доменний сервіс.

    Використовується в DeduplicateRawArticleUseCase.
    Не залежить від БД — тільки від вхідних даних.
    """

    MIN_TITLE_LEN = 5
    MIN_BODY_LEN  = 50
    NGRAM_SIZE    = 3  # tri-gram shingles

    def __init__(self, num_perm: int = 128) -> None:
        self._num_perm = num_perm
        # Генеруємо стабільні коефіцієнти для universal hashing
        # a*x + b mod p — класична схема MinHash
        self._a, self._b = _generate_hash_params(num_perm)

    # ── Валідація контенту ────────────────────────────────────────────────────

    def validate_content(self, title: str, body: str) -> None:
        """
        Кидає InvalidContentError якщо контент не задовольняє
        мінімальним вимогам.

        Виклик до будь-якої іншої перевірки.
        """
        if len(title.strip()) < self.MIN_TITLE_LEN:
            raise InvalidContentError(
                f"Title too short: {len(title.strip())} chars "
                f"(minimum {self.MIN_TITLE_LEN})"
            )
        if len(body.strip()) < self.MIN_BODY_LEN:
            raise InvalidContentError(
                f"Body too short: {len(body.strip())} chars "
                f"(minimum {self.MIN_BODY_LEN})"
            )

    # ── Exact duplicate ───────────────────────────────────────────────────────

    def compute_hash(self, title: str, body: str) -> ContentHash:
        """Обчислити ContentHash для пари title+body."""
        return ContentHash.from_content(title, body)

    def is_exact_duplicate(
        self,
        candidate_hash: ContentHash,
        existing_hash: ContentHash,
    ) -> bool:
        """Точне порівняння хешів."""
        return candidate_hash.value == existing_hash.value

    # ── Near-duplicate (MinHash) ──────────────────────────────────────────────

    def compute_minhash(self, title: str, body: str) -> MinHashSignature:
        """
        Обчислити MinHash підпис для тексту.

        Алгоритм:
          1. Токенізувати текст в tri-gram shingles
          2. Для кожного з num_perm хеш-функцій знайти мінімум по всіх шинглах
          3. Результат — вектор з num_perm мінімумів
        """
        text = _normalize_for_minhash(f"{title} {body}")
        shingles = _get_shingles(text, self.NGRAM_SIZE)

        if not shingles:
            # Якщо текст занадто короткий — повертаємо нульовий підпис
            return MinHashSignature(
                signature=[0] * self._num_perm,
                num_perm=self._num_perm,
            )

        _MERSENNE_PRIME = (1 << 61) - 1
        _MAX_HASH = (1 << 32) - 1

        signature = []
        for i in range(self._num_perm):
            min_hash = _MAX_HASH
            for shingle_hash in shingles:
                h = (self._a[i] * shingle_hash + self._b[i]) % _MERSENNE_PRIME
                h = h & _MAX_HASH
                if h < min_hash:
                    min_hash = h
            signature.append(min_hash)

        return MinHashSignature(signature=signature, num_perm=self._num_perm)

    def is_near_duplicate(
        self,
        candidate: MinHashSignature,
        existing: MinHashSignature,
        threshold: float,
    ) -> tuple[bool, float]:
        """
        Перевірити чи є near-duplicate.

        Returns:
            (is_duplicate, similarity_score)
        """
        similarity = candidate.jaccard(existing)
        return similarity >= threshold, similarity


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize_for_minhash(text: str) -> str:
    """Нормалізація для MinHash: lowercase, тільки літери і цифри."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _get_shingles(text: str, n: int) -> set[int]:
    """
    Отримати множину n-gram shingles як хеші.

    "hello world" з n=3 → {"hel", "ell", "llo", "lo ", ...}
    Хешуємо рядки в int для ефективності.
    """
    if len(text) < n:
        return {hash(text)}
    return {hash(text[i:i+n]) & 0xFFFFFFFF for i in range(len(text) - n + 1)}


def _generate_hash_params(num_perm: int) -> tuple[list[int], list[int]]:
    """
    Генерує стабільні коефіцієнти a, b для universal hashing.
    Використовує seed=42 для детермінізму між перезапусками.
    """
    import random
    rng = random.Random(42)
    _MAX = (1 << 61) - 1
    a = [rng.randint(1, _MAX) for _ in range(num_perm)]
    b = [rng.randint(0, _MAX) for _ in range(num_perm)]
    return a, b
