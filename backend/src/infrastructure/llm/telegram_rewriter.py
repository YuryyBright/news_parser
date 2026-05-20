import logging
import re
import urllib.parse
from datetime import datetime, date
from typing import Optional

import httpx

from src.application.ports.llm_rewriter import ILLMRewriter

logger = logging.getLogger(__name__)

# ─── Валюти які конвертуємо ───────────────────────────────────────────────────
# ISO код → (символи/назви для regex, Ukrainian label)
_CURRENCY_CONFIG: dict[str, tuple[list[str], str]] = {
    "USD": (["USD", r"\$", "долар", "доларів", "долара", "dollars?", "bucks?"], "дол. США"),
    "EUR": (["EUR", "€", "євро", "euro[s]?"], "євро"),
    "RON": (["RON", "леї", "лей", "lei", "leu"], "румунських леїв"),
    "HUF": (["HUF", "форинт", "forint[s]?"], "форинтів"),
    "PLN": (["PLN", "злот", "zł", "zlot[yych]?"], "польських злотих"),
    "GBP": (["GBP", "£", "фунт", "pounds?", "sterling"], "фунтів стерлінгів"),
    "CHF": (["CHF", "франк", "francs?"], "швейцарських франків"),
    "CZK": (["CZK", "крон", "koruna", "korun"], "чеських крон"),
}

# ─── Числові множники ─────────────────────────────────────────────────────────
_MULTIPLIERS = {
    "млрд": 1_000_000_000,
    "mld": 1_000_000_000,
    "billion": 1_000_000_000,
    "milliárd": 1_000_000_000, # Угорська
    "miliarde": 1_000_000_000, # Румунська
    "miliarda": 1_000_000_000, # Словацька
    "млн": 1_000_000,
    "mln": 1_000_000,
    "million": 1_000_000,
    "millió": 1_000_000,       # Угорська
    "milioane": 1_000_000,     # Румунська
    "milión": 1_000_000,       # Словацька
    "тис": 1_000,
    "thousand": 1_000,
    "ezer": 1_000,             # Угорська
    "mii": 1_000,              # Румунська
    "tisíc": 1_000,            # Словацька
}

# ─── NBU API ──────────────────────────────────────────────────────────────────
_NBU_API = "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?json"
_RATE_CACHE: dict[str, float] = {}
_CACHE_DATE: Optional[date] = None


async def _fetch_nbu_rates() -> dict[str, float]:
    """
    Завантажує офіційний курс НБУ на сьогодні.
    Кешується на весь день — один запит на день.
    Повертає словник {ISO_CODE: rate_to_UAH}.
    """
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
        # Повертаємо старий кеш якщо є
        if _RATE_CACHE:
            logger.info("Using stale NBU rate cache (date=%s)", _CACHE_DATE)
            return _RATE_CACHE

    return _RATE_CACHE


def _format_uah(amount: float) -> str:
    """
    Форматує суму у гривнях з множниками.
    1_500_000 → "1,5 млн грн"
    2_300_000_000 → "2,3 млрд грн"
    """
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
        return f"{amount:,.0f} грн".replace(",", " ")

    # Обрізаємо зайві нулі після коми
    if val == int(val):
        return f"{int(val)} {label} грн"
    return f"{val:.1f} {label} грн".replace(".", ",")


def _build_currency_pattern() -> re.Pattern:
    mult_pat = r"(?P<mult>" + "|".join(_MULTIPLIERS.keys()) + r")"
    
    # ОНОВЛЕНО: Дозволяємо числам мати всередині дефіс або тире (наприклад: "4-5", "4 - 5.5")
    num_pat = r"(?P<amount>\d[\d\s,.]*(?:[-–—]\s*\d[\d\s,.]*)?)"

    all_markers: list[str] = []
    for iso, (markers, _) in _CURRENCY_CONFIG.items():
        for m in markers:
            all_markers.append(re.escape(m) if not m.startswith("(") and not m.endswith(")") else m)

    all_markers.sort(key=len, reverse=True)
    currency_pat = r"(?P<currency>" + "|".join(all_markers) + r")"

    pattern = (
        r"(?:"
        r"(?:" + num_pat + r"\s*" + mult_pat + r"?\s*" + currency_pat + r")"
        r"|"
        r"(?:" + currency_pat.replace("currency", "currency2") +
        r"\s*" + num_pat.replace("amount", "amount2") +
        r"\s*" + mult_pat.replace("mult", "mult2") + r"?)"
        r")"
    )
    return re.compile(pattern, re.IGNORECASE | re.UNICODE)


_CURRENCY_RE: Optional[re.Pattern] = None


def _get_currency_re() -> re.Pattern:
    global _CURRENCY_RE
    if _CURRENCY_RE is None:
        _CURRENCY_RE = _build_currency_pattern()
    return _CURRENCY_RE


def _parse_amount(amount_str: str) -> list[float]:
    """
    Перетворює рядок типу '1 500 000', '1.5' або '4-5' у список float.
    Повертає [1500000.0] або [4.0, 5.0].
    """
    # Розбиваємо по дефісу або тире
    parts = re.split(r'[-–—]', amount_str)
    parsed = []
    
    for p in parts:
        cleaned = p.strip().replace(" ", "").replace("\xa0", "")
        if not cleaned:
            continue
            
        # Логіка визначення десяткового розділювача
        if "." in cleaned and "," in cleaned:
            cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
            
        try:
            parsed.append(float(cleaned))
        except ValueError:
            pass
            
    return parsed


def _detect_iso(marker: str) -> Optional[str]:
    """За маркером визначає ISO-код валюти."""
    marker_lower = marker.lower().strip()
    for iso, (markers, _) in _CURRENCY_CONFIG.items():
        for m in markers:
            # прибираємо regex-специфіку для простого порівняння
            m_clean = re.sub(r'[\\()?\[\]]', '', m).lower()
            if marker_lower in (m_clean, iso.lower()):
                return iso
            if re.match(m, marker, re.IGNORECASE):
                return iso
    return None


async def convert_currencies_in_text(text: str) -> tuple[str, dict[str, float]]:
    """
    Знаходить всі грошові суми у тексті та додає конвертацію в гривні в дужках.

    Повертає: (оновлений текст, використані курси {ISO: rate})
    """
    rates = await _fetch_nbu_rates()
    if not rates:
        return text, {}

    used_rates: dict[str, float] = {}
    
    # Delegating all the regex sub and mathematical logic to the helper
    converted_text = _apply_currency_replacements(text, rates, used_rates)
    
    return converted_text, used_rates


def _format_uah_range(uah_amounts: list[float]) -> str:
    """Форматує список сум у гривнях, склеюючи діапазони."""
    formatted = [_format_uah(a) for a in uah_amounts]
    
    if len(formatted) == 1:
        return formatted[0]
        
    if len(formatted) == 2:
        # Спроба зробити "16,8–21 млн грн" замість "16,8 млн грн – 21 млн грн"
        parts0 = formatted[0].split(' ', 1) # ['16,8', 'млн грн']
        parts1 = formatted[1].split(' ', 1) # ['21', 'млн грн']
        
        if len(parts0) == 2 and len(parts1) == 2 and parts0[1] == parts1[1]:
            # Якщо суфікси (тис/млн/млрд) однакові
            return f"{parts0[0]}–{formatted[1]}"
            
    # Якщо різні (напр. '800 тис. грн – 1,2 млн грн')
    return " – ".join(formatted)

def _apply_currency_replacements(
    text: str, rates: dict[str, float], used_rates: dict[str, float]
) -> str:
    pattern = _get_currency_re()

    def replacer(m: re.Match) -> str:
        amount_str = m.group("amount") or m.group("amount2") or ""
        mult_str   = m.group("mult")   or m.group("mult2")   or ""
        curr_str   = m.group("currency") or m.group("currency2") or ""

        if not amount_str or not curr_str:
            return m.group(0)

        # Тепер отримуємо список значень
        amounts = _parse_amount(amount_str)
        if not amounts:
            return m.group(0)

        multiplier = 1
        if mult_str:
            mult_key = mult_str.lower().rstrip(".")
            multiplier = next(
                (v for k, v in _MULTIPLIERS.items() if k.lower() == mult_key), 1
            )

        iso = _detect_iso(curr_str)
        if not iso or iso not in rates:
            return m.group(0)

        rate = rates[iso]
        used_rates[iso] = rate
        
        # Рахуємо UAH для кожного числа в діапазоні
        uah_amounts = [amt * multiplier * rate for amt in amounts]
        uah_str = _format_uah_range(uah_amounts)

        return f"{m.group(0)} ({uah_str})"

    return pattern.sub(replacer, text)


# ─── Основний клас ────────────────────────────────────────────────────────────

class TelegramLLMRewriter(ILLMRewriter):
    """
    Реалізує ILLMRewriter через будь-який ILLMClient.

    Покращення порівняно з попередньою версією:
      1. RAG style_context передається в промпт як довідкова база —
         LLM бере стиль і факти зі схожих раніше опублікованих матеріалів.
      2. Конвертація валют (USD/EUR/RON/HUF/PLN/GBP/CHF/CZK → UAH)
         з актуальним курсом НБУ, вставляється в дужках поруч із сумою
         ПЕРЕД відправкою тексту в LLM — модель вже бачить UAH і може
         природно вписати їх у резюме.
      3. Курс НБУ кешується на день — один HTTP-запит на добу.

    Всі помилки перехоплюються — повертає "" як fallback.
    """

    def __init__(self, llm_client) -> None:
        self._llm = llm_client

    async def rewrite(
        self,
        title: str,
        full_text: str,
        url: str,
        style_context: str = "",
        published_at=None
    ) -> str:
        if self._llm is None:
            return ""

        # ── 1. Конвертація валют у вихідному тексті ───────────────────────────
        enriched_text, used_rates = await convert_currencies_in_text(
            full_text[:6000]  # беремо більше тексту бо після конвертації може збільшитись
        )
        if published_at:
            from datetime import datetime
            if isinstance(published_at, str):
                article_date = published_at
            else:
                article_date = published_at.strftime("%d.%m.%Y")
        else:
            article_date = current_date
        # ── 2. Метадані для промпту ───────────────────────────────────────────
        try:
            domain = urllib.parse.urlparse(url).netloc.replace("www.", "")
        except Exception:
            domain = "unknown"

        current_date = datetime.now().strftime("%d.%m.%Y")

        # ── 3. Блок стилістичного контексту з RAG ─────────────────────────────
        style_block = ""
        if style_context and style_context.strip():
            style_block = (
                "\n\nДОВІДКОВА БАЗА (фрагменти раніше опублікованих матеріалів у потрібному стилі):\n"
                "─────────────────────────────────────────────\n"
                f"{style_context[:3000]}\n"
                "─────────────────────────────────────────────\n"
                "Використовуй ці фрагменти як ЕТАЛОН стилю, термінології та рівня деталізації. "
                "НЕ копіюй факти з довідкової бази — тільки стиль і термінологію."
            )

        # ── 4. Інформація про курси для прозорості ────────────────────────────
        rates_note = ""
        if used_rates:
            rates_lines = ", ".join(
                f"1 {iso} = {rate:.2f} грн" for iso, rate in sorted(used_rates.items())
            )
            rates_note = f"\n\nКурс НБУ на {current_date}: {rates_lines}."

        # ── 5. System prompt ──────────────────────────────────────────────────
        system = (
                "You are an expert intelligence analyst and translator. "
                "Your task is to translate and rewrite the provided news article "
                "into a strict official-business summary in Ukrainian.\n\n"
                "REQUIREMENTS:\n"
                "1. The style MUST be extremely dry, formal, and completely devoid of emotional "
                "coloring, metaphors, or subjective assessments.\n"
                "2. Identify the original publication date from the provided text. "
                "Format it as DD.MM.YYYY. "
                f"The article was published on {article_date}. Use this date unless the text explicitly mentions a different date."
                f"3. ALWAYS start the first sentence with the date and the source. "
                f"Use the format: '[Дата] за повідомленням [Назва ресурсу]' "
                f"or 'За повідомленням [Назва ресурсу] від [Дата]'. "
                f"Use the domain '{domain}'.\n"
                "4. MONETARY AMOUNTS: The source text already contains UAH equivalents in parentheses "
                "(e.g. '10 млн EUR (420 млн грн)'). PRESERVE these parenthetical UAH amounts in your "
                "output — do not remove or recalculate them.\n"
                "5. IF the text mentions specialized military terminology, weapons, technical equipment "
                "(e.g., drones, vehicles), or complex legal/political procedures, you MUST add a "
                "reference section below the main text starting with 'Довідково:'.\n"
                "6. Output ONLY the finalized Ukrainian text. Do NOT use markdown formatting "
                "(like ** or #), do not add titles, and do not include any introductions.\n"
                "7. TRANSLITERATION AND PROPER NOUNS: All proper nouns MUST be translated or "
                "transliterated into their officially accepted Ukrainian equivalents according to "
                "phonetic rules. Do NOT leave them in the original Latin alphabet. "
                "Pay special attention to specific phonetics "
                "(e.g., Slovak 'c' is 'ц', so 'Fico' → 'Фіцо'; Hungarian 'sz' is 'с', etc.).\n\n"
                "8. KEY TAGS: After the main text add on a new line:\n"
                "Ключові теги: #[tag1] #[tag2] ...\n"
                "5 to 10 tags in Ukrainian, camelCase compounds, no #новини or #стаття."
                "Rules for tags:\n"
                "  - 5 to 10 tags per article\n"
                "  - Tags MUST be in Ukrainian, written as a single word or compound without spaces "
                "(use camelCase for compounds, e.g. #державнефінансування)\n"
                "  - Cover: main topic, key actors (persons/organizations), country, sector "
                "(e.g. #економіка #політика #військо #енергетика), and any specific event type\n"
                "  - Do NOT use generic tags like #новини or #стаття\n\n"
                "TEMPLATE EXAMPLES:\n"
                f"12.04.2024 за повідомленням Інтернет-ресурсу «{domain}», міністр оборони...\n"
                f"За повідомленням агентства «Bloomberg» від {current_date}, "
                f"майбутній прем'єр-міністр...\n\n"
            )

        # ── 6. User prompt ────────────────────────────────────────────────────
        user = (
            f"Title: {title}\n\n"
            f"Text (with UAH equivalents already added):\n{enriched_text}\n\n"
            f"Source URL: {url}"
            f"{rates_note}"
            f"{style_block}\n\n"
            "Translate and rewrite the text strictly following the official summary requirements "
            "and the template. Preserve all UAH amounts in parentheses."
        )

        # ── 7. LLM call ───────────────────────────────────────────────────────
        try:
            resp = await self._llm.complete(system, user, max_tokens=8192)
            rewritten = resp.text.strip()

            # Прибираємо <think>...</think> блоки (Qwen/DeepSeek)
            rewritten = re.sub(r"<think>.*?</think>", "", rewritten, flags=re.DOTALL).strip()

            logger.info(
                "LLM rewrite done: url=%s chars=%d currencies_converted=%s",
                url,
                len(rewritten),
                list(used_rates.keys()) if used_rates else "none",
            )
            return rewritten

        except Exception as exc:
            logger.warning("LLM rewrite failed for url=%s: %s", url, exc)
            return ""