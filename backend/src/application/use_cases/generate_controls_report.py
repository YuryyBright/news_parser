from __future__ import annotations

"""
application/use_cases/generate_controls_report.py
──────────────────────────────────────────────────
GenerateControlsReportUseCase

LLM аналізує статті за сьогодні (які вже пройшли threshold і були
відправлені в Telegram) та генерує структурований звіт по заходах
на контролі у форматі документа 8.

Flow:
  1. Завантажити активні заходи на контролі (ControlItemsRepository)
  2. Відфільтрувати ТІЛЬКИ майбутні заходи (дата > сьогодні або без дати)
  3. Завантажити статті за сьогодні з БД (IArticleRepository)
  4. Передати в LLM: майбутні заходи + статті → аналітичний звіт
  5. Повернути готовий текст для Telegram
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

        # ── 1. Активні заходи → залишаємо тільки майбутні ────────────────────
        # all_controls = (
        #     self._controls_repo.list_by_country(country_filter)
        #     if country_filter
        #     else self._controls_repo.list_active()
        # )

        # future_controls = [
        #     c for c in all_controls
        #     if c.get("date") is None or date.fromisoformat(c["date"]) > today
        # ]

        # ── 2. Статті за сьогодні ─────────────────────────────────────────────
        async with self._session_factory() as session:
            article_repo = self._article_repo_factory(session)
            f = ArticleFilter(
                status=ArticleStatus.ACCEPTED,
                date_from=today,
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

        # ── 3. Промпти ────────────────────────────────────────────────────────
        system_prompt = _build_system_prompt()
        user_prompt   = _build_user_prompt(articles)

        # ── 4. LLM генерація ──────────────────────────────────────────────────
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
            report_text = self._controls_repo.format_block(country_filter)

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
        "You are an intelligence unit analyst. Your task is to prepare a "
        "structured report in a strict formal business style in the UKRAINIAN LANGUAGE.\n\n"
        "REQUIREMENTS:\n"
        "1. Style — extremely dry, formal, without emotions, metaphors, or subjective assessments.\n"
        "2. You receive a list of UPCOMING control items (events/tasks planned for the future). "
        "Your task is to check whether today's news contains any information relevant to these items.\n"
        "3. For each control item: if relevant news exists — cite the source and date in the format "
        "'за повідомленням [domain] від [date]' and briefly summarize (1–3 sentences). "
        "Then provide a brief situational assessment.\n"
        "4. If NO relevant news is found for an item — state explicitly: "
        "'Релевантних повідомлень за звітний період не виявлено.'\n"
        "5. IMPORTANT: Do NOT report on events that have already occurred or were mentioned as "
        "happening today. Focus ONLY on upcoming scheduled events and ongoing monitoring tasks.\n"
        f"6. Start the report with: 'ЗАХОДИ НА КОНТРОЛІ — зведення станом на {today_str}'\n"
        "7. DO NOT use markdown formatting (** # etc.). "
        "DO NOT add introductions or conclusions — output the report body ONLY.\n"
        "8. Group items by country exactly as presented in the input data.\n"
    )


def _build_user_prompt(articles: list) -> str:
    lines: list[str] = []

    # ── Блок 1: Майбутні заходи на контролі ──────────────────────────────────
    lines.append("=== UPCOMING ITEMS ON CONTROL ===\n")

    # ── Блок 2: Новини за сьогодні ────────────────────────────────────────────
    lines.append("=== TODAY'S NEWS ===\n")

    if not articles:
        lines.append("(no news available for today)")
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
                f"[{i}] {pub_date} | {domain}\n"
                f"Title: {article.title or '—'}\n"
                f"Text: {body}\n"
            )

    # ── Блок 3: Завдання ──────────────────────────────────────────────────────
    lines.append("=== TASK ===")
    lines.append(
        "Using today's news, analyze each UPCOMING control item. "
        "For each item state: whether today's news contains relevant information, "
        "cite the source if applicable, and provide a brief situational assessment. "
        "Skip any items that have already occurred — they are not present in this list."
    )

    return "\n".join(lines)