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
            # Дата обробки (як fallback)
            current_date = datetime.now().strftime("%d.%m.%Y")

            system = (
                "You are an expert intelligence analyst and translator. Your task is to translate and rewrite the provided news article into a strict official-business summary in Ukrainian.\n\n"
                "REQUIREMENTS:\n"
                "1. The style MUST be extremely dry, formal, and completely devoid of emotional coloring, metaphors, or subjective assessments.\n"
                "2. Identify the original publication date from the provided text. Format it as DD.MM.YYYY. "
                f"If NO date is mentioned in the text, use the current processing date: {current_date}.\n"
                f"3. ALWAYS start the first sentence with the date and the source. Use the format: '[Знайдена дата] за повідомленням [Назва ресурсу]', or 'За повідомленням [Назва ресурсу] від [Знайдена дата]'. Use the domain '{domain}'.\n"
                "4. IF the text mentions specialized military terminology, weapons, technical equipment (e.g., drones, vehicles), or complex legal/political procedures, you MUST add a reference section below the source attribution starting with 'Довідково:'.\n"
                "5. Output ONLY the finalized Ukrainian text. Do NOT use markdown formatting (like ** or #), do not add titles, and do not include any introductions.\n"
                "6. TRANSLITERATION AND PROPER NOUNS: All proper nouns (names, surnames, cities, regions, institutions) MUST be translated or transliterated into their officially accepted Ukrainian equivalents according to phonetic rules. Do NOT leave them in the original Latin alphabet. Pay special attention to specific phonetics (e.g., Slovak 'c' is 'ц', so 'Fico' must be translated as 'Фіцо', not 'Фіко'; Hungarian 'sz' is 'с', etc.). Use standard Ukrainian orthography for foreign names.\n\n"
                "TEMPLATE EXAMPLES:\n"
                f"12.04.2024 за повідомленням Інтернет-ресурсу «{domain}», міністр оборони...\n"
                f"За повідомленням агентства «Bloomberg» від {current_date}, майбутній прем’єр-міністр..."
            )

            user = (
                f"Title: {title}\n\n"
                f"Text: {full_text[:3000]}\n\n"
                f"Source URL: {url}\n\n"
                "Translate and rewrite the text strictly following the official summary requirements and the template."
            )

            try:
                resp = await self._llm.complete(system, user, max_tokens=8192)
                
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