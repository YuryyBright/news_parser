import logging
import re
import urllib.parse
from datetime import datetime, date
from typing import Optional

import httpx

from src.application.ports.llm_rewriter import ILLMRewriter

logger = logging.getLogger(__name__)

# ─── Валюти для курсів НБУ ────────────────────────────────────────────────────
_TRACKED_CURRENCIES = {"USD", "EUR", "RON", "HUF", "PLN", "GBP", "CHF", "CZK"}

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
            if code and rate and code in _TRACKED_CURRENCIES:
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


# ─── Основний клас ────────────────────────────────────────────────────────────

class TelegramLLMRewriter(ILLMRewriter):
    """
    Реалізує ILLMRewriter через будь-який ILLMClient.
    Курси НБУ (USD/EUR/RON/HUF/PLN/GBP/CHF/CZK → UAH) передаються в промпт,
    конвертація виконується самим LLM.
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

        # ── 1. Завантажуємо курси НБУ ─────────────────────────────────────────
        rates = await _fetch_nbu_rates()

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

        # ── 4. Блок курсів НБУ для промпту ────────────────────────────────────
        if rates:
            rates_lines = "\n".join(
                f"  1 {iso} = {rate:.4f} грн"
                for iso, rate in sorted(rates.items())
            )
            rates_block = (
                f"\nАКТУАЛЬНІ КУРСИ НБУ на {current_date}:\n"
                f"{rates_lines}\n"
            )
        else:
            rates_block = ""

        # ── 5. Блок стилістичного контексту (RAG) ────────────────────────────
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

        # ── 6. System prompt ──────────────────────────────────────────────────
        system = (
            "Роль: перекладач та аналітик офіційно-ділових текстів.\n\n"
            "ЗАВДАННЯ:\n"
            "Перекласти та переписати новинну статтю у вигляді стислої офіційної довідки "
            "українською мовою. Стиль — суворий канцелярсько-діловий: нейтральний, фактологічний, "
            "без оцінних суджень, метафор та емоційного забарвлення. Текст має бути написаний суцільною прозою.\n\n"
            "ОБОВ'ЯЗКОВІ ВИМОГИ ЩОДО СТРУКТУРИ ТА СТИЛЮ:\n"
            f"1. ВСТУПНА ФРАЗА. Перше речення ПОВИННО починатися виключно за цим шаблоном:\n"
            f"   «За повідомленням [Інтернет-ресурсу / інформаційного агентства] «{domain}» від {article_date}, [Хто] [зробив що]...»\n"
            "2. ДРУГЕ РЕЧЕННЯ (ПЕРЕХІД). Друге речення ПОВИННЕ починатися точною фразою:\n"
            "   «З даного приводу зазначається, що...» (і далі розкривається суть події).\n"
            "3. ФОРМАТ (ПРОЗА). Писати суцільним текстом (1-2 стислі абзаци). Жодних списків, маркерів, "
            "заголовків чи Markdown-розмітки (**, ##, __ тощо).\n"
            "4. ГРОШОВІ СУМИ. Кожну грошову суму в іноземній валюті ОБОВ'ЯЗКОВО супроводжувати "
            "еквівалентом у гривнях у дужках, використовуючи надані курси НБУ. "
            "Формат: «10 млн EUR (понад 460 млн грн)». Великі суми скорочувати: млн, млрд. "
            "Якщо валюти немає в курсах НБУ — залишити без конвертації.\n"
            "5. ВЛАСНІ НАЗВИ. Усі власні назви та імена транслітерувати або перекладати "
            "відповідно до чинних українських норм. Фонетичні правила: словацька «c» → «ц» (Fico → Фіцо); "
            "угорська «sz» → «с». Латиниця у тексті не допускається (окрім оригінальних назв компаній за потреби).\n\n"
            "ЗАБОРОНЕНО:\n"
            "— Вступні або підсумкові фрази від власної особи (наприклад: «Ось довідка:», «Переклад:»).\n"
            "— Будь-яке емоційне забарвлення, публіцистичний стиль або зайва вода.\n"
            "— Копіювання фактів з еталонних фрагментів (якщо такі надані).\n\n"
            "ВИВОДИТИ: лише готовий стислий текст офіційної довідки."
        )

        # ── 7. User prompt ────────────────────────────────────────────────────
        user = (
            f"Заголовок: {title}\n\n"
            f"Текст статті:\n{full_text[:6000]}\n\n"
            f"URL джерела: {url}"
            f"{rates_block}"
            f"{style_block}\n\n"
            "Згенеруй офіційну довідку прозою. Обов'язково почни з «За повідомленням...», "
            "а друге речення почни з «З даного приводу зазначається, що...». "
            "Усі грошові суми в іноземній валюті перерахуй у гривні за наданими курсами НБУ "
            "та вкажи еквівалент у дужках. Текст має бути максимально стислим та безоціночним."
        )

        # ── 8. LLM call ───────────────────────────────────────────────────────
        try:
            resp = await self._llm.complete(system, user, max_tokens=8192)
            rewritten = resp.text.strip()

            # Прибираємо <think>...</think> блоки (Qwen/DeepSeek)
            rewritten = re.sub(r"<think>.*?</think>", "", rewritten, flags=re.DOTALL).strip()

            logger.info(
                "LLM rewrite done: url=%s chars=%d rates_loaded=%s",
                url,
                len(rewritten),
                bool(rates),
            )
            return rewritten

        except Exception as exc:
            logger.warning("LLM rewrite failed for url=%s: %s", url, exc)
            return ""