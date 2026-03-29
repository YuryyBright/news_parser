# domain/deduplication/value_objects.py
"""
Value objects для домену Deduplication.

ContentHash — центральний об'єкт дедуплікації.
Живе в домені, бо бізнес-правило "однаковий контент = дублікат"
є доменним інваріантом, а не деталлю інфраструктури.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from src.domain.shared.base_value_object import ValueObject
from src.domain.shared.exceptions import ValidationError


@dataclass(frozen=True)
class ContentHash(ValueObject):
    """
    SHA-256 хеш від нормалізованого title + body.

    Нормалізація (lowercase + strip whitespace) відбувається
    у фабричному методі — щоб два тексти з різними пробілами
    давали однаковий хеш.
    """
    value: str  # hex string, 64 chars

    def _validate(self) -> None:
        if len(self.value) != 64:
            raise ValidationError(
                f"ContentHash must be sha256 hex (64 chars), got {len(self.value)}"
            )
        if not all(c in "0123456789abcdef" for c in self.value):
            raise ValidationError("ContentHash must be lowercase hex string")

    @classmethod
    def from_content(cls, title: str, body: str) -> "ContentHash":
        """
        Фабричний метод — нормалізує і хешує.

        Нормалізація:
          - lowercase
          - collapse whitespace (кілька пробілів/переносів → один пробіл)
          - strip країв

        Так 'Hello  World' і 'hello world' дають однаковий хеш.
        """
        normalized = _normalize(title) + "\n" + _normalize(body)
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return cls(value=digest)

    def __str__(self) -> str:
        return self.value

    def short(self) -> str:
        """Перші 8 символів для логів."""
        return self.value[:8]


@dataclass(frozen=True)
class ParsedContent(ValueObject):
    """Контент, розпарсений з джерела до збереження."""
    title: str
    body: str
    url: str
    language: str = "unknown"
    published_at: object = None  # datetime | None

    def _validate(self) -> None:
        if not self.title.strip():
            raise ValidationError("ParsedContent.title cannot be empty")
        if not self.url.strip():
            raise ValidationError("ParsedContent.url cannot be empty")

    @property
    def content_hash(self) -> ContentHash:
        return ContentHash.from_content(self.title, self.body)


def _normalize(text: str) -> str:
    import re
    return re.sub(r"\s+", " ", text.lower()).strip()
