# infrastructure/scoring/bm25_scoring_service.py
"""
BM25ScoringService — перший шар scoring (pre-filter).

Чому BM25 а не regex як у KeywordScoringService:
  - BM25 враховує TF (частоту терміну в документі) і IDF (рідкість терміну)
  - Не просто "є/немає" а реальний score → краща дискримінація
  - Стійкий до "spam" — сотня повторень "армія" не дасть score=1.0
  - Підходить для мультимовного тексту (токенізація по пробілах)

Бібліотека: rank_bm25 (pip install rank-bm25)
  Якщо недоступна — fallback на SimpleKeywordScoring (без BM25).

Корпус:
  Один документ на тему = список ключових слів.
  BM25 оцінює query (токени статті) відносно цього корпусу.
  Повертає score для кожного "документу" (теми) — беремо max.

Нормалізація:
  Raw BM25 score залежить від довжини документів у корпусі.
  Емпіричний max_score = 8.0 (для нашого корпусу, ~20 ключових слів/тему).
  min(raw / max_score, 1.0) → [0.0, 1.0].
  Якщо score занадто маленький — calibrate_max_score() підкаже реальне значення.
"""
from __future__ import annotations

import logging
import re

import numpy as np

from src.application.ports.scoring_service import IScoringService
from src.domain.ingestion.value_objects import ParsedContent

logger = logging.getLogger(__name__)

# ─── Корпус тем ───────────────────────────────────────────────────────────────
# Кожна тема = один "документ" у BM25 корпусі.
# Ключові слова — основи/стеми, щоб "військов" матчила "військовий"/"військових".
# Мікс UA + EN — модель BM25 мовонезалежна (просто токени).

_TOPIC_CORPUS_RAW: list[list[str]] = [
    # war_and_weapons
    [
        "війн", "збро", "ракет", "атак", "удар", "зсу", "армі", "військ",
        "оборон", "наступ", "дрон", "бпла", "фронт", "снаряд", "ппо",
        "окупац", "мобіліз", "бригад", "батальон", "обстріл",
        "war", "attack", "missile", "strike", "military", "drone", "artillery",
        "weapon", "troops", "army", "defense", "offensive", "combat", "ammo",
    ],
    # politics
    [
        "політ", "президент", "парламент", "уряд", "вибор", "депутат",
        "міністр", "санкці", "дипломат", "скандал", "відставк", "коаліц",
        "опозиц", "заяв", "законопроект",
        "election", "president", "parliament", "sanctions", "government",
        "diplomacy", "minister", "senate", "scandal", "resignation",
    ],
    # economy
    [
        "економік", "інфляці", "ввп", "ринок", "банк", "фінанс", "інвестиц",
        "бюджет", "валют", "акці", "торгівл", "кредит", "борг", "податк",
        "gdp", "inflation", "market", "trade", "bank", "finance", "investment",
        "budget", "currency", "stock", "debt", "tax",
    ],
    # diplomacy/international
    [
        "переговор", "саміт", "угод", "договір", "посол", "союзник",
        "нато", "євросоюз", "оон", "міжнародн",
        "negotiations", "summit", "agreement", "ambassador", "nato", "eu", "un",
        "international", "bilateral",
    ],
    # energy
    [
        "енергетик", "газ", "нафт", "електроенерг", "аес", "ядерн",
        "блекаут", "відключен", "світл", "відновлюван",
        "energy", "gas", "oil", "electricity", "nuclear", "blackout", "power",
        "renewable", "solar", "wind",
    ],
    # technology
    [
        "технологі", "штучний інтелект", "стартап", "кібер", "айті",
        "алгоритм", "блокчейн", "цифров", "хакер",
        "ai", "startup", "software", "cyber", "tech", "algorithm",
        "blockchain", "digital", "machine learning", "hacker",
    ],
    # society/humanitarian
    [
        "суспільств", "протест", "демонстрац", "права людини", "біженц",
        "міграц", "гуманітарн", "евакуац", "постраждал", "жертв",
        "society", "protest", "human rights", "refugees", "migration",
        "humanitarian", "evacuation", "victims", "civilian",
    ],
]

# Емпіричний максимальний raw BM25 score для нормалізації до [0,1]
# Підбирається calibrate_max_score() або вручну
_BM25_MAX_SCORE = 8.0


def _tokenize(text: str) -> list[str]:
    """
    Простий токенізатор: lowercase + split по non-word chars.
    Без стемінгу — BM25 матчить підрядки через substring check.
    """
    text = text.lower()
    # Розбиваємо по пробілах і знаках пунктуації
    tokens = re.split(r"[\s\W]+", text)
    return [t for t in tokens if len(t) > 2]


def _corpus_with_substrings(query_tokens: list[str], corpus: list[list[str]]) -> list[list[str]]:
    """
    BM25 потребує exact match токенів.
    Наш корпус містить основи ("армі"), а стаття — повні форми ("армією").
    Рішення: для кожного query token перевіряємо чи є він підрядком
    ключового слова corpus (або навпаки).
    Повертаємо модифікований корпус де ключові слова замінені на matched tokens.
    """
    expanded = []
    for doc_keywords in corpus:
        expanded_doc = []
        for kw in doc_keywords:
            # Якщо хоча б один query token починається з kw або kw — підрядок токену
            matched = [
                qt for qt in query_tokens
                if qt.startswith(kw) or kw.startswith(qt[:4]) or kw in qt
            ]
            expanded_doc.extend(matched if matched else [kw])
        expanded.append(expanded_doc)
    return expanded


class BM25ScoringService(IScoringService):
    """
    IScoringService через BM25.

    При score < 0.05 → стаття точно не по темі.
    При score >= 0.3 → потрапляє на embedding scoring.
    """

    def __init__(self, max_score: float = _BM25_MAX_SCORE) -> None:
        self._max_score = max_score
        self._bm25 = self._build_bm25()

    def _build_bm25(self):
        try:
            from rank_bm25 import BM25Okapi
            self._backend = "rank_bm25"
            return BM25Okapi(_TOPIC_CORPUS_RAW)
        except ImportError:
            logger.warning(
                "rank_bm25 not installed (pip install rank-bm25). "
                "Falling back to SimpleKeyword scoring."
            )
            self._backend = "simple"
            return None

    async def score(self, content: ParsedContent) -> float:
        text = content.full_text()
        if not text:
            return 0.0

        if self._backend == "simple":
            return self._simple_score(text)

        return self._bm25_score(text)

    def _bm25_score(self, text: str) -> float:
        """BM25 scoring з rank_bm25."""
        tokens = _tokenize(text)
        if not tokens:
            return 0.0

        # Розширюємо корпус для substring matching
        expanded_corpus = _corpus_with_substrings(tokens, _TOPIC_CORPUS_RAW)

        from rank_bm25 import BM25Okapi
        bm25 = BM25Okapi(expanded_corpus)
        scores = bm25.get_scores(tokens)

        raw = float(np.max(scores))
        normalized = min(raw / self._max_score, 1.0)

        logger.debug(
            "BM25: raw_max=%.3f normalized=%.3f tokens_count=%d",
            raw, normalized, len(tokens),
        )
        return normalized

    def _simple_score(self, text: str) -> float:
        """Fallback: стара логіка з KeywordScoringService."""
        text_lower = text.lower()
        matched = 0
        for keywords in _TOPIC_CORPUS_RAW:
            pattern = re.compile(
                r"(?:" + "|".join(re.escape(kw) for kw in keywords) + r")"
            )
            if pattern.search(text_lower):
                matched += 1
        return min(matched / len(_TOPIC_CORPUS_RAW), 1.0)

    def calibrate_max_score(self, sample_texts: list[str]) -> float:
        """
        Утиліта для калібрування _BM25_MAX_SCORE.
        Запусти на кількох "ідеально релевантних" статтях щоб знайти реальний max.

        Використання (один раз, у скрипті):
            svc = BM25ScoringService()
            max_s = svc.calibrate_max_score(sample_texts)
            print(f"Set _BM25_MAX_SCORE = {max_s:.1f}")
        """
        if self._backend != "rank_bm25":
            return self._max_score

        from rank_bm25 import BM25Okapi
        max_raw = 0.0
        for text in sample_texts:
            tokens = _tokenize(text)
            expanded = _corpus_with_substrings(tokens, _TOPIC_CORPUS_RAW)
            bm25 = BM25Okapi(expanded)
            scores = bm25.get_scores(tokens)
            max_raw = max(max_raw, float(np.max(scores)))

        logger.info("Calibrated BM25 max score: %.2f", max_raw)
        return max_raw