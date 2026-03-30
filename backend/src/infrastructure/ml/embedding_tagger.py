# infrastructure/ml/embedding_tagger.py
"""
EmbeddingTagger — замінює ArticleClassificationService.

Підхід: zero-shot через cosine similarity.
  1. При старті кодуємо описи тегів (раз назавжди, кешується)
  2. Для кожної статті — кодуємо текст
  3. Порівнюємо з кожним тегом → similarity
  4. Повертаємо теги де similarity >= threshold

Переваги над keyword matching:
  - Розуміє "удар по інфраструктурі" = war (без слова "війна")
  - Мультимовне: та сама логіка для UA/EN/PL/DE тощо
  - Легко додати новий тег — тільки один рядок опису

Теги і їх семантичні описи (навмисно РОЗЛОГІ — більше контексту):
  Описи мають бути тією мовою яку розуміє модель (EN або UA,
  multilingual-e5 однаково добре).
"""
from __future__ import annotations

import logging

import numpy as np

from src.infrastructure.ml.embedder import Embedder

logger = logging.getLogger(__name__)


# ─── Словник тегів ────────────────────────────────────────────────────────────
# key   = назва тегу (зберігається в БД)
# value = семантичний опис для zero-shot (довільна мова, краще EN або UA)
#
# Поради для опису:
#   - Перелічуй конкретні слова/концепції, не абстракції
#   - 10-30 слів — оптимально
#   - Якщо тег охоплює кілька аспектів — додай їх через кому

TAG_DESCRIPTIONS: dict[str, str] = {
    "war": (
        "війна збройний конфлікт бойові дії фронт атака удар ракети дрони БПЛА "
        "ЗСУ армія військові окупація наступ оборона снаряди артилерія "
        "war military attack missile drone strike combat troops offensive defense"
    ),
    "politics": (
        "політика президент уряд парламент вибори депутат міністр закон "
        "рішення влада заява скандал відставка коаліція опозиція "
        "politics president government parliament election minister law decision scandal"
    ),
    "diplomacy": (
        "дипломатія переговори санкції міжнародні відносини саміт зустріч "
        "угода договір посол союзники НАТО ЄС ООН "
        "diplomacy negotiations sanctions summit meeting agreement treaty ambassador NATO EU"
    ),
    "economy": (
        "економіка фінанси ВВП інфляція ринок бюджет торгівля інвестиції "
        "банк валюта курс акції кредит борг податки "
        "economy finance GDP inflation market budget trade investment bank currency"
    ),
    "energy": (
        "енергетика газ нафта електроенергія АЕС ядерна електростанція "
        "блекаут відключення світла відновлювальна енергія сонячна вітрова "
        "energy gas oil electricity nuclear power plant blackout renewable solar wind"
    ),
    "society": (
        "суспільство люди протести демонстрації права людини біженці "
        "міграція демографія культура освіта медицина охорона здоров'я "
        "society people protests human rights refugees migration culture education healthcare"
    ),
    "technology": (
        "технології штучний інтелект AI стартап кібербезпека хакери "
        "програмне забезпечення цифровізація інновації блокчейн "
        "technology artificial intelligence AI startup cybersecurity hacker software digital innovation"
    ),
    "crime": (
        "злочин корупція арешт затримання вирок суд поліція прокуратура "
        "розслідування хабар шахрайство вбивство "
        "crime corruption arrest court police prosecutor investigation fraud murder"
    ),
    "humanitarian": (
        "гуманітарна допомога евакуація постраждалі жертви цивільні "
        "відновлення відбудова волонтери допомога "
        "humanitarian aid evacuation victims civilians reconstruction volunteers relief"
    ),
}

# Поріг схожості для присвоєння тегу
# 0.35 — досить м'який (менше пропусків, більше false positive)
# 0.45 — суворий (менше шуму, можливі пропуски)
DEFAULT_THRESHOLD = 0.40


class EmbeddingTagger:
    """
    Zero-shot тегер на основі cosine similarity.

    Singleton через Embedder.instance() — модель завантажується один раз.

    Приклад використання:
        tagger = EmbeddingTagger()
        tags = tagger.tag("Ракетний удар по Харкову: зруйновано інфраструктуру")
        # → ["war", "humanitarian"]
    """

    def __init__(
        self,
        embedder: Embedder | None = None,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        self._embedder = embedder or Embedder.instance()
        self._threshold = threshold
        # Кешуємо вектори описів тегів при ініціалізації
        self._tag_vectors: dict[str, np.ndarray] = self._build_tag_vectors()
        logger.info(
            "EmbeddingTagger initialized: %d tags, threshold=%.2f",
            len(self._tag_vectors), threshold,
        )

    def _build_tag_vectors(self) -> dict[str, np.ndarray]:
        """
        Кодуємо описи тегів як query (бо порівнюємо з passage статті).
        Робиться ОДИН РАЗ при старті.
        """
        tags = list(TAG_DESCRIPTIONS.keys())
        descriptions = list(TAG_DESCRIPTIONS.values())
        vectors = self._embedder.encode_batch(descriptions, is_query=True)
        return {tag: vectors[i] for i, tag in enumerate(tags)}

    def tag(self, text: str) -> list[str]:
        """
        Повертає список тегів для тексту статті.

        Args:
            text: повний текст статті (title + body).

        Returns:
            Відсортований список тегів (за score DESC).
            Порожній список якщо нічого не підходить.
        """
        if not text or not text.strip():
            return []

        article_vec = self._embedder.encode_passage(text)

        scored: list[tuple[str, float]] = []
        for tag_name, tag_vec in self._tag_vectors.items():
            sim = self._embedder.cosine_similarity(article_vec, tag_vec)
            if sim >= self._threshold:
                scored.append((tag_name, sim))

        # Сортуємо за схожістю DESC
        scored.sort(key=lambda x: x[1], reverse=True)

        if scored:
            logger.debug(
                "EmbeddingTagger: top tags %s",
                [(t, f"{s:.3f}") for t, s in scored[:3]],
            )

        return [tag for tag, _ in scored]

    def tag_with_scores(self, text: str) -> dict[str, float]:
        """
        Те саме що tag() але повертає {tag: score} для діагностики.
        Корисно для дебагу та майбутнього fine-tuning.
        """
        if not text or not text.strip():
            return {}

        article_vec = self._embedder.encode_passage(text)
        return {
            tag_name: self._embedder.cosine_similarity(article_vec, tag_vec)
            for tag_name, tag_vec in self._tag_vectors.items()
        }