# infrastructure/scoring/bm25_scoring_service.py
"""
BM25ScoringService — перший шар scoring (pre-filter).

Чому BM25 а не regex як у KeywordScoringService:
  - BM25 враховує TF (частоту терміну в документі) і IDF (рідкість терміну)
  - Не просто "є/немає" а реальний score → краща дискримінація
  - Стійкий до "spam" — сотня повторень "армія" не дасть score=1.0
  - Підходить для мультимовного тексту (токенізація по пробілах)

[ОНОВЛЕНО] Geo early-reject:
  Якщо BM25 score * geo_multiplier < bm25_geo_threshold → reject одразу.
  Тобто: стаття угорською про NATO (geo_mult=0.40) з BM25=0.10
    → 0.10 * 0.40 = 0.04 < 0.05 → reject без embeddings.
  Але стаття угорською про Угорщину в NATO (geo_mult=1.0) з BM25=0.10
    → 0.10 * 1.0 = 0.10 → проходить на embeddings.

  ParsedContent тепер має поле language (заповнюється ILanguageDetector раніше).
  Якщо language порожній — geo_multiplier=BASE_MULTIPLIER (не відкидаємо повністю).

Бібліотека: rank_bm25 (pip install rank-bm25)
  Якщо недоступна — fallback на SimpleKeywordScoring (без BM25).
"""
from __future__ import annotations

import logging
import re

import numpy as np

from src.application.ports.scoring_service import IScoringService
from src.domain.ingestion.value_objects import ParsedContent
from src.infrastructure.scoring.geo_relevance_filter import GeoRelevanceFilter

logger = logging.getLogger(__name__)

# ─── Корпус тем ───────────────────────────────────────────────────────────────
_TOPIC_CORPUS_RAW: list[list[str]] = [
    # war_and_weapons
    [
        "війн", "збро", "ракет", "атак", "удар", "зсу", "армі", "військ",
        "оборон", "наступ", "дрон", "бпла", "фронт", "снаряд", "ппо",
        "окупац", "мобіліз", "бригад", "батальон", "обстріл",
        "war", "attack", "missile", "strike", "military", "drone", "artillery",
        "weapon", "troops", "army", "defense", "offensive", "combat", "ammo",
        # HU
        "háború", "fegyver", "rakéta", "támadás", "katoná", "hadsereg",
        "védelm", "offenzív", "drón", "invázió",
        # SK
        "vojn", "zbraň", "raket", "útok", "armád", "vojsk", "obran", "ofenzív",
        # RO
        "război", "armă", "rachet", "atac", "armat", "militar", "defens", "ofensiv",
    ],
    # politics
    [
        "політ", "президент", "парламент", "уряд", "вибор", "депутат",
        "міністр", "санкці", "дипломат", "скандал", "відставк", "коаліц",
        "опозиц", "заяв", "законопроект",
        "election", "president", "parliament", "sanctions", "government",
        "diplomacy", "minister", "senate", "scandal", "resignation",
        # HU
        "választás", "elnök", "parlament", "kormány", "képviselő", "miniszter",
        "szankció", "botrány",
        # SK
        "voľby", "prezident", "parlament", "vlád", "poslanec", "minister", "sankci",
        # RO
        "aleger", "președinte", "parlament", "guvern", "deputat", "ministru", "sancțiun",
    ],
    # economy
    [
        "економік", "інфляці", "ввп", "ринок", "банк", "фінанс", "інвестиц",
        "бюджет", "валют", "акці", "торгівл", "кредит", "борг", "податк",
        "gdp", "inflation", "market", "trade", "bank", "finance", "investment",
        "budget", "currency", "stock", "debt", "tax",
        # HU
        "gazdaság", "infláció", "piac", "bank", "pénzügy", "befektetés",
        "költségvetés", "valuta", "részvény", "adó",
        # SK
        "ekonomika", "infláci", "trh", "bank", "financi", "investíci",
        "rozpočet", "mena", "akci", "daň",
        # RO
        "economi", "inflați", "piață", "banc", "finanț", "investiți",
        "buget", "valut", "acțiun", "impozit",
    ],
    # diplomacy/international
    [
        "переговор", "саміт", "угод", "договір", "посол", "союзник",
        "нато", "євросоюз", "оон", "міжнародн",
        "negotiations", "summit", "agreement", "ambassador", "nato", "eu", "un",
        "international", "bilateral",
        # HU
        "tárgyalás", "csúcstalálkozó", "megállapodás", "nagykövet", "szövetség",
        "nato", "európai unió", "ensz",
        # SK
        "rokovani", "samit", "dohod", "veľvyslanec", "spojenec",
        "nato", "európska únia", "osn",
        # RO
        "negocier", "summit", "acord", "ambasador", "alianță",
        "nato", "uniunea europeană", "onu",
    ],
    # energy
    [
        "енергетик", "газ", "нафт", "електроенерг", "аес", "ядерн",
        "блекаут", "відключен", "світл", "відновлюван",
        "energy", "gas", "oil", "electricity", "nuclear", "blackout", "power",
        "renewable", "solar", "wind",
        # HU
        "energia", "gáz", "olaj", "villamos", "atomerőmű", "nukleáris", "áramszünet",
        # SK
        "energetik", "plyn", "ropa", "elektrina", "atómová", "jadrový", "výpadok",
        # RO
        "energet", "gaze", "petrol", "electricitat", "nuclear", "întreruper",
    ],
    # technology
    [
        "технологі", "штучний інтелект", "стартап", "кібер", "айті",
        "алгоритм", "блокчейн", "цифров", "хакер",
        "ai", "startup", "software", "cyber", "tech", "algorithm",
        "blockchain", "digital", "machine learning", "hacker",
        # HU
        "technológi", "mesterséges intelligencia", "szoftver", "kiberbiztonság",
        # SK
        "technológi", "umelá inteligencia", "softvér", "kybernetick",
        # RO
        "tehnologi", "inteligență artificială", "software", "cibernetic",
    ],
    # society/humanitarian
    [
        "суспільств", "протест", "демонстрац", "права людини", "біженц",
        "міграц", "гуманітарн", "евакуац", "постраждал", "жертв",
        "society", "protest", "human rights", "refugees", "migration",
        "humanitarian", "evacuation", "victims", "civilian",
        # HU
        "társadalom", "tüntetés", "menekült", "migráció", "humanitárius",
        "evakuáció", "áldozat", "polgári",
        # SK
        "spoločnosť", "protest", "utečenec", "migráci", "humanitárn",
        "evakuáci", "obeť", "civilist",
        # RO
        "societat", "protest", "refugiat", "migrați", "umanitar",
        "evacuare", "victimă", "civil",
    ],
]

_BM25_MAX_SCORE = 8.0


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    tokens = re.split(r"[\s\W]+", text)
    return [t for t in tokens if len(t) > 2]


def _corpus_with_substrings(query_tokens: list[str], corpus: list[list[str]]) -> list[list[str]]:
    expanded = []
    for doc_keywords in corpus:
        expanded_doc = []
        for kw in doc_keywords:
            matched = [
                qt for qt in query_tokens
                if qt.startswith(kw) or kw.startswith(qt[:4]) or kw in qt
            ]
            expanded_doc.extend(matched if matched else [kw])
        expanded.append(expanded_doc)
    return expanded


class BM25ScoringService(IScoringService):
    """
    IScoringService через BM25 з geo early-reject.

    [ОНОВЛЕНО] Тепер враховує мову статті для гео-фільтрації.
    ParsedContent.language має бути заповнений до виклику score().
    Це робить ProcessArticlesUseCase через _detect_language() перед scoring.

    Якщо language порожній — GeoRelevanceFilter повертає BASE_MULTIPLIER (не reject).

    При score < bm25_geo_threshold після geo_mult → reject без embeddings.
    """

    def __init__(
        self,
        max_score: float = _BM25_MAX_SCORE,
        geo_filter: GeoRelevanceFilter | None = None,
    ) -> None:
        self._max_score = max_score
        self._geo_filter = geo_filter or GeoRelevanceFilter()
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

        # ── BM25 topic score ──────────────────────────────────────────────────
        if self._backend == "simple":
            raw_score = self._simple_score(text)
        else:
            raw_score = self._bm25_score(text)

        # ── Geo multiplier (early signal) ─────────────────────────────────────
        # BM25 не відкидає — він тільки сигналізує.
        # Фінальний reject за geo відбувається у CompositeScoringService.
        # Тут ми повертаємо raw_score * geo_mult щоб composite міг вирішити.
        language = getattr(content, "language", "") or ""
        geo_result = self._geo_filter.analyze(text, language)

        adjusted = raw_score * geo_result.multiplier

        logger.debug(
            "BM25: raw=%.3f geo_mult=%.2f adjusted=%.3f lang=%s reason=%s",
            raw_score, geo_result.multiplier, adjusted,
            geo_result.language, geo_result.reason,
        )
        return adjusted

    def _bm25_score(self, text: str) -> float:
        tokens = _tokenize(text)
        if not tokens:
            return 0.0

        expanded_corpus = _corpus_with_substrings(tokens, _TOPIC_CORPUS_RAW)

        from rank_bm25 import BM25Okapi
        bm25 = BM25Okapi(expanded_corpus)
        scores = bm25.get_scores(tokens)

        raw = float(np.max(scores))
        normalized = min(raw / self._max_score, 1.0)

        logger.debug(
            "BM25_raw: raw_max=%.3f normalized=%.3f tokens_count=%d",
            raw, normalized, len(tokens),
        )
        return normalized

    def _simple_score(self, text: str) -> float:
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