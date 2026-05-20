from __future__ import annotations

"""
application/use_cases/generate_controls_report.py
──────────────────────────────────────────────────
GenerateControlsReportUseCase

LLM аналізує статті за сьогодні (які вже пройшли threshold і були
відправлені в Telegram) та генерує структурований звіт по заходах
на контролі у форматі документа 8.

Flow:
  1. Завантажити статті за сьогодні з БД (IArticleRepository)
  2. Передати в LLM: статті → витягти майбутні заходи
  3. Повернути готовий текст для Telegram
"""

import logging
import re
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, date

from src.application.ports.rag_ports import ILLMClient
from src.domain.knowledge.repositories import IArticleRepository
from src.domain.knowledge.value_objects import ArticleFilter, ArticleStatus

logger = logging.getLogger(__name__)

_MAX_ARTICLE_CHARS = 800


@dataclass
class ControlsReportResult:
    report_text: str
    articles_used: int
    generated_at: datetime


class GenerateControlsReportUseCase:
    def __init__(
        self,
        llm_client: ILLMClient,
        controls_repo,
        session_factory,
        article_repo_factory,
    ) -> None:
        self._llm                  = llm_client
        self._controls_repo        = controls_repo
        self._session_factory      = session_factory
        self._article_repo_factory = article_repo_factory

    async def execute(
        self,
        country_filter: str | None = None,
    ) -> ControlsReportResult:

        today = date.today()

        # ── 1. Статті за сьогодні ─────────────────────────────────────────────
        async with self._session_factory() as session:
            article_repo = self._article_repo_factory(session)
            f = ArticleFilter(
                status=ArticleStatus.ACCEPTED,
                date_from=today,
                min_score=0.71,
                date_to=today,
                sort_by="created_at",
                sort_dir="desc",
                limit=200,
            )
            articles_raw = await article_repo.find(f)

        # Додатковий фільтр на випадок якщо date_from/date_to не підтримується репо
        articles = [
            a for a in articles_raw
            if (
                (a.published_at and _to_date(a.published_at) == today)
                or (a.created_at and _to_date(a.created_at) == today)
            )
        ]

        logger.info(
            "controls_report: articles=%d country_filter=%s",
            len(articles), country_filter,
        )

        # ── 2. Промпти ────────────────────────────────────────────────────────
        system_prompt = _build_system_prompt()
        user_prompt   = _build_user_prompt(articles)

        # ── 3. LLM генерація ──────────────────────────────────────────────────
        try:
            resp = await self._llm.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=4096,
            )
            report_text = resp.text.strip()
            report_text = re.sub(
                r"<think>.*?</think>", "", report_text, flags=re.DOTALL
            ).strip()

        except Exception as exc:
            logger.error("controls_report LLM failed: %s", exc)
            report_text = "Помилка генерації звіту."

        return ControlsReportResult(
            report_text=report_text,
            articles_used=len(articles),
            generated_at=datetime.now(),
        )


# ── helpers ───────────────────────────────────────────────────────────────────

def _to_date(value) -> date | None:
    """Витягує date з datetime, value-object або рядка."""
    try:
        if hasattr(value, "value"):
            value = value.value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
    except Exception:
        pass
    return None


# ── Prompt builders ───────────────────────────────────────────────────────────

def _build_system_prompt() -> str:
    today_str = datetime.now().strftime("%d.%m.%Y")
    return (
        "You are an intelligence unit analyst preparing a formal daily briefing "
        "in UKRAINIAN LANGUAGE.\n\n"
        "YOUR TASK:\n"
        "Analyze today's news articles and extract ALL mentions of future planned events "
        "that are scheduled beyond the immediate period — meaning events with a specific "
        "future date, a named month, quarter, or year. "
        "Do NOT include events happening today, tomorrow, or within the next few days. "
        "Do NOT include vague references like 'soon', 'in the near future', 'shortly'.\n\n"
        "OUTPUT FORMAT:\n"
        f"Start with header: 'ЗАХОДИ НА КОНТРОЛІ — виявлені за {today_str}'\n\n"
        "Group extracted items by COUNTRY (or 'МІЖНАРОДНИЙ РІВЕНЬ' if multi-country). "
        "Country name as a standalone line in uppercase.\n\n"
        "For each extracted event — exactly 2 lines:\n"
        "  [DD.MM.YYYY або місяць/квартал/рік] — [назва заходу та короткий зміст, "
        "1-2 речення: хто, що, з якого приводу]\n"
        "  [повне URL статті]\n\n"
        "Example output:\n"
        "УГОРЩИНА\n"
        "20.06.2026 — Засідання парламенту Угорщини з розгляду законопроєкту про "
        "державний бюджет на 2027 рік; очікується голосування за участю фракцій "
        "«Фідес» та опозиційних партій.\n"
        "https://hang.hu/belfold/example-article-123\n\n"
        "RULES:\n"
        "1. Date format: DD.MM.YYYY if exact date known; otherwise 'червень 2026', "
        "'III квартал 2026', '2027 рік' — exactly as stated in the source.\n"
        "2. Event description: noun-phrase start, then brief factual context. "
        "No verbs at the start. No opinions. No assessments.\n"
        "3. URL must be the full URL from the article header — do not shorten or modify.\n"
        "4. One blank line between events within the same country.\n"
        "5. NO markdown, NO bullet points, NO extra commentary outside the format.\n"
        "6. Extremely dry and formal. Facts only.\n"
        f"7. If no qualifying events found — write exactly: "
        f"'Запланованих заходів у новинах за {today_str} не виявлено.'\n"
    )


def _build_user_prompt(articles: list) -> str:
    lines: list[str] = []
    lines.append("=== TODAY'S NEWS ===\n")

    if not articles:
        lines.append("(no news available for today)\n")
    else:
        for i, article in enumerate(articles, 1):
            pub_date = ""
            if article.published_at:
                try:
                    dt = (
                        article.published_at.value
                        if hasattr(article.published_at, "value")
                        else article.published_at
                    )
                    pub_date = dt.strftime("%d.%m.%Y") if dt else ""
                except Exception:
                    pass

            try:
                domain = urllib.parse.urlparse(article.url).netloc.replace("www.", "")
            except Exception:
                domain = "unknown"

            body = (article.body or "").strip().replace("\n", " ")
            if len(body) > _MAX_ARTICLE_CHARS:
                body = body[:_MAX_ARTICLE_CHARS] + "…"

            lines.append(
                f"[{i}] {pub_date} | {domain} | {article.url or '—'}\n"
                f"Title: {article.title or '—'}\n"
                f"Text: {body}\n"
            )

    lines.append("=== TASK ===")
    lines.append(
        "Read ALL articles above.\n"
        "Extract ONLY future events planned beyond the immediate period "
        "(at minimum a named month or specific date in the future — not today, "
        "not tomorrow, not 'next few days').\n\n"
        "For each qualifying event output exactly 2 lines:\n"
        "Line 1: [date or period] — [event name and brief factual context, 1-2 sentences]\n"
        "Line 2: [full URL exactly as provided in the article header above]\n\n"
        "Group by country (uppercase country name as header).\n"
        "Blank line between events.\n"
        "Do not add any other text, commentary, or formatting."
    )

    return "\n".join(lines)