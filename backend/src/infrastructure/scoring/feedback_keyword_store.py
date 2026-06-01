"""
infrastructure/scoring/feedback_keyword_store.py

Екстракція ключових слів для BM25 dynamic corpus.

Два режими:
  1. LLMKeywordExtractor  — основний, через ILLMClient (VLLMClient / OpenRouterClient).
                            LLM сама визначає важливі терміни і фільтрує
                            стоп-слова — жодних хардкодних списків не потрібно.
  2. extract_keywords()   — fallback, TF-IDF-like, без залежності від LLM.
                            Використовує STOP_WORDS тільки тут.

Логіка вибору (у DynamicCorpusManager):
  - якщо llm_extractor налаштований → LLMKeywordExtractor.extract()
  - інакше → extract_keywords() (стара поведінка, зворотна сумісність)

Формат LLM відповіді (JSON):
  {"keywords": ["слово1", "фраза два", ...]}

Якщо LLM повертає невалідний JSON або порожній список — автоматичний
fallback на extract_keywords() для того ж тексту.

Prompt-дизайн:
  - Явна інструкція повертати тільки JSON, без зайвого тексту.
  - Вказується мова тексту (hu/sk/ro/en/uk) щоб LLM не перекладала.
  - top_n передається в prompt, щоб LLM обмежила список самостійно.
  - max_tokens навмисно малий (256) — відповідь коротка, швидкий інференс.
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.application.ports.rag_ports import ILLMClient

logger = logging.getLogger(__name__)

# ── Стоп-слова — ТІЛЬКИ для TF-IDF fallback (extract_keywords) ───────────────
# LLMKeywordExtractor їх не використовує — LLM сама фільтрує стоп-слова.

STOP_WORDS: dict[str, set[str]] = {
    "uk": {
        "і", "та", "в", "у", "на", "до", "з", "за", "що", "як", "але", "або",
        "це", "той", "про", "не", "при", "по", "від", "для", "він", "вона",
        "вони", "його", "їх", "ми", "ви", "все", "ще", "вже", "тому", "через",
        "коли", "де", "хто", "між", "над",
    },
    "hu": {
        "és", "a", "az", "is", "de", "nem", "van", "egy", "hogy", "mint",
        "ezt", "azt", "vagy", "meg", "már", "még", "csak", "erre", "arra",
        "ezek", "aki", "ami",
    },
    "sk": {
        "a", "i", "v", "na", "do", "zo", "za", "sa", "je", "nie", "ale",
        "ako", "alebo", "pre", "pri", "po", "od", "ich", "sú", "ten", "tá",
        "to", "tie", "tí", "som",
    },
    "ro": {
        "și", "în", "la", "de", "cu", "pe", "că", "din", "este", "sunt",
        "sau", "dar", "nu", "mai", "se", "ale", "prin", "pentru", "după",
        "între", "care", "cel",
    },
    "en": {
        "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
        "but", "is", "was", "are", "were", "be", "has", "have", "with",
        "from", "by", "as", "that", "this", "it", "not", "also", "its",
        "their", "about", "after", "more", "all",
    },
}

# ── System / User prompts для LLM ─────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a keyword extraction engine. Your only task is to extract the most \
important topical keywords and short phrases from the given text.

Rules:
- Respond ONLY with a valid JSON object: {"keywords": ["word1", "phrase two", ...]}
- Do NOT add explanations, comments, markdown, or any text outside the JSON.
- Extract nouns, named entities, and domain-specific terms.
- Prefer the original language of the text; do NOT translate keywords.
- Exclude generic stop-words and filler words.
- Each keyword must be 1-3 words maximum.
- Return exactly the number of keywords requested (or fewer if the text is short).
"""

_USER_PROMPT_TEMPLATE = """\
Text language: {language}
Number of keywords to extract: {top_n}

Text:
{text}
"""

# ── Публічний fallback (TF-IDF-like, без LLM) ────────────────────────────────

def extract_keywords(
    text: str,
    language: str = "en",
    top_n: int = 20,
) -> list[str]:
    """
    Fallback екстракція без LLM — TF-score + власні назви + біграми.

    Стоп-слова фільтруються вручну через STOP_WORDS.
    У LLM-режимі цей список не використовується — LLM сама визначає
    що є стоп-словом для конкретної мови і контексту.

    Використовується:
      - якщо LLMKeywordExtractor не налаштований
      - якщо LLM повернула невалідний JSON або порожній список
      - у тестах без залежності від LLM
    """
    stops = STOP_WORDS.get(language, STOP_WORDS["en"])

    proper: set[str] = set()
    for sent in re.split(r"[.!?]\s+", text):
        words = sent.split()
        for w in words[1:]:
            clean = re.sub(r"[^\wа-яёіїєґА-ЯЁІЇЄҐA-Za-z\u00C0-\u024F]", "", w)
            if clean and clean[0].isupper() and len(clean) >= 3:
                proper.add(clean.lower())

    tokens = re.findall(
        r"[a-zA-Zа-яёіїєґА-ЯЁІЇЄҐ\u00C0-\u024F]{3,}",
        text.lower(),
    )
    tokens = [t for t in tokens if t not in stops]
    if not tokens:
        return []

    freq = Counter(tokens)
    total = len(tokens)
    scored: dict[str, float] = {}
    for tok, cnt in freq.items():
        tf = cnt / total
        mult = 3.0 if tok in proper else (1.5 if len(tok) >= 7 else 1.0)
        scored[tok] = tf * mult

    top_set = set(list(scored.keys())[:30])
    for i in range(len(tokens) - 1):
        if tokens[i] in top_set and tokens[i + 1] in top_set:
            bg = f"{tokens[i]} {tokens[i + 1]}"
            scored[bg] = (scored[tokens[i]] + scored[tokens[i + 1]]) * 0.6

    return [k for k, _ in sorted(scored.items(), key=lambda x: -x[1])[:top_n]]


# ── LLM-based екстрактор ──────────────────────────────────────────────────────

class LLMKeywordExtractor:
    """
    Асинхронний екстрактор ключових слів через ILLMClient.

    Підтримує будь-яку реалізацію ILLMClient:
      VLLMClient, OpenRouterClient, AnthropicLLMClient тощо.

    Fallback:
      Якщо LLM повертає невалідний JSON, порожній список або кидає виключення —
      автоматично використовується extract_keywords() (TF-IDF fallback).
      Це гарантує що DynamicCorpusManager ніколи не отримає порожній список
      через тимчасову недоступність LLM.

    Args:
        llm_client:      реалізація ILLMClient
        max_tokens:      обмеження токенів відповіді (256 достатньо для JSON-списку)
        fallback_on_error: True → при помилці LLM використати TF-IDF fallback
                           False → прокинути виключення вгору
    """

    def __init__(
        self,
        llm_client: "ILLMClient",
        max_tokens: int = 256,
        fallback_on_error: bool = True,
    ) -> None:
        self._llm = llm_client
        self._max_tokens = max_tokens
        self._fallback_on_error = fallback_on_error

    async def extract(
        self,
        text: str,
        language: str = "en",
        top_n: int = 20,
    ) -> list[str]:
        """
        Екстрагує топ-N ключових слів через LLM.

        Returns:
            Список рядків (ключових слів / фраз).
            Ніколи не повертає порожній список якщо fallback_on_error=True.

        Raises:
            Exception — якщо fallback_on_error=False і LLM недоступний.
        """
        # Обрізаємо дуже довгі тексти — LLM не потребує повного тіла статті
        # для екстракції ключових слів; перші ~1500 символів достатньо.
        truncated_text = text[:1500] if len(text) > 1500 else text

        user_prompt = _USER_PROMPT_TEMPLATE.format(
            language=language,
            top_n=top_n,
            text=truncated_text,
        )

        try:
            response = await self._llm.complete(
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=self._max_tokens,
            )
            keywords = self._parse_response(response.text)

            if not keywords:
                logger.warning(
                    "[keyword_extractor] LLM returned empty keywords list "
                    "(lang=%s, text_len=%d). Using TF-IDF fallback.",
                    language, len(text),
                )
                return extract_keywords(text, language, top_n)

            logger.debug(
                "[keyword_extractor] LLM extracted %d keywords (lang=%s): %s",
                len(keywords), language, keywords[:5],
            )
            return keywords[:top_n]

        except Exception as exc:
            if not self._fallback_on_error:
                raise

            logger.warning(
                "[keyword_extractor] LLM extraction failed (lang=%s): %s. "
                "Falling back to TF-IDF.",
                language, exc,
            )
            return extract_keywords(text, language, top_n)

    # ── Private ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_response(raw: str) -> list[str]:
        """
        Парсить JSON з відповіді LLM.

        Обробляє edge-cases:
          - зайвий текст до/після JSON (деякі моделі ігнорують інструкцію)
          - одинарні лапки замість подвійних
          - markdown-огорнений JSON (```json ... ```)

        Returns:
            Список рядків або [] якщо парсинг провалився.
        """
        if not raw:
            return []

        # Прибрати markdown-огортання якщо є
        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()

        # Спробуємо знайти JSON-об'єкт у тексті (модель могла додати пояснення)
        match = re.search(r"\{[^{}]*\}", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(0)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Остання спроба: одинарні → подвійні лапки
            try:
                data = json.loads(cleaned.replace("'", '"'))
            except json.JSONDecodeError:
                logger.debug(
                    "[keyword_extractor] Failed to parse LLM JSON: %r", raw[:200]
                )
                return []

        if not isinstance(data, dict):
            return []

        keywords = data.get("keywords", [])
        if not isinstance(keywords, list):
            return []

        # Фільтруємо: тільки непорожні рядки
        return [str(kw).strip() for kw in keywords if kw and str(kw).strip()]