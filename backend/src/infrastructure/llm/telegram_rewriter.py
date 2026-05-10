import logging
import urllib.parse
from datetime import datetime
from src.application.ports.llm_rewriter import ILLMRewriter

logger = logging.getLogger(__name__)

class TelegramLLMRewriter(ILLMRewriter):
    """
    Реалізує ILLMRewriter через будь-який ILLMClient.
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
        if self._llm is None:
            return ""

        # Витягуємо домен для підпису (наприклад: pravda.sk, mti.hu)
        try:
            domain = urllib.parse.urlparse(url).netloc.replace("www.", "")
        except Exception:
            domain = "unknown"

        # Поточна дата для підпису у форматі DD.MM.YYYY
        current_date = datetime.now().strftime("%d.%m.%Y")

        system = (
            "You are an expert intelligence analyst and translator. Your task is to translate and rewrite the provided news article into a strict official-business summary in Ukrainian.\n\n"
            "REQUIREMENTS:\n"
            "1. The style MUST be extremely dry, formal, and completely devoid of emotional coloring, metaphors, or subjective assessments.\n"
            f"2. ALWAYS start the first sentence with the date and the source of the information. Use the format: 'DD.MM.YYYY за повідомленням [Назва ресурсу/агентства], ...' or 'За повідомленням [Назва ресурсу/агентства] від DD.MM.YYYY, ...'. Use the domain '{domain}' or the specific agency mentioned in the text.\n"
            "3. IF the text mentions specialized military terminology, weapons, technical equipment (e.g., drones, vehicles), or complex legal/political procedures, you MUST add a reference section below the source attribution starting with 'Довідково:'.\n"
            "4. Output ONLY the finalized Ukrainian text. Do NOT use markdown formatting (like ** or #), do not add titles, and do not include any introductions.\n\n"
            "TEMPLATE EXAMPLES:\n"
            f"14.04.2026 за повідомленням Інтернет-ресурсу «{domain}», міністр оборони СР Роберт Каліняк повідомив...\n"
            f"За повідомленням агентства «Bloomberg» від 29.04.2026, майбутній прем’єр-міністр Угорщини...\n"
            "Довідково: SERE Charlie (або Рівень C) — це найвищий та найінтенсивніший рівень підготовки військовослужбовців..."
        )

        user = (
            f"Title: {title}\n\n"
            f"Text: {full_text[:3000]}\n\n"
            f"Source URL: {url}\n\n"
            "Translate and rewrite the text strictly following the official summary requirements and the template."
        )

        try:
            # Використовуємо no_think параметри для блокування reasoning процесу
            resp = await self._llm.complete(system, user, max_tokens=8192)
            
            # Очищуємо від можливих тегів <think>, якщо вони все ж просочилися
            rewritten = resp.text.strip()
            import re
            rewritten = re.sub(r'<think>.*?</think>', '', rewritten, flags=re.DOTALL).strip()

            logger.info(
                "LLM rewrite done: url=%s chars=%d",
                url, len(rewritten),
            )
            return rewritten
        except Exception as exc:
            logger.warning("LLM rewrite failed for url=%s: %s", url, exc)
            return ""