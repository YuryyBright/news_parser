import logging
import re
import urllib.parse
from datetime import datetime, date
from typing import Optional

import httpx

from src.application.ports.llm_rewriter import ILLMRewriter

logger = logging.getLogger(__name__)

# ─── Валюти які конвертуємо ───────────────────────────────────────────────────
# ISO код → (список raw-regex маркерів, Ukrainian label)
# ВАЖЛИВО: маркери — це raw regex без re.escape, вони компілюються як є.
_CURRENCY_CONFIG: dict[str, tuple[list[str], str]] = {
    "USD": ([r"USD", r"\$", r"долар(?:ів|а)?", r"dollars?", r"bucks?"], "дол. США"),
    "EUR": ([r"EUR", r"€", r"євро", r"euros?"], "євро"),
    "RON": ([r"RON", r"лей(?:ів)?", r"леї", r"lei", r"leu"], "румунських леїв"),
    "HUF": ([r"HUF", r"форинт(?:ів)?", r"forints?"], "форинтів"),
    "PLN": ([r"PLN", r"злот(?:их)?", r"zł", r"zlot[yych]*"], "польських злотих"),
    "GBP": ([r"GBP", r"£", r"фунт(?:ів)?", r"pounds?", r"sterling"], "фунтів стерлінгів"),
    "CHF": ([r"CHF", r"франк(?:ів)?", r"francs?"], "швейцарських франків"),
    "CZK": ([r"CZK", r"крон(?:и)?", r"koruna", r"korun"], "чеських крон"),
}

# ─── Числові множники ─────────────────────────────────────────────────────────
_MULTIPLIERS: dict[str, int] = {
    "млрд":     1_000_000_000,
    "mld":      1_000_000_000,
    "billion":  1_000_000_000,
    "milliárd": 1_000_000_000,
    "miliarde": 1_000_000_000,
    "miliarda": 1_000_000_000,
    "млн":      1_000_000,
    "mln":      1_000_000,
    "million":  1_000_000,
    "millió":   1_000_000,
    "milioane": 1_000_000,
    "milión":   1_000_000,
    "тис":      1_000,
    "тис.":     1_000,
    "thousand": 1_000,
    "ezer":     1_000,
    "mii":      1_000,
    "tisíc":    1_000,
}

# ─── NBU API ──────────────────────────────────────────────────────────────────
_NBU_API = "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?json"
_RATE_CACHE: dict[str, float] = {}
_CACHE_DATE: Optional[date] = None


async def _fetch_nbu_rates() -> dict[str, float]:
    global _RATE_CACHE, _CACHE_DATE

    today = date.today()
    if _CACHE_DATE == today and _RATE_CACHE:
        return _RATE_CACHE

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(_NBU_API)
            resp.raise_for_status()
            data = resp.json()

        rates: dict[str, float] = {}
        for item in data:
            code = item.get("cc", "").upper()
            rate = item.get("rate")
            if code and rate:
                rates[code] = float(rate)

        if rates:
            _RATE_CACHE = rates
            _CACHE_DATE = today
            logger.debug("NBU rates loaded: %d currencies (date=%s)", len(rates), today)

    except Exception as exc:
        logger.warning("NBU rates fetch failed: %s", exc)
        if _RATE_CACHE:
            logger.info("Using stale NBU rate cache (date=%s)", _CACHE_DATE)

    return _RATE_CACHE


def _format_uah(amount: float) -> str:
    """Форматує суму у гривнях з множниками."""
    if amount >= 1_000_000_000:
        val = amount / 1_000_000_000
        label = "млрд"
    elif amount >= 1_000_000:
        val = amount / 1_000_000
        label = "млн"
    elif amount >= 1_000:
        val = amount / 1_000
        label = "тис."
    else:
        return f"{amount:,.0f} грн".replace(",", "\u00a0")

    if val == int(val):
        return f"{int(val)} {label} грн"
    return f"{val:.1f} {label} грн".replace(".", ",")


def _format_uah_range(uah_amounts: list[float]) -> str:
    """Форматує список сум у гривнях, склеюючи діапазони."""
    formatted = [_format_uah(a) for a in uah_amounts]

    if len(formatted) == 1:
        return formatted[0]

    if len(formatted) == 2:
        # Намагаємося зробити "16,8–21 млн грн" замість "16,8 млн грн – 21 млн грн"
        parts0 = formatted[0].split(" ", 1)
        parts1 = formatted[1].split(" ", 1)
        if len(parts0) == 2 and len(parts1) == 2 and parts0[1] == parts1[1]:
            return f"{parts0[0]}–{parts1[0]} {parts0[1]}"

    return " – ".join(formatted)


# ─── Побудова regex ───────────────────────────────────────────────────────────

def _build_currency_pattern() -> re.Pattern:
    """
    Будує єдиний regex для пошуку грошових сум.

    ВИПРАВЛЕНО: маркери валют НЕ екрануються через re.escape — вони вже є
    валідними regex-фрагментами (напр. r"dollars?" містить квантор '?').
    Сортуємо за довжиною (довші першими) щоб уникнути часткових збігів.
    """
    # Зібрати всі маркери як raw regex без escape
    all_markers: list[str] = []
    for _iso, (markers, _label) in _CURRENCY_CONFIG.items():
        all_markers.extend(markers)

    # Довші маркери мають пріоритет
    all_markers.sort(key=len, reverse=True)
    currency_pat = r"(?P<currency>" + "|".join(all_markers) + r")"
    currency_pat2 = r"(?P<currency2>" + "|".join(all_markers) + r")"

    # Множники — екрануємо крапку в "тис.", решта — прості слова
    mult_list = sorted(_MULTIPLIERS.keys(), key=len, reverse=True)
    mult_escaped = [re.escape(m) for m in mult_list]
    mult_pat  = r"(?P<mult>"  + "|".join(mult_escaped) + r")"
    mult_pat2 = r"(?P<mult2>" + "|".join(mult_escaped) + r")"

    # Число: цифри з пробілами/комами/крапками, опційно діапазон через дефіс/тире
    num_core = r"\d[\d\s\u00a0,\.]*"
    num_pat  = r"(?P<amount>"  + num_core + r"(?:[-–—]\s*" + num_core + r")?)"
    num_pat2 = r"(?P<amount2>" + num_core + r"(?:[-–—]\s*" + num_core + r")?)"

    # Два порядки: "10 млн USD" і "USD 10 млн"
    pattern = (
        r"(?:"
        # Варіант 1: число [множник] валюта
        r"(?:" + num_pat + r"\s*" + mult_pat + r"?\s*" + currency_pat + r")"
        r"|"
        # Варіант 2: валюта число [множник]
        r"(?:" + currency_pat2 + r"\s*" + num_pat2 + r"\s*" + mult_pat2 + r"?)"
        r")"
    )
    return re.compile(pattern, re.IGNORECASE | re.UNICODE)


_CURRENCY_RE: Optional[re.Pattern] = None


def _get_currency_re() -> re.Pattern:
    global _CURRENCY_RE
    if _CURRENCY_RE is None:
        _CURRENCY_RE = _build_currency_pattern()
    return _CURRENCY_RE


# ─── Парсинг числа ────────────────────────────────────────────────────────────

def _parse_amount(amount_str: str) -> list[float]:
    """
    Перетворює рядок типу '1 500 000', '1.5' або '4 - 5' у список float.

    ВИПРАВЛЕНО: розбивка по дефісу/тире із trim пробілів навколо роздільника,
    коректна логіка визначення десяткового знаку.
    """
    # Нормалізуємо non-breaking spaces
    amount_str = amount_str.replace("\u00a0", " ")

    # Розбиваємо по дефісу/тире з опціональними пробілами навколо
    parts = re.split(r"\s*[-–—]\s*", amount_str.strip())
    parsed: list[float] = []

    for p in parts:
        # Прибираємо пробіли (розділювачі тисяч)
        cleaned = p.strip().replace(" ", "")
        if not cleaned:
            continue

        # Визначення десяткового знаку:
        # "1.500.000" або "1,500,000" — роздільник тисяч; "1.5" або "1,5" — десятковий
        dot_count   = cleaned.count(".")
        comma_count = cleaned.count(",")

        if dot_count > 1:
            # Крапка — роздільник тисяч: "1.500.000"
            cleaned = cleaned.replace(".", "")
        elif comma_count > 1:
            # Кома — роздільник тисяч: "1,500,000"
            cleaned = cleaned.replace(",", "")
        elif dot_count == 1 and comma_count == 1:
            # Обидва: беремо останній як десятковий
            if cleaned.index(".") < cleaned.index(","):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif comma_count == 1:
            # Одна кома — десятковий знак: "1,5"
            cleaned = cleaned.replace(",", ".")
        # dot_count == 1: одна крапка — вже десятковий знак, нічого не робимо

        try:
            parsed.append(float(cleaned))
        except ValueError:
            logger.debug("_parse_amount: cannot parse '%s'", p.strip())

    return parsed


# ─── Визначення ISO ───────────────────────────────────────────────────────────

def _detect_iso(marker: str) -> Optional[str]:
    """За рядком-маркером визначає ISO-код валюти."""
    for iso, (markers, _label) in _CURRENCY_CONFIG.items():
        for m in markers:
            try:
                if re.fullmatch(m, marker, re.IGNORECASE | re.UNICODE):
                    return iso
            except re.error:
                # На випадок некоректного regex-фрагмента
                if marker.lower() == m.lower():
                    return iso
    return None


# ─── Основна функція конвертації ──────────────────────────────────────────────

async def convert_currencies_in_text(text: str) -> tuple[str, dict[str, float]]:
    """
    Знаходить всі грошові суми у тексті та додає конвертацію в гривні в дужках.
    Повертає: (оновлений текст, використані курси {ISO: rate})
    """
    rates = await _fetch_nbu_rates()
    if not rates:
        return text, {}

    used_rates: dict[str, float] = {}
    converted_text = _apply_currency_replacements(text, rates, used_rates)
    return converted_text, used_rates


def _apply_currency_replacements(
    text: str,
    rates: dict[str, float],
    used_rates: dict[str, float],
) -> str:
    pattern = _get_currency_re()

    def replacer(m: re.Match) -> str:
        amount_str = m.group("amount")  or m.group("amount2")  or ""
        mult_str   = m.group("mult")    or m.group("mult2")    or ""
        curr_str   = m.group("currency") or m.group("currency2") or ""

        if not amount_str or not curr_str:
            return m.group(0)

        amounts = _parse_amount(amount_str)
        if not amounts:
            return m.group(0)

        multiplier = 1
        if mult_str:
            # Пошук без урахування регістру і крапки
            mult_key = mult_str.strip().lower()
            multiplier = next(
                (v for k, v in _MULTIPLIERS.items() if k.lower() == mult_key),
                1,
            )

        iso = _detect_iso(curr_str)
        if not iso or iso not in rates:
            return m.group(0)

        rate = rates[iso]
        used_rates[iso] = rate

        uah_amounts = [amt * multiplier * rate for amt in amounts]
        uah_str = _format_uah_range(uah_amounts)

        return f"{m.group(0)} ({uah_str})"

    return pattern.sub(replacer, text)


# ─── Основний клас ────────────────────────────────────────────────────────────

class TelegramLLMRewriter(ILLMRewriter):
    """
    Реалізує ILLMRewriter через будь-який ILLMClient.
    Конвертація валют (USD/EUR/RON/HUF/PLN/GBP/CHF/CZK → UAH) виконується
    до відправки тексту в LLM з актуальним курсом НБУ (кеш на добу).
    """

    def __init__(self, llm_client) -> None:
        self._llm = llm_client

    async def rewrite(
        self,
        title: str,
        full_text: str,
        url: str,
        style_context: str = "",
        published_at=None,
    ) -> str:
        if self._llm is None:
            return ""

        current_date = datetime.now().strftime("%d.%m.%Y")

        # ── 1. Конвертація валют у вихідному тексті ───────────────────────────
        enriched_text, used_rates = await convert_currencies_in_text(full_text[:6000])

        # ── 2. Дата публікації ────────────────────────────────────────────────
        if published_at:
            article_date = (
                published_at if isinstance(published_at, str)
                else published_at.strftime("%d.%m.%Y")
            )
        else:
            article_date = current_date

        # ── 3. Домен джерела ──────────────────────────────────────────────────
        try:
            domain = urllib.parse.urlparse(url).netloc.replace("www.", "")
        except Exception:
            domain = "unknown"

        # ── 4. Блок стилістичного контексту (RAG) ────────────────────────────
        style_block = ""
        if style_context and style_context.strip():
            style_block = (
                "\n\nЕТАЛОННІ ФРАГМЕНТИ (для відтворення стилю та термінології):\n"
                "─────────────────────────────────────────────\n"
                f"{style_context[:4000]}\n"
                "─────────────────────────────────────────────\n"
                "Відтворювати виключно стиль і термінологію. "
                "Факти з еталонних фрагментів не використовувати."
            )

        # ── 5. Примітка про курси НБУ ─────────────────────────────────────────
        rates_note = ""
        if used_rates:
            rates_lines = ", ".join(
                f"1 {iso} = {rate:.2f} грн"
                for iso, rate in sorted(used_rates.items())
            )
            rates_note = f"\n\nКурс НБУ на {current_date}: {rates_lines}."

        # ── 6. System prompt (директивний, без емоційного забарвлення) ────────
        system = (
            "Роль: перекладач та аналітик офіційно-ділових текстів.\n\n"
            "ЗАВДАННЯ:\n"
            "Перекласти та переписати новинну статтю у вигляді стислої офіційної довідки "
            "українською мовою. Стиль — канцелярсько-діловий: нейтральний, фактологічний, "
            "без оцінних суджень, метафор та емоційного забарвлення.\n\n"
            "ОБОВ'ЯЗКОВІ ВИМОГИ:\n"
            f"1. ПЕРШИЙ РЯДОК. Починати першу фразу з дати та джерела за одним із форматів:\n"
            f"   «[Дата] за повідомленням [джерело], ...»\n"
            f"   «За повідомленням [джерело] від [Дата], ...»\n"
            f"   Дата публікації: {article_date}. Домен джерела: {domain}.\n"
            "2. ДАТА. Формат дати — ДД.ММ.РРРР. "
            "Використовувати надану дату, якщо в тексті явно не вказана інша.\n"
            "3. ГРОШОВІ СУМИ. Вихідний текст містить еквіваленти у гривнях у дужках "
            "(приклад: «10 млн EUR (420 млн грн)»). Зберігати ці дужкові значення у вихідному вигляді, "
            "не перераховувати.\n"
            "4. ВЛАСНІ НАЗВИ. Усі власні назви та імена транслітерувати або перекладати "
            "відповідно до чинних українських норм. Латиниця у вихідному тексті не допускається. "
            "Фонетичні правила: словацька «c» → «ц» (Fico → Фіцо); угорська «sz» → «с» тощо.\n"
            "5. СПЕЦІАЛЬНА ТЕРМІНОЛОГІЯ. За наявності військової техніки, зброї, дронів, "
            "спеціальних правових або процедурних понять — додати після основного тексту "
            "окремий блок «Довідково:» з поясненням термінів.\n"
            "ЗАБОРОНЕНО:\n"
            "— Markdown-розмітка (**, ##, __ тощо).\n"
            "— Заголовки та підзаголовки.\n"
            "— Вступні або підсумкові фрази від власної особи (наприклад: «Ось переклад:»).\n"
            "— Копіювання фактів з еталонних фрагментів (якщо надані).\n\n"
            "ВИВОДИТИ: лише готовий текст офіційної довідки."
        )

        # ── 7. User prompt ────────────────────────────────────────────────────
        user = (
            f"Заголовок: {title}\n\n"
            f"Текст (з еквівалентами в гривнях):\n{enriched_text}\n\n"
            f"URL джерела: {url}"
            f"{rates_note}"
            f"{style_block}\n\n"
            "Перекласти і переписати текст відповідно до вимог. "
            "Зберегти всі суми у гривнях у дужках."
        )

        # ── 8. LLM call ───────────────────────────────────────────────────────
        try:
            resp = await self._llm.complete(system, user, max_tokens=8192)
            rewritten = resp.text.strip()

            # Прибираємо <think>...</think> блоки (Qwen/DeepSeek)
            rewritten = re.sub(r"<think>.*?</think>", "", rewritten, flags=re.DOTALL).strip()

            logger.info(
                "LLM rewrite done: url=%s chars=%d currencies=%s",
                url,
                len(rewritten),
                list(used_rates.keys()) if used_rates else "none",
            )
            return rewritten

        except Exception as exc:
            logger.warning("LLM rewrite failed for url=%s: %s", url, exc)
            return ""