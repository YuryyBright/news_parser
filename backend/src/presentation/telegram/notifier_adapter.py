"""
TelegramNotifierAdapter — конкретна реалізація ITelegramNotifier.

Відправляє красиве повідомлення з кнопкою-посиланням і score-bar.
Використовує httpx напряму (без aiogram) — мінімум залежностей.

Score bar: ░░░░░░░░░░ (10 символів, заповнені ▓)
parse_mode: HTML — простіший і надійніший ніж MarkdownV2
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from src.application.ports.telegram_notifier import ArticleNotification, ITelegramNotifier
from src.presentation.telegram.user_repo import TelegramUserRepository

logger = logging.getLogger(__name__)

_SCORE_BAR_LEN = 10
_SEND_DELAY    = 0.05   # щоб не вдаритись у rate limit Telegram


def _score_bar(score: float) -> str:
    filled = round(score * _SCORE_BAR_LEN)
    return "▓" * filled + "░" * (_SCORE_BAR_LEN - filled)


def _escape(text: str) -> str:
    """HTML escape — тільки три символи потрібні для Telegram HTML mode."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _build_message(article: ArticleNotification) -> str:
    bar = _score_bar(article.score)
    pct = int(article.score * 100)
    tags = "  ".join(f"#{_escape(t)}" for t in article.tags[:5]) if article.tags else ""
    lang = article.language.upper() if article.language != "unknown" else ""

    # Якщо є LLM-рерайт — використовуємо його як основний текст
    if article.rewritten_text:
        body = _escape(article.rewritten_text.strip())
    elif article.body:
        raw = article.body.strip().replace("\n", " ")
        if len(raw) > 1000:
            raw = raw[:1000].rsplit(" ", 1)[0] + "…"
        body = _escape(raw)
    else:
        body = ""

    lines = [f"📰 <b>{_escape(article.title)}</b>", ""]

    if body:
        lines += [body, ""]

    lines.append(f"<code>{bar}</code> {pct}%")

    if lang:
        lines.append(f"🌐 {lang}")
    if tags:
        lines.append(tags)

    return "\n".join(lines)


def _inline_keyboard(url: str) -> dict | None:
    # Порожній або некоректний URL → Telegram поверне 400
    if not url or not url.startswith("http"):
        return None
    return {
        "inline_keyboard": [[
            {"text": "Читати статтю →", "url": url}
        ]]
    }


class TelegramNotifierAdapter(ITelegramNotifier):

    def __init__(
        self,
        bot_token: str,
        user_repo: TelegramUserRepository,
        timeout: float = 10.0,
    ) -> None:
        self._token     = bot_token
        self._user_repo = user_repo
        self._base_url  = f"https://api.telegram.org/bot{bot_token}"
        self._timeout   = timeout

    async def notify_all(self, article: ArticleNotification) -> int:
        subscribers = self._user_repo.all()
        if not subscribers:
            logger.info("telegram: no subscribers, skip notify")
            return 0

        text     = _build_message(article)
        keyboard = _inline_keyboard(article.url)
        sent     = 0

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for chat_id in subscribers:
                try:
                    await self._send(client, chat_id, text, keyboard)
                    sent += 1
                except Exception as exc:
                    logger.warning(
                        "telegram: failed to send to chat_id=%d: %s", chat_id, exc
                    )
                await asyncio.sleep(_SEND_DELAY)

        logger.info(
            "telegram: notified %d/%d subscribers for url=%s",
            sent, len(subscribers), article.url,
        )
        return sent

    async def _send(
        self,
        client: httpx.AsyncClient,
        chat_id: int,
        text: str,
        keyboard: dict | None,
    ) -> None:
        payload: dict = {
            "chat_id":                  chat_id,
            "text":                     text,
            "parse_mode":               "HTML",
            "disable_web_page_preview": False,
        }
        if keyboard is not None:
            payload["reply_markup"] = keyboard

        resp = await client.post(
            f"{self._base_url}/sendMessage",
            json=payload,
        )
        if resp.status_code != 200:
            # Логуємо ПОВНЕ тіло — там буде точна причина від Telegram
            logger.warning(
                "telegram API error: status=%d body=%s",
                resp.status_code, resp.text,
            )
        resp.raise_for_status()