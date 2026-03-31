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
        # UA & EN (Original + Added)
        "війн", "збро", "ракет", "атак", "удар", "зсу", "армія", "військ", "оборон", "наступ", "дрон", "бпла", "фронт", "снаряд", "ппо", "окупант", "вторгнення",
        "war", "attack", "missile", "strike", "military", "drone", "artillery", "weapon", "troops", "army", "defense", "offensive", "combat", "invasion", "shelling", "uav",
        # Romanian (RO)
        "război", "armă", "muniți", "rachet", "atac", "lovitur", "armat", "militar", "defens", "ofensiv", "front", "obuz", "bombard", "invazi", "soldat", "tanc", "blindat",
        # Hungarian (HU)
        "háború", "fegyver", "lőszer", "rakéta", "támadás", "csapás", "katon", "sereg", "védelem", "offenzív", "front", "tüzérség", "drón", "invázió", "bombáz", "páncélos", "honvédelem",
        # Slovak (SK)
        "vojn", "zbraň", "muníci", "raket", "útok", "úder", "armád", "vojsk", "obran", "ofenzív", "front", "granát", "delostrelectvo", "invázi", "ostreľovan", "tank", "stíhač",
    ],
    "politics": [
        # UA & EN
        "політ", "президент", "парламент", "уряд", "вибор", "депутат", "міністр", "санкці", "дипломат", "корупці", "закон", "рада",
        "election", "president", "parliament", "sanctions", "government", "diplomacy", "minister", "senate", "policy", "corruption", "vote", "summit",
        # Romanian (RO)
        "politic", "președinte", "parlament", "guvern", "aleger", "deputat", "ministru", "sancțiun", "diplomaț", "corupți", "lege", "vot", "senat", "summit",
        # Hungarian (HU)
        "politik", "elnök", "parlament", "kormány", "választás", "képviselő", "miniszter", "szankció", "diplomácia", "korrupció", "törvény", "szavazat", "szenátus", "csúcstalálkozó",
        # Slovak (SK)
        "politi", "prezident", "parlament", "vlád", "voľb", "poslanec", "minister", "sankci", "diplomaci", "korupci", "zákon", "hlasovan", "senát", "samit",
    ],
    "economy": [
        # UA & EN
        "економік", "інфляці", "ввп", "ринок", "банк", "фінанс", "інвестиц", "бюджет", "валют", "акці", "кредит", "дефіцит", "експорт", "імпорт",
        "gdp", "inflation", "market", "trade", "bank", "finance", "investment", "budget", "currency", "stocks", "deficit", "export", "import", "crypto",
        # Romanian (RO)
        "economi", "inflați", "pib", "piață", "banc", "finanț", "investiți", "buget", "valut", "acțiun", "credit", "deficit", "export", "import", "curs valutar",
        # Hungarian (HU)
        "gazdaság", "infláció", "gdp", "piac", "bank", "pénzügy", "befektetés", "költségvetés", "valuta", "részvény", "hitel", "hiány", "export", "import", "árfolyam",
        # Slovak (SK)
        "ekonomika", "infláci", "hdp", "trh", "bank", "financi", "investíci", "rozpočet", "men", "akci", "úver", "deficit", "export", "import", "kurz",
    ],
    "technology": [
        # UA & EN
        "технологі", "штучний інтелект", "стартап", "кібер", "айті", "алгоритм", "блокчейн", "цифров", "софт", "розробка", "сервер",
        "ai", "startup", "software", "cyber", "tech", "algorithm", "blockchain", "digital", "machine learning", "hardware", "data", "cloud",
        # Romanian (RO)
        "tehnologi", "inteligență artificială", "startup", "ciber", "it", "algoritm", "digital", "software", "dezvoltare", "server", "date", "cloud", "automatiz",
        # Hungarian (HU)
        "technológi", "mesterséges intelligencia", "startup", "kiber", "informatika", "algoritmus", "digitális", "szoftver", "fejlesztés", "szerver", "adat", "felhő", "automatizálás",
        # Slovak (SK)
        "technológi", "umelá inteligencia", "startup", "kyber", "it", "algoritmus", "digitáln", "softvér", "vývoj", "server", "údaj", "cloud", "automatizáci",
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