from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import httpx

from src.application.ports.telegram_notifier import ArticleNotification, ITelegramNotifier
from src.presentation.telegram.user_repo import TelegramUserRepository

logger = logging.getLogger(__name__)

_SCORE_BAR_LEN = 10
_SEND_DELAY    = 0.05
_MAX_TELEGRAM_LEN = 4096
_REWRITTEN_CAP    = 2800   # leaves ~1200 for title/body/meta


def _build_message(article: ArticleNotification) -> str:
    lines = []

    if article.title or article.body:
        lines.append("📝 <b>Фрагмент новини:</b>")

        if article.title:
            lines.append(f"<b>{_escape(article.title)}</b>\n")

        if article.body:
            raw_body = article.body.strip().replace("\n", " ")
            if len(raw_body) > 1500:
                raw_body = raw_body[:1500].rsplit(" ", 1)[0] + "…"
            lines.append(_escape(raw_body))
            lines.append("")

        if article.rewritten_text:
            rewritten = article.rewritten_text.strip()
            # ── FIX 1: cap rewritten text so the whole message fits ──────
            if len(rewritten) > _REWRITTEN_CAP:
                rewritten = rewritten[:_REWRITTEN_CAP].rsplit("\n", 1)[0] + "\n…"
            lines.append("—" * 20)
            escaped_rewritten = _escape(rewritten)
            escaped_url = _escape(article.url)
            lines.append(f"<code>{escaped_rewritten}\n{escaped_url}</code>")
            lines.append("")
            lines.append("—" * 20)
            lines.append("")

    bar = _score_bar(article.score)
    pct = int(article.score * 100)
    tags = "  ".join(f"#{_escape(t)}" for t in article.tags[:5]) if article.tags else ""
    lang = article.language.upper() if article.language != "unknown" else ""
    date_str = _format_date(article.published_at)

    lines.append(f"<code>{bar}</code> {pct}%")

    if date_str:
        lines.append(f"🗓 {date_str}")
    if lang:
        lines.append(f"🌐 Джерело: {lang}")
    if tags:
        lines.append(tags)

    return "\n".join(lines)


def _split_message(text: str, max_len: int = _MAX_TELEGRAM_LEN) -> list[str]:
    """Split at paragraph → newline → space boundary. Safety net for FIX 1 misses."""
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        for sep in ("\n\n", "\n", " "):
            pos = text.rfind(sep, 0, max_len)
            if pos != -1:
                break
        else:
            pos = max_len
        chunks.append(text[:pos].strip())
        text = text[pos:].strip()
    return chunks

def _score_bar(score: float) -> str:
    filled = round(score * _SCORE_BAR_LEN)
    return "▓" * filled + "░" * (_SCORE_BAR_LEN - filled)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _format_date(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.strftime("%d.%m.%Y, %H:%M")


def _build_message(article: ArticleNotification) -> str:
    lines = []

    if article.title or article.body:
        lines.append("📝 <b>Фрагмент новини:</b>")

        if article.title:
            lines.append(f"<b>{_escape(article.title)}</b>\n")

        if article.body:
            raw_body = article.body.strip().replace("\n", " ")
            if len(raw_body) > 1500:
                raw_body = raw_body[:1500].rsplit(" ", 1)[0] + "…"
            lines.append(_escape(raw_body))
            lines.append("")

        if article.rewritten_text:
            rewritten = article.rewritten_text.strip()
            # ── FIX 1: cap rewritten text so the whole message fits ──────
            if len(rewritten) > _REWRITTEN_CAP:
                rewritten = rewritten[:_REWRITTEN_CAP].rsplit("\n", 1)[0] + "\n…"
            lines.append("—" * 20)
            escaped_rewritten = _escape(rewritten)
            escaped_url = _escape(article.url)
            
            # Now this tag will safely stay inside a single Telegram message
            lines.append(f"<code>{escaped_rewritten}\n{escaped_url}</code>")
            lines.append("")
            lines.append("—" * 20)
            lines.append("")

    bar = _score_bar(article.score)
    pct = int(article.score * 100)
    tags = "  ".join(f"#{_escape(t)}" for t in article.tags[:5]) if article.tags else ""
    lang = article.language.upper() if article.language != "unknown" else ""
    date_str = _format_date(article.published_at)

    lines.append(f"<code>{bar}</code> {pct}%")

    if date_str:
        lines.append(f"🗓 {date_str}")
    if lang:
        lines.append(f"🌐 Джерело: {lang}")
    if tags:
        lines.append(tags)

    return "\n".join(lines)


def _inline_keyboard(url: str, article_id: str) -> dict:
    rows = [
        [
            {"text": "👍", "callback_data": f"like:{article_id}"},
            {"text": "👎", "callback_data": f"dislike:{article_id}"},
        ]
    ]
    if url and url.startswith("http"):
        rows.append([{"text": "Читати статтю →", "url": url}])
    return {"inline_keyboard": rows}


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
        # Беремо тільки тих підписників, які хочуть цю мову
        lang = (article.language or "unknown").lower()
        subscribers = self._user_repo.subscribers_for_lang(lang)

        if not subscribers:
            logger.info(
                "telegram: no subscribers for lang=%s, skip notify (url=%s)",
                lang, article.url,
            )
            return 0

        text     = _build_message(article)
        keyboard = _inline_keyboard(article.url, str(article.id))
        sent     = 0

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for chat_id in subscribers:
                try:
                    await self._send(client, chat_id, text, keyboard)
                    sent += 1
                except Exception as exc:
                    logger.warning("telegram: failed chat_id=%d: %s", chat_id, exc)
                await asyncio.sleep(_SEND_DELAY)

        logger.info(
            "telegram: notified %d/%d for lang=%s url=%s",
            sent, len(subscribers), lang, article.url,
        )
        return sent

    async def _send(
        self,
        client: httpx.AsyncClient,
        chat_id: int,
        text: str,
        keyboard: dict,
    ) -> None:
        chunks = _split_message(text)
        for i, chunk in enumerate(chunks):
            # Only attach the keyboard (like/dislike + read link) to the last chunk
            payload = {
                "chat_id":                  chat_id,
                "text":                     chunk,
                "parse_mode":               "HTML",
                "disable_web_page_preview": False,
                "reply_markup":             keyboard if i == len(chunks) - 1 else {},
            }
            resp = await client.post(f"{self._base_url}/sendMessage", json=payload)
            if resp.status_code != 200:
                logger.warning(
                    "telegram API error: status=%d body=%s",
                    resp.status_code, resp.text,
                )
            resp.raise_for_status()
            if i < len(chunks) - 1:
                await asyncio.sleep(0.3)   # avoid hitting Telegram's rate limit