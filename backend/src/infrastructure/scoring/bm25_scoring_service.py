# infrastructure/scoring/bm25_scoring_service.py
"""
BM25ScoringService — перший шар scoring (pre-filter).

Чому BM25 а не regex як у KeywordScoringService:
  - BM25 враховує TF (частоту терміну в документі) і IDF (рідкість терміну)
  - Не просто "є/немає" а реальний score → краща дискримінація
  - Стійкий до "spam" — сотня повторень "армія" не дасть score=1.0
  - Підходить для мультимовного тексту (токенізація по пробілах)

[СПРОЩЕНО] Geo early-reject повністю видалено.
  BM25 повертає чистий тематичний score без будь-яких гео-множників.
  Фільтрація виключно за тематичною релевантністю — geo не є нашою
  відповідальністю на цьому рівні.

[РОЗШИРЕНО] Корпус тем:
  war_and_weapons        — армія, фронт, зброя (UA/EN/HU/SK/RO)
  politics               — вибори, уряд, президент
  economy                — ВВП, ринки, санкції, торгівля
  diplomacy              — НАТО, ООН, саміти, договори
  energy                 — газ, нафта, АЕС, відновлювані
  technology             — ШІ, кібер, стартапи
  society                — права, біженці, протести
  geopolitics            — NEW: сфери впливу, великі держави, альянси
  security_intelligence  — NEW: спецслужби, шпигунство, гібридна війна
  nuclear_wmd            — NEW: ядерна загроза, МАГАТЕ, нерозповсюдження
  disinformation_info    — NEW: дезінформація, пропаганда, кібератаки
  sanctions_finance      — NEW: санкції, заморожені активи, SWIFT
  humanitarian_crisis    — NEW: МГП, гуманітарні коридори, військові злочини
  elections_democracy    — NEW: демократія, авторитаризм, вибори під тиском

Бібліотека: rank_bm25 (pip install rank-bm25)
  Якщо недоступна — fallback на SimpleKeywordScoring (без BM25).
"""
from __future__ import annotations

import logging
import re

import numpy as np

from src.application.ports.scoring_service import IScoringService
from src.domain.ingestion.value_objects import ParsedContent

logger = logging.getLogger(__name__)

# ─── Корпус тем ───────────────────────────────────────────────────────────────
_TOPIC_CORPUS_RAW: list[list[str]] = [

    # ── 0. war_and_weapons ────────────────────────────────────────────────────
    [
        # UA
        "війн", "збро", "ракет", "атак", "удар", "зсу", "армі", "військ",
        "оборон", "наступ", "дрон", "бпла", "фронт", "снаряд", "ппо",
        "окупац", "мобіліз", "бригад", "батальон", "обстріл", "загибл",
        "втрат", "полонен", "контрнаступ", "укріплен", "позиці", "штурм",
        "засідк", "мінн", "артилері", "танк", "броньован",
        # EN
        "war", "attack", "missile", "strike", "military", "drone", "artillery",
        "weapon", "troops", "army", "defense", "offensive", "combat", "ammo",
        "front line", "frontline", "counteroffensive", "siege", "shelling",
        "occupation", "mobilization", "casualties", "prisoner of war", "pow",
        "armored", "tank", "fortification", "minefield",
        # HU
        "háború", "fegyver", "rakéta", "támadás", "katoná", "hadsereg",
        "védelm", "offenzív", "drón", "invázió", "lövöldöz", "ostrom",
        "hadifogoly", "veszteség",
        # SK
        "vojn", "zbraň", "raket", "útok", "armád", "vojsk", "obran", "ofenzív",
        "dron", "invázia", "ostreľovani", "straty", "zajatec",
        # RO
        "război", "armă", "rachet", "atac", "armat", "militar", "defens",
        "ofensiv", "dronă", "invazie", "bombardament", "pierderi",
    ],

    # ── 1. politics ───────────────────────────────────────────────────────────
    [
        # UA
        "політ", "президент", "парламент", "уряд", "вибор", "депутат",
        "міністр", "санкці", "дипломат", "скандал", "відставк", "коаліц",
        "опозиц", "заяв", "законопроект", "реформ", "корупці", "олігарх",
        "партіj", "конституці", "референдум", "вето", "указ",
        # EN
        "election", "president", "parliament", "sanctions", "government",
        "diplomacy", "minister", "senate", "scandal", "resignation",
        "coalition", "opposition", "legislation", "reform", "corruption",
        "referendum", "decree", "veto", "political crisis",
        # HU
        "választás", "elnök", "parlament", "kormány", "képviselő", "miniszter",
        "szankció", "botrány", "korrupció", "reform", "koalíció",
        # SK
        "voľby", "prezident", "parlament", "vlád", "poslanec", "minister",
        "sankci", "korupci", "reforma", "koalíci", "škandál",
        # RO
        "aleger", "președinte", "parlament", "guvern", "deputat", "ministru",
        "sancțiun", "corupți", "reformă", "coaliți", "scandal",
    ],

    # ── 2. economy ────────────────────────────────────────────────────────────
    [
        # UA
        "економік", "інфляці", "ввп", "ринок", "банк", "фінанс", "інвестиц",
        "бюджет", "валют", "акці", "торгівл", "кредит", "борг", "податк",
        "рецесі", "девальвац", "дефолт", "мвф", "відбудов", "ембарго",
        # EN
        "gdp", "inflation", "market", "trade", "bank", "finance", "investment",
        "budget", "currency", "stock", "debt", "tax", "recession", "devaluation",
        "default", "imf", "reconstruction", "embargo", "tariff", "export",
        "import", "supply chain",
        # HU
        "gazdaság", "infláció", "piac", "bank", "pénzügy", "befektetés",
        "költségvetés", "valuta", "részvény", "adó", "recesszió",
        # SK
        "ekonomika", "infláci", "trh", "bank", "financi", "investíci",
        "rozpočet", "mena", "daň", "recesia",
        # RO
        "economi", "inflați", "piață", "banc", "finanț", "investiți",
        "buget", "valut", "impozit", "recesiune",
    ],

    # ── 3. diplomacy_international ────────────────────────────────────────────
    [
        # UA
        "переговор", "саміт", "угод", "договір", "посол", "союзник",
        "нато", "євросоюз", "оон", "міжнародн", "двосторонн", "мирн план",
        "перемир", "припинен вогню", "мирні переговори",
        # EN
        "negotiations", "summit", "agreement", "ambassador", "nato", "eu", "un",
        "international", "bilateral", "ceasefire", "peace talks", "treaty",
        "alliance", "foreign policy", "g7", "g20", "security council",
        "un security council", "european council", "peacekeeping",
        # HU
        "tárgyalás", "csúcstalálkozó", "megállapodás", "nagykövet", "szövetség",
        "tűzszünet", "béketárgyalás", "külpolitika",
        # SK
        "rokovani", "samit", "dohod", "veľvyslanec", "spojenec",
        "prímeri", "mierové rokovani", "zahraničná politika",
        # RO
        "negocier", "summit", "acord", "ambasador", "alianță",
        "încetarea focului", "politică externă",
    ],

    # ── 4. energy ────────────────────────────────────────────────────────────
    [
        # UA
        "енергетик", "газ", "нафт", "електроенерг", "аес", "ядерн",
        "блекаут", "відключен", "світл", "відновлюван", "трубопровід",
        "газопровід", "nord stream", "lng", "спг",
        # EN
        "energy", "gas", "oil", "electricity", "nuclear", "blackout", "power",
        "renewable", "solar", "wind", "pipeline", "lng", "natural gas",
        "energy crisis", "power grid", "hydroelectric",
        # HU
        "energia", "gáz", "olaj", "villamos", "atomerőmű", "nukleáris",
        "áramszünet", "megújuló", "csővezeték",
        # SK
        "energetik", "plyn", "ropa", "elektrina", "atómová", "jadrový",
        "výpadok", "obnoviteľn", "plynovod",
        # RO
        "energet", "gaze", "petrol", "electricitat", "nuclear", "întreruper",
        "regenerabil", "conductă",
    ],

    # ── 5. technology ────────────────────────────────────────────────────────
    [
        # UA
        "технологі", "штучний інтелект", "стартап", "кібер", "айті",
        "алгоритм", "блокчейн", "цифров", "хакер", "програмн",
        # EN
        "ai", "artificial intelligence", "startup", "software", "cyber", "tech",
        "algorithm", "blockchain", "digital", "machine learning", "hacker",
        "semiconductor", "chip", "quantum", "data breach",
        # HU
        "technológi", "mesterséges intelligencia", "szoftver", "kiberbiztonság",
        "hacker", "adatlopás",
        # SK
        "technológi", "umelá inteligencia", "softvér", "kybernetick",
        "hacker", "únik dát",
        # RO
        "tehnologi", "inteligență artificială", "software", "cibernetic",
        "hacker", "breșă de date",
    ],

    # ── 6. society_humanitarian ──────────────────────────────────────────────
    [
        # UA
        "суспільств", "протест", "права людини", "біженц",
        "міграц", "гуманітарн", "евакуац", "постраждал", "жертв", "цивільн",
        "демонстрац", "страйк", "соціальн",
        # EN
        "society", "protest", "human rights", "refugees", "migration",
        "humanitarian", "evacuation", "victims", "civilian", "demonstration",
        "strike", "social", "ngo", "aid",
        # HU
        "társadalom", "tüntetés", "menekült", "migráció", "humanitárius",
        "evakuáció", "áldozat", "polgári", "sztrájk",
        # SK
        "spoločnosť", "protest", "utečenec", "migráci", "humanitárn",
        "evakuáci", "obeť", "civilist", "štrajk",
        # RO
        "societat", "protest", "refugiat", "migrați", "umanitar",
        "evacuare", "victimă", "civil", "grevă",
    ],

    # ── 7. geopolitics [NEW] ──────────────────────────────────────────────────
    # Велика геополітика: сфери впливу, стратегічне суперництво, блоки
    [
        # UA
        "геополітик", "сфера впливу", "стратегічн", "наддержав", "многополярн",
        "розширенн нато", "вступ до єс", "кандидатств", "членств",
        "безпековий порядок", "ядерне стримуванн",
        # EN
        "geopolitics", "sphere of influence", "strategic", "superpower",
        "multipolar", "nato expansion", "eu accession", "eu membership",
        "security order", "deterrence", "containment", "proxy war",
        "great power", "cold war", "iron curtain", "buffer state",
        "geostrategic", "hegemony", "power projection", "military alliance",
        "transatlantic", "indo-pacific", "brics", "global south",
        # HU
        "geopolitika", "befolyási övezet", "stratégiai", "nagyhatalom",
        "nato-bővítés", "eu-csatlakozás", "nukleáris elrettentés",
        # SK
        "geopolitika", "sféra vplyvu", "strategick", "superveľmoc",
        "rozšírenie nato", "vstup do eú", "odstrašovanie",
        # RO
        "geopolitic", "sferă de influență", "strategic", "superputere",
        "extinderea nato", "aderarea la ue", "descurajare nucleară",
    ],

    # ── 8. security_intelligence [NEW] ────────────────────────────────────────
    # Спецслужби, гібридна війна, тероризм, шпигунство
    [
        # UA
        "спецслужб", "розвідк", "контррозвідк", "гібридн", "диверсі",
        "саботаж", "шпигун", "терорист", "вербуванн", "агент", "ффсб", "гру",
        "ціа", "мі6", "нсо", "пегас", "кібератак", "інфраструктур",
        # EN
        "intelligence", "counterintelligence", "hybrid war", "hybrid warfare",
        "sabotage", "espionage", "spy", "terrorism", "terrorist", "recruit",
        "fsb", "gru", "cia", "mi6", "mossad", "nso group", "pegasus",
        "cyberattack", "critical infrastructure", "false flag",
        "asymmetric warfare", "psychological operations", "psyops",
        "information warfare", "covert operation",
        # HU
        "titkosszolgálat", "hírszerzés", "kémkedés", "hibrid háború",
        "szabotázs", "terrorista", "kibertámadás", "kritikus infrastruktúra",
        # SK
        "spravodajsk", "kontrarozviedka", "hybridná vojna", "sabotáž",
        "špionáž", "terorizmus", "kyberútok", "kritická infraštruktúra",
        # RO
        "servicii de informați", "contrainformații", "război hibrid",
        "sabotaj", "spionaj", "terorism", "atac cibernetic",
    ],

    # ── 9. nuclear_wmd [NEW] ──────────────────────────────────────────────────
    # Ядерна зброя, МАГАТЕ, нерозповсюдження, хімічна/біологічна зброя
    [
        # UA
        "ядерн", "атомн", "аес", "запорізька аес", "заяес", "магате",
        "нерозповсюдженн", "ядерна зброя", "радіоактивн", "бруднa бомб",
        "хімічна зброя", "біологічна зброя", "хімічна атак",
        # EN
        "nuclear", "atomic", "iaea", "non-proliferation", "nuclear weapon",
        "radioactive", "dirty bomb", "chemical weapon", "biological weapon",
        "wmd", "weapons of mass destruction", "nuclear plant", "nuclear power",
        "enrichment", "warhead", "icbm", "ballistic missile",
        "nuclear deterrence", "nuclear threat", "radiation leak",
        # HU
        "nukleáris", "atomerőmű", "atomfegyver", "sugárzás", "vegyifegyver",
        "biológiai fegyver", "nukleáris fenyegetés",
        # SK
        "nukleárn", "atómová elektráreň", "jadrová zbraň", "žiareni",
        "chemická zbraň", "biologická zbraň",
        # RO
        "nuclear", "centrală nucleară", "armă nucleară", "radiații",
        "armă chimică", "armă biologică",
    ],

    # ── 10. disinformation_information_war [NEW] ──────────────────────────────
    # Дезінформація, пропаганда, медіа-маніпуляції, цензура
    [
        # UA
        "дезінформац", "пропаганд", "фейк", "маніпуляці", "цензур",
        "інформаційн війн", "медіа маніпуляці", "fake news", "deepfake",
        "тролі", "ботоферм", "наратив", "когнітивн", "медіаграмотн",
        # EN
        "disinformation", "propaganda", "fake news", "deepfake", "manipulation",
        "censorship", "information war", "troll farm", "bot network",
        "narrative", "cognitive warfare", "media literacy", "fact-check",
        "misinformation", "influence operation", "psyops",
        # HU
        "dezinformáció", "propaganda", "álhír", "manipuláció", "cenzúra",
        "információs háború", "trollfarm",
        # SK
        "dezinformáci", "propaganda", "falošné správy", "manipuláci",
        "cenzúra", "informačná vojna", "trollfarma",
        # RO
        "dezinformare", "propagandă", "știri false", "manipulare",
        "cenzură", "război informațional",
    ],

    # ── 11. sanctions_finance_war [NEW] ───────────────────────────────────────
    # Санкційна економіка, заморожені активи, обхід санкцій, SWIFT
    [
        # UA
        "санкці", "заморожен актив", "конфіскац", "репарац",
        "обхід санкцій", "swift", "свіфт", "вторинні санкці",
        "олігарх", "яхт", "активи рф", "замороженн резерв",
        # EN
        "sanctions", "frozen assets", "confiscation", "reparations",
        "sanctions evasion", "swift", "secondary sanctions", "oligarch",
        "asset freeze", "russian assets", "war reparations",
        "financial warfare", "export control", "dual use",
        # HU
        "szankciók", "befagyasztott eszközök", "elkobzás", "jóvátétel",
        "szankciók kijátszása", "oligarcha",
        # SK
        "sankcie", "zmrazené aktíva", "konfiškáci", "reparáci",
        "obchádzanie sankcií", "oligarcha",
        # RO
        "sancțiun", "active înghețate", "confiscare", "reparații",
        "eludarea sancțiunilor", "oligarh",
    ],

    # ── 12. war_crimes_accountability [NEW] ──────────────────────────────────
    # Воєнні злочини, МКС, трибунали, геноцид, відповідальність
    [
        # UA
        "воєнн злочин", "злочин проти людяності", "геноцид", "мкс",
        "міжнародний кримінальний суд", "трибунал", "депортаці",
        "фільтраційн табір", "катуванн", "страт", "масов вбивств",
        "буча", "маріупол", "ізюм",
        # EN
        "war crimes", "crimes against humanity", "genocide", "icc",
        "international criminal court", "tribunal", "deportation",
        "filtration camp", "torture", "execution", "mass killing",
        "accountability", "justice", "atrocity", "massacre",
        # HU
        "háborús bűnök", "emberiesség elleni bűnök", "népirtás", "nbn",
        "deportálás", "kínzás", "tömeges gyilkosság",
        # SK
        "vojnové zločiny", "zločiny proti ľudskosti", "genocída",
        "deportáci", "mučeni", "masová vražda",
        # RO
        "crime de război", "crime împotriva umanității", "genocid",
        "deportare", "tortură", "masacru",
    ],

    # ── 13. elections_democracy [NEW] ────────────────────────────────────────
    # Демократія під тиском, автократія, виборчі маніпуляції
    [
        # UA
        "демократі", "автократі", "авторитаризм", "виборч маніпуляці",
        "фальсифікац", "виборч комісі", "міжнародн спостерігач",
        "свобод преси", "незалежн суд", "верховенств прав",
        # EN
        "democracy", "autocracy", "authoritarianism", "election fraud",
        "electoral manipulation", "election commission", "international observer",
        "press freedom", "judicial independence", "rule of law",
        "democratic backsliding", "hybrid regime", "competitive authoritarianism",
        # HU
        "demokrácia", "autokrácia", "tekintélyelvűség", "választási csalás",
        "sajtószabadság", "bírói függetlenség", "jogállamiság",
        # SK
        "demokraci", "autokraci", "autoritarizmus", "volebný podvod",
        "sloboda tlače", "nezávislosť súdnictva", "právny štát",
        # RO
        "democrație", "autocrație", "autoritarism", "fraudă electorală",
        "libertatea presei", "independența justiției", "statul de drept",
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
    IScoringService через BM25 без geo-фільтрації.

    [СПРОЩЕНО] Повністю видалено GeoRelevanceFilter — BM25 повертає
    чистий тематичний score ∈ [0.0, 1.0]. Geo-логіка більше не є
    відповідальністю цього сервісу.

    [РОЗШИРЕНО] Корпус тем: 14 категорій замість 7, акцент на геополітику,
    безпеку, ядерку, дезінформацію, санкції, воєнні злочини.

    ParsedContent.language більше НЕ потрібен для scoring —
    corpus сам містить ключові слова всіх мов (UA/EN/HU/SK/RO).
    """

    def __init__(self, max_score: float = _BM25_MAX_SCORE) -> None:
        self._max_score = max_score
        self._bm25 = self._build_bm25()

    def _build_bm25(self):
        try:
            from rank_bm25 import BM25Okapi
            self._backend = "rank_bm25"
            # ✅ Corpus будується ОДИН РАЗ з keyword-документів
            # Кожна тема = один "документ" зі своїми ключовими словами
            return BM25Okapi(_TOPIC_CORPUS_RAW)
        except ImportError:
            self._backend = "simple"
            return None

    async def score(self, content: ParsedContent) -> float:
        text = content.full_text()
        if not text:
            return 0.0

        if self._backend == "simple":
            raw_score = self._simple_score(text)
        else:
            raw_score = self._bm25_score(text)

        logger.info("BM25: score=%.3f", raw_score)
        return raw_score

    def _bm25_score(self, text: str) -> float:
        tokens = _tokenize(text)
        if not tokens:
            return 0.0

        # ✅ Query = токени статті проти фіксованого corpus тем
        scores = self._bm25.get_scores(tokens)
        
        raw = float(np.max(scores))
        normalized = min(raw / self._max_score, 1.0)

        logger.debug(
            "BM25: raw_max=%.3f normalized=%.3f best_topic=%d tokens=%d",
            raw, normalized, int(np.argmax(scores)), len(tokens),
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