# infrastructure/scoring/keyword_scoring_service.py
"""
KeywordScoringService — реалізує IScoringService через keyword matching.

Простий але робочий алгоритм:
  - підраховує кількість тематичних ключових слів у тексті
  - нормалізує до [0.0, 1.0] відносно максимуму по категоріях

Application layer знає тільки про IScoringService.
Заміна на ML-модель не потребує змін у use cases.
"""
from __future__ import annotations

import re

from src.application.ports.scoring_service import IScoringService
from src.domain.ingestion.value_objects import ParsedContent

# Тематичні ключові слова (копіюємо логіку з ArticleClassificationService
# але тут вона використовується для scoring, а не тегування)
_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "war_and_weapons": [
        "війн", "збро", "ракет", "атак", "удар", "зсу", "армія", "військ",
        "оборон", "наступ", "дрон", "бпла", "фронт", "снаряд", "ппо",
        "war", "attack", "missile", "strike", "military", "drone", "artillery",
        "weapon", "troops", "army", "defense", "offensive", "combat",
    ],
    "politics": [
        "політ", "президент", "парламент", "уряд", "вибор", "депутат",
        "міністр", "санкці", "дипломат",
        "election", "president", "parliament", "sanctions", "government",
        "diplomacy", "minister", "senate",
    ],
    "economy": [
        "економік", "інфляці", "ввп", "ринок", "банк", "фінанс", "інвестиц",
        "бюджет", "валют", "акці",
        "gdp", "inflation", "market", "trade", "bank", "finance", "investment",
        "budget", "currency",
    ],
    "technology": [
        "технологі", "штучний інтелект", "стартап", "кібер", "айті",
        "алгоритм", "блокчейн", "цифров",
        "ai", "startup", "software", "cyber", "tech", "algorithm",
        "blockchain", "digital", "machine learning",
    ],
}

# Максимальна кількість матчів яку ми вважаємо "100% релевантно"
_MAX_HITS = 5


class KeywordScoringService(IScoringService):

    async def score(self, content: ParsedContent) -> float:
        """
        Підрахувати кількість тематичних категорій що є в тексті.
        Кожна категорія дає +0.25 до score, max = 1.0.

        Наприклад:
          - є war_and_weapons + politics → 0.5
          - є тільки technology → 0.25
          - немає жодної категорії → 0.0
        """
        text = content.full_text().lower()
        matched_categories = 0

        for _topic, keywords in _TOPIC_KEYWORDS.items():
            pattern = re.compile(
                r"(?:" + "|".join(re.escape(kw) for kw in keywords) + r")"
            )
            if pattern.search(text):
                matched_categories += 1

        # Нормалізуємо: 4 категорії = 1.0
        total_categories = len(_TOPIC_KEYWORDS)
        return min(matched_categories / total_categories, 1.0)