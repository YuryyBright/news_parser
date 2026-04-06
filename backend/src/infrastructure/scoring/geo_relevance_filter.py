# infrastructure/scoring/geo_relevance_filter.py
"""
GeoRelevanceFilter — географічна релевантність статті.

Задача:
  Стаття угорською про NATO глобально ≠ стаття про Угорщину в NATO.
  Стаття румунською про МВФ ≠ стаття про позику Румунії від МВФ.

Логіка:
  1. Визначаємо мову статті (передається з ProcessArticlesUseCase через ILanguageDetector).
  2. Кожна мова має свій набір "домашніх" гео-сигналів (назви країни, міст, інституцій).
  3. Підраховуємо кількість гео-сигналів у тексті → geo_score ∈ [0.0, 1.0].
  4. Повертаємо geo_multiplier:
       - geo_score >= GEO_SELF_THRESHOLD  → 1.0   (стаття точно про "нас")
       - geo_score >= GEO_WEAK_THRESHOLD  → 0.75  (є згадки але не головна тема)
       - geo_score == 0.0 і мова цікавить  → BASE_MULTIPLIER (0.4 за замовчуванням)
         Тобто приймаємо тільки якщо тематичний score дуже високий.
       - мова взагалі не в профілі         → FOREIGN_MULTIPLIER (0.15)
         Майже завжди reject, крім виняткової тематики.

Чому НЕ просто reject:
  Іноді стаття EN про Угорщину/Румунію важливіша за HU-стаття про котиків.
  Множник зберігає гнучкість — фінальне рішення за threshold у use case.

Конфігурація (передається через DI або settings):
  GEO_SELF_THRESHOLD:   float = 0.15  # частка гео-токенів у тексті → "точно про нас"
  GEO_WEAK_THRESHOLD:   float = 0.04  # є згадки але не головна тема
  BASE_MULTIPLIER:      float = 0.40  # стаття рідною мовою але без гео-сигналів
  FOREIGN_MULTIPLIER:   float = 0.15  # стаття чужою мовою

Приклад:
  "Akár kilép Trump a NATO-ból..." (HU, нема HU гео-сигналів)
    → geo_score=0.0, мова HU є в профілі
    → multiplier=0.40
    → final_score = topic_score * 0.40
    → reject якщо topic_score < 0.625 (threshold 0.25 / 0.40)

  "Magyarország megkapta az EU-támogatást..." (HU, є "magyarország", "budapest")
    → geo_score=0.20 >= 0.15
    → multiplier=1.0
    → full score, нормальний pipeline

  "Словаччина запровадила нові санкції..." (SK текст UA)
    → мова UA, є SK гео-сигнали
    → multiplier=0.75 (UA-стаття про SK — релевантна але не "домашня")
    → насправді для UA-статей про сусідів це нормально
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ─── Гео-сигнали по мовах ────────────────────────────────────────────────────
# Формат: {мова_ISO: [сигнали_lowercase]}
# Сигнали — основи/стеми + повні форми найважливіших назв.
# Порядок важливий: специфічніші раніше (щоб regex не давав false matches).
#
# Стратегія для кожної мови:
#   - Назви країни (всі відмінки основи)
#   - Столиця + великі міста
#   - Ключові інституції (парламент, уряд, центробанк)
#   - Унікальні географічні об'єкти
#   - Сусідні країни які часто згадуються у контексті

# ─── Гео-сигнали по мовах ────────────────────────────────────────────────────
# Формат: {мова_ISO: [сигнали_lowercase]}
# Сигнали — основи/стеми + повні форми + найважливіші варіації.
# Порядок важливий: специфічніші сигнали йдуть раніше.

_GEO_SIGNALS: dict[str, list[str]] = {

    # ── Українська ──────────────────────────────────────────────────────────
    "uk": [
        # Країна та всі форми
        "україна", "україн", "ukraine", "ukrainian", "україни", "україні", "українська",
        # Столиця і найбільші міста (всі форми)
        "київ", "харків", "одес", "дніпр", "запоріж", "львів", "маріупол", "миколаїв",
        "херсон", "полтав", "суми", "чернігів", "вінниц", "ужгород", "чернівц", "тернопіл",
        "івано-франківськ", "хмельниц", "кривий ріг", "луцьк", "рівн", "черкас", "кропивниц",
        "kyiv", "kharkiv", "odesa", "dnipro", "zaporizhzhia", "lviv", "mariupol",
        # Окуповані території та Донбас
        "донецьк", "луганськ", "мелітопол", "бердянськ", "сєвєродонецьк", "лисичанськ",
        "донбас", "donbas", "donbass", "luhansk", "donetsk", "крим", "севастополь", "яким",
        # Регіони / області (повні назви)
        "київська область", "харківська область", "одеська область", "дніпропетровська",
        "запорізька область", "львівська область", "херсонська область", "луганська область",
        "донецька область", "закарпатська", "чернігівська", "сумська", "полтавська",
        "вінницька", "волинська", "житомирська", "кировоградська", "кропивницька",
        # Закарпаття (дуже важливо для UA-SK-HU контексту)
        "закарпаття", "закарпатська область", "ужгород", "мукачево", "берегово", "хуст",
        # Інституції, армія, влада
        "верховна рада", "зеленськ", "кабмін", "офіс президента", "генеральний штаб",
        "зсу", "сбу", "гур", "дснс", "нацгвардія", "азов", "єрмак", "залужний",
        # ЗМІ та ключові бренди
        "укрінформ", "суспільне", "радіо свобода", "1+1", "інтер", "ictv",
        # Сусіди в українському контексті
        "угорщин", "словаччин", "румун", "польщ", "угорськ", "словацьк", "румунськ",
        "польськ", "молдов", "білорус", "росі",
    ],

    # ── Угорська ─────────────────────────────────────────────────────────────
    "hu": [
        # Країна
        "magyarország", "magyar", "hungari", "magyarországon", "magyarországi",
        # Столиця і найбільші міста
        "budapest", "debrecen", "győr", "miskolc", "pécs", "sopron", "nyíregyháza",
        "kecskemét", "székesfehérvár", "veszprém", "eger", "szombathely", "zalaegerszeg",
        "kaposvár", "szeged", "szolnok", "tatabánya", "kecskemét",
        # Регіони / комітати (megye)
        "pannónia", "alföld", "dunántúl", "észak-magyarország", "dél-alföld",
        "vas megye", "győr-moson-sopron", "baranya", "borsod", "hajdú-bihar",
        "szabolcs-szatmár", "békés megye", "heves megye", "csongrád", "komárom-esztergom",
        "pest megye", "tolna megye", "somogy megye", "zala megye",
        # Закарпаття / угорська меншина
        "kárpátalj", "kárpátaljai magyarok", "erdély", "vajdaság", "felvidék", "burgenland",
        # Інституції та ключові політики (2026)
        "orbán", "fidesz", "országgyűl", "nemzeti bank", "mnb", "magyar kormány",
        "parlament", "köztársasági elnök", "sulyok tamás", "szijjártó", "novák katalin",
        "belügyminisztérium", "külügyminisztérium", "honvédelmi minisztérium",
        "pénzügyminisztérium", "kormány",
        # Партії / опозиція
        "momentum", "demokratikus koalíció", "dk", "mszp", "jobbik", "mi hazánk",
        "tisza párt", "magyar péter", "tisza",
        # ЗМІ
        "hvg", "444", "telex", "index", "rtl klub", "m1", "m2", "duna tv",
        "mandiner", "válasz online", "origo", "blikk",
        # Сусіди
        "ukrajna", "szlovákia", "románia", "szerbia", "ausztria", "horvátország",
    ],

    # ── Словацька ────────────────────────────────────────────────────────────
    # (СИЛЬНО РОЗШИРЕНО — саме для твоєї проблеми з SK-статтями)
    "sk": [
        # Країна та всі форми
        "slovensko", "slovensk", "slovak", "slovenskej", "slovenskej republiky",
        "slovenská republika", "slovenskú",
        # Столиця і всі важливі міста
        "bratislava", "košice", "prešov", "žilina", "banská bystrica", "nitra",
        "trnava", "trenčín", "poprad", "martin", "zvolen", "michalovce",
        "spišská nová ves", "komárno", "levice", "lučenec", "rimavská sobota",
        "bardejov", "trebišov", "humenné", "liptovský mikuláš", "ružomberok",
        # Регіони / краї (kraje)
        "bratislavský kraj", "trnavský kraj", "trenčínsky kraj", "nitriansky kraj",
        "žilinský kraj", "banskobystrický kraj", "prešovský kraj", "košický kraj",
        # Інституції та влада (2026)
        "fico", "pellegrini", "národná rada", "národná banka", "nbs", "slovenská vláda",
        "ministerstvo zahraničných vecí", "ministerstvo vnútra", "ministerstvo obrany",
        "ministerstvo financií", "prezidentský palác", "úrad vlády", "prezident",
        # Партії
        "smer", "hlas", "progresívne slovensko", "ps", "sas", "kdh", "oľano",
        "sns", "republika", "kresťanská demokracia", "šimečka", "blanár",
        "taraba", "danko", "sulík",
        # ЗМІ
        "sme", "denník n", "aktuality", "pravda", "hospodárske noviny", "ta3",
        "rtvs", "rádio slovensko", "markíza", "joj", "tv lux",
        # Сусіди та меншини в SK-контексті
        "ukrayna", "ukrayin", "maďarsko", "poľsko", "česko", "rakúsko",
        "ukraine", "ukrainian minority", "rusíni", "rusínska", "madari", "maďarská menšina",
        # Додаткові важливі терміни
        "visegrád", "v4", "eurofondy", "schengen", "nato", "európska únia",
    ],

    # ── Румунська ────────────────────────────────────────────────────────────
    "ro": [
        # Країна
        "românia", "român", "romania", "româniei", "românie",
        # Столиця і найбільші міста
        "bucurești", "cluj", "timișoara", "iași", "constanța", "craiova", "brașov",
        "galați", "ploiești", "oradea", "sibiu", "bacău", "pitești", "arad",
        "târgu mureș", "baia mare", "buzău", "râmnicu vâlcea", "suceava",
        "drobeta-turnu severin", "cluj-napoca",
        # Регіони / жудці (județe)
        "transilvania", "moldova", "muntenia", "oltenia", "dobrogea", "bucovina",
        "maramureș", "banat", "crișana", "ilfov", "bihor", "timiș", "dolj",
        "brăila", "tulcea", "caraș-severin", "mehedinți",
        # Порти та стратегічна інфраструктура
        "portul constanța", "sulina", "brăila port", "dunărea", "constanța port",
        # Інституції та політики (2026)
        "iohannis", "ciolacu", "parlamentul româniei", "banca națională",
        "guvernul româniei", "ministerul afacerilor externe", "ministerul apărării",
        "ministerul de interne", "cotroceni", "curtea constituțională", "ccr",
        "înaltă curte", "parchetul general",
        # Партії
        "psd", "pnl", "usr", "aur", "fdgr", "udmr", "forța dreptei", "ciolacu",
        "ciucă", "geoană", "simion", "năsui",
        # ЗМІ
        "digi24", "antena 3", "pro tv", "realitatea", "g4media", "hotnews",
        "ziarul financiar", "jurnalul național", "libertatea", "adevărul",
        # Сусіди та меншини
        "ucraina", "ungaria", "moldova", "serbia", "bulgaria", "ucraineni din românia",
        "minorități ucrainene", "maghiari", "hungarian minority",
    ],

    # ── Англійська ───────────────────────────────────────────────────────────
    # EN-статті цікаві тільки якщо явно згадують наші країни
    "en": [
        # Країни
        "ukraine", "ukrainian", "hungary", "hungarian", "slovakia", "slovak",
        "romania", "romanian",
        # Міста
        "kyiv", "budapest", "bratislava", "bucharest", "kharkiv", "odesa", "lviv",
        "dnipro", "zaporizhzhia", "debrecen", "kosice", "timisoara", "cluj-napoca",
        "uzhhorod", "mukachevo", "oradea",
        # Регіони
        "transcarpathia", "transcarpathian", "zakarpattia", "carpathian ruthenia",
        "transylvania", "donbas", "donbass", "banat",
        # Ключові політики
        "zelensky", "orban", "fico", "pellegrini", "iohannis", "szijjarto", "szijjártó",
        # Міжнародний контекст
        "visegrad", "v4", "nato eastern flank", "eu enlargement", "central europe",
        "eastern europe", "carpathian", "ukrainian minority", "hungarian minority",
    ],
}

# Мови що є в профілі інтересів (рідні мови)
_PROFILE_LANGUAGES: frozenset[str] = frozenset({"uk", "hu", "sk", "ro"})

# Мови що цікавлять але не є "домашніми" (EN — читаємо але менший пріоритет)
_SECONDARY_LANGUAGES: frozenset[str] = frozenset({"en"})

# ─── Пороги ───────────────────────────────────────────────────────────────────

# Частка гео-токенів від загальної кількості токенів статті
# >= цього → "стаття про нас" → multiplier=1.0
GEO_SELF_THRESHOLD: float = 0.08

# >= цього → "є згадки" → multiplier=0.75
GEO_WEAK_THRESHOLD: float = 0.025

# Мова є в профілі але гео-сигналів немає
# Стаття пройде тільки якщо topic_score > threshold / BASE_MULTIPLIER
# При threshold=0.25 і BASE=0.40 → потрібен topic_score > 0.625
BASE_MULTIPLIER: float = 0.55

# Мова не в профілі (але є EN або інша)
FOREIGN_MULTIPLIER: float = 0.20

# Повністю невідома мова
UNKNOWN_MULTIPLIER: float = 0.08


@dataclass
class GeoResult:
    """Результат гео-аналізу для діагностики."""
    language: str
    geo_score: float          # частка гео-токенів
    geo_hits: int             # кількість знайдених гео-сигналів
    matched_signals: list[str] = field(default_factory=list)
    multiplier: float = 1.0
    reason: str = ""


class GeoRelevanceFilter:
    """
    Визначає географічну релевантність статті і повертає multiplier для score.

    Використання у BM25ScoringService (early reject):
        geo = GeoRelevanceFilter()
        multiplier = geo.multiplier(content.full_text(), language)
        if bm25_score * multiplier < threshold:
            return 0.0  # early reject

    Використання у CompositeScoringService (фінальний множник):
        geo_mult = geo.multiplier(content.full_text(), language)
        final = (bm25_w * bm25 + embed_w * embed) * geo_mult
    """

    def __init__(
        self,
        geo_self_threshold: float = GEO_SELF_THRESHOLD,
        geo_weak_threshold: float = GEO_WEAK_THRESHOLD,
        base_multiplier: float = BASE_MULTIPLIER,
        foreign_multiplier: float = FOREIGN_MULTIPLIER,
        unknown_multiplier: float = UNKNOWN_MULTIPLIER,
    ) -> None:
        self._geo_self_threshold = geo_self_threshold
        self._geo_weak_threshold = geo_weak_threshold
        self._base_multiplier = base_multiplier
        self._foreign_multiplier = foreign_multiplier
        self._unknown_multiplier = unknown_multiplier

        # Компілюємо regex для кожної мови один раз
        self._patterns: dict[str, re.Pattern] = {
            lang: re.compile(
                r"(?:" + "|".join(re.escape(sig) for sig in signals) + r")",
                re.IGNORECASE,
            )
            for lang, signals in _GEO_SIGNALS.items()
        }

    def multiplier(self, text: str, language: str) -> float:
        """
        Швидкий метод — тільки multiplier без деталей.
        Використовується у scoring pipeline де не потрібна діагностика.
        """
        return self.analyze(text, language).multiplier

    def analyze(self, text: str, language: str) -> GeoResult:
        """
        Повний аналіз з деталями — для діагностики і логування.

        Args:
            text:     повний текст статті (title + body)
            language: ISO 639-1 код мови ("uk", "hu", "sk", "ro", "en", ...)
        """
        lang = language.lower().strip() if language else "unknown"
        text_lower = text.lower() if text else ""

        # ── Підраховуємо кількість слів у тексті (грубо) ─────────────────────
        word_count = max(len(text_lower.split()), 1)

        # ── Гео-сигнали для даної мови ────────────────────────────────────────
        # Якщо мова невідома або не в нашому словнику — беремо EN як fallback
        pattern = self._patterns.get(lang) or self._patterns.get("en")

        geo_hits = 0
        matched: list[str] = []

        if pattern and text_lower:
            matches = pattern.findall(text_lower)
            geo_hits = len(matches)
            # Унікальні для логування (не дублюємо "угорщин" 20 разів)
            matched = list(dict.fromkeys(m.lower() for m in matches))[:10]

        # Також перевіряємо cross-language сигнали:
        # Стаття HU може згадувати Україну/SK/RO — це теж підвищує релевантність
        cross_hits = self._cross_language_hits(text_lower, lang)
        geo_hits += cross_hits

        # ── Нормалізуємо до [0, 1] ────────────────────────────────────────────
        # Використовуємо sqrt щоб не карати короткі статті
        # 1 хіт у 100-словній статті = 0.01 (мало)
        # 3 хіти у 100-словній статті = 0.03 (вже щось)
        # 10 хітів у 200-словній статті = 0.05 (явно про нас)
        geo_score = min(geo_hits / word_count, 1.0)

        # ── Визначаємо multiplier ─────────────────────────────────────────────
        if lang in _PROFILE_LANGUAGES:
            if geo_score >= self._geo_self_threshold:
                mult = 1.0
                reason = f"profile_lang+strong_geo (score={geo_score:.3f})"
            elif geo_score >= self._geo_weak_threshold:
                mult = 0.75
                reason = f"profile_lang+weak_geo (score={geo_score:.3f})"
            else:
                mult = self._base_multiplier
                reason = f"profile_lang+no_geo → base_multiplier={mult}"

        elif lang in _SECONDARY_LANGUAGES:
            if geo_score >= self._geo_weak_threshold:
                mult = 0.75
                reason = f"secondary_lang+geo (score={geo_score:.3f})"
            else:
                mult = self._foreign_multiplier
                reason = f"secondary_lang+no_geo → foreign_multiplier={mult}"

        elif lang == "unknown":
            mult = self._unknown_multiplier
            reason = "unknown_lang"

        else:
            # Мова не в профілі і не EN (наприклад, DE, FR, PL...)
            # Єдиний шанс — явні гео-сигнали через EN fallback pattern
            if geo_score >= self._geo_weak_threshold:
                mult = 0.50
                reason = f"foreign_lang+geo_signals (score={geo_score:.3f})"
            else:
                mult = self._foreign_multiplier
                reason = f"foreign_lang+no_geo → {mult}"

        result = GeoResult(
            language=lang,
            geo_score=geo_score,
            geo_hits=geo_hits,
            matched_signals=matched,
            multiplier=mult,
            reason=reason,
        )

        logger.info(
            "GeoFilter: lang=%s geo_hits=%d geo_score=%.3f mult=%.2f reason=%s",
            lang, geo_hits, geo_score, mult, reason,
        )
        return result

    def _cross_language_hits(self, text_lower: str, source_lang: str) -> int:
        """
        Перевіряємо наявність гео-сигналів ІНШИХ профільних мов у тексті.

        Приклад:
          HU-стаття про Закарпаття згадує "ukrajna" → +cross_hits
          SK-стаття про угорську меншину згадує "maďarsko" → +cross_hits

        Це збільшує geo_score і шанс потрапити у weak/self threshold.
        """
        total = 0
        for lang, pattern in self._patterns.items():
            # Не перевіряємо EN, тому що воно вже враховано вище
            if lang == source_lang or lang == "en":
                continue  # вже враховано вище
            if lang not in _PROFILE_LANGUAGES:
                continue
            # Даємо менший вага cross-hits (ділимо на 2)
            hits = len(pattern.findall(text_lower))
            total += hits // 2
        return total