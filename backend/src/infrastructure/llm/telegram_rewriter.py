from __future__ import annotations
import logging
from src.application.ports.llm_rewriter import ILLMRewriter

logger = logging.getLogger(__name__)

class TelegramLLMRewriter(ILLMRewriter):
    """
    Реалізує ILLMRewriter через будь-який ILLMClient
    (VLLMClient або AnthropicLLMClient — взаємозамінні).

    Всі помилки перехоплюються всередині — повертає "" як fallback.
    """

    def __init__(self, llm_client) -> None:
        self._llm = llm_client

    async def rewrite(
        self,
        title: str,
        full_text: str,
        url: str,
        style_context: str = "",
    ) -> str:
        """
        LLM-рерайт статті в стилі попередніх публікацій.

        Якщо llm_client=None або LLM впав — повертає порожній рядок,
        тоді TelegramNotifierAdapter показує звичайний RSS body як fallback.
        """
        if self._llm is None:
            return ""

        system = (
            "You are an analytical assistant. Your task is to rewrite the news into a concise, dry, and formal official summary. "
            "The output MUST be strictly in Ukrainian. "
            "Use a strict official-business style, completely devoid of emotional coloring, metaphors, or subjective assessments. "
            "Provide ONLY the final rewritten text, without any explanations, titles, or markdown formatting."
            "Use This format this text only as template: За повідомленням «Угорської телеграфної агенції» (МТІ) від 31.03.2026, заступник голови угорської опозиційної політичної партії «Демократична коаліція» Шандор Ронаї закликав до відставки міністра закордонних справ та зовнішньої торгівлі Угорщини Петера Сійярто, у зв’язку з проведення ним перемовин з міністром закордонних справ рф сергієм лавровим. Згідно заяви партії, телефонні переговори підтверджують, що П. Сійярто вчинив державну зраду.  Партія зазначає також, що П. Сійярто як член уряду Угорщини, виконував вказівки російського президента володимира путіна, а безпосередньо керував ним по телефону російський міністр закордонних справ. Наголошено, що відставка політика не врятує уряд В. Орбана на виборах 12.04.2026, але Угорщина повинна якомога швидше позбутись російських шпигунів, які працюють на керівних посадах."
        )

        # context_block = (
        #     f"Style examples (top-5 relevant publications):\n{style_context}\n\n---\n\n"
        #     if style_context else ""
        # )

        user = (
            # f"{context_block}"
            f"Title: {title}\n\n"
            f"Text: {full_text[:3000]}\n\n"
            f"Source URL: {url}\n\n"
            "Rewrite the text as a concise, formal official summary in Ukrainian."
        )

        try:
            resp = await self._llm.complete(system, user, max_tokens=4096)
            rewritten = resp.text.strip()
            logger.info(
                "LLM rewrite done: urLM rewrite done: url=%s chars=%d",
                url, len(rewritten),
            )
            return rewritten
        except Exception as exc:
            logger.warning("LLM rewrite failed for url=%s: %s", url, exc)
            return ""