# src/infrastructure/tagging/composite_tagger.py
"""
CompositeTagger — композитний шар тегування.

Об'єднує результати декількох тегерів (наприклад, CategoryTagger на базі BM25/keywords 
та EmbeddingTagger на базі семантичного пошуку/LLM), усуваючи дублікати.

Гарантія для фронтенду: tag() повертає ВИКЛЮЧНО теги зі спільного словника
tag_vocabulary.ALLOWED_TAGS. Будь-які "сторонні" значення (англійські
internal-id, помилки мапінгу тощо), якщо вони раптом просочаться з одного
з тегерів, тут відфільтровуються — це останній рубіж захисту.
"""
from typing import Protocol, Optional
import logging

from src.infrastructure.tagging.tag_vocabulary import ALLOWED_TAGS

logger = logging.getLogger(__name__)

class ITagger(Protocol):
    """
    Протокол для всіх тегерів у системі. 
    Сумісний з CategoryTagger та EmbeddingTagger через duck typing.
    """
    def tag(self, text: str) -> list[str]:
        ...


class CompositeTagger:
    """
    Об'єднує результати різних тегерів для отримання єдиного набору унікальних тегів.
    """

    def __init__(
        self,
        category_tagger: Optional[ITagger] = None,
        embedding_tagger: Optional[ITagger] = None,
    ) -> None:
        """
        Ініціалізація композитного тегера.
        
        :param category_tagger: Тегер на основі фіксованих категорій (BM25 + keywords).
        :param embedding_tagger: Тегер на основі векторних вкладень або іншої ML-моделі (опціонально).
        """
        self._category_tagger = category_tagger
        self._embedding_tagger = embedding_tagger

    def tag(self, text: str) -> list[str]:
        """
        Проганяє текст через усі доступні тегери та об'єднує результати.
        
        :param text: Текст статті для тегування.
        :return: Відсортований список унікальних тегів (тільки з ALLOWED_TAGS).
        """
        if not text or not text.strip():
            return []

        combined_tags: set[str] = set()

        # 1. Отримуємо теги від CategoryTagger
        if self._category_tagger:
            try:
                cat_tags = self._category_tagger.tag(text)
                combined_tags.update(cat_tags)
            except Exception as e:
                logger.error("Помилка під час виконання CategoryTagger: %s", e, exc_info=True)

        # 2. Отримуємо теги від EmbeddingTagger
        if self._embedding_tagger:
            try:
                emb_tags = self._embedding_tagger.tag(text)
                combined_tags.update(emb_tags)
            except Exception as e:
                logger.error("Помилка під час виконання EmbeddingTagger: %s", e, exc_info=True)

        # ── Санітизація: пропускаємо лише канонічні теги ─────────────────────
        # Якщо щось "втекло" поза ALLOWED_TAGS (наприклад, забули оновити
        # мапінг у одному з тегерів) — логуємо warning, щоб помітити баг,
        # але НЕ показуємо "сирий" тег користувачу.
        invalid_tags = combined_tags - ALLOWED_TAGS
        if invalid_tags:
            logger.warning(
                "CompositeTagger: відфільтровано теги поза ALLOWED_TAGS: %s",
                invalid_tags,
            )
            combined_tags &= ALLOWED_TAGS

        # Повертаємо відсортований список для стабільного порядку (зручно для тестів та фронтенду)
        return sorted(combined_tags)