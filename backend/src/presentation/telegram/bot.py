from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from src.presentation.telegram.user_repo import TelegramUserRepository

logger = logging.getLogger(__name__)

router    = Router()
user_repo: TelegramUserRepository | None = None
_feedback_factory = None   # async context manager factory


def setup(repo: TelegramUserRepository, feedback_factory=None) -> None:
    global user_repo, _feedback_factory
    user_repo         = repo
    _feedback_factory = feedback_factory


# ── /start ────────────────────────────────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    assert user_repo is not None
    is_new = user_repo.add(message.chat.id)
    if is_new:
        await message.answer(
            "✅ Підписано! Надсилатиму важливі новини (score ≥ 74%).\n"
            "/stop — відписатись."
        )
    else:
        await message.answer("Ти вже підписаний. /stop — відписатись.")


# ── /stop ─────────────────────────────────────────────────────────────────────

@router.message(Command("stop"))
async def cmd_stop(message: Message) -> None:
    assert user_repo is not None
    user_repo.remove(message.chat.id)
    await message.answer("❌ Відписано. /start — підписатись знову.")


# ── 👍 / 👎 callback ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("like:") | F.data.startswith("dislike:"))
async def handle_feedback(callback: CallbackQuery) -> None:
    action, article_id = callback.data.split(":", 1)
    liked = action == "like"

    # ── 1. Одразу оновлюємо кнопки — показуємо що вибір зафіксовано ──────────
    chosen_label = "👍 Оцінено" if liked else "👎 Не цікаво"
    url = _extract_url(callback.message)

    new_rows = [[{"text": chosen_label, "callback_data": "noop"}]]
    if url:
        new_rows.append([{"text": "Читати статтю →", "url": url}])

    try:
        await callback.message.edit_reply_markup(
            reply_markup={"inline_keyboard": new_rows}
        )
    except Exception as exc:
        logger.debug("edit_reply_markup skipped: %s", exc)

    # ── 2. Підтвердження юзеру (спливаюче) ───────────────────────────────────
    await callback.answer("Дякую! Враховую 🙂" if liked else "Зрозуміло, не показуватиму схоже")

    # ── 3. Зберігаємо feedback через use case ────────────────────────────────
    if _feedback_factory is None:
        logger.debug("feedback_factory not set, skipping profile update")
        return

    try:
        import uuid
        from src.application.dtos.article_dto import SubmitFeedbackCommand

        user_uuid    = user_repo.get_user_uuid(callback.from_user.id)
        article_uuid = uuid.UUID(article_id)

        async with _feedback_factory() as (_, uc):
            await uc.execute(SubmitFeedbackCommand(
                user_id=user_uuid,
                article_id=article_uuid,
                liked=liked,
            ))

        logger.info(
            "Telegram feedback saved: user=%s article=%s liked=%s",
            user_uuid, article_uuid, liked,
        )
    except Exception as exc:
        logger.warning("Telegram feedback failed: %s", exc)


@router.callback_query(F.data == "noop")
async def handle_noop(callback: CallbackQuery) -> None:
    """Вже оцінено — нічого не робимо, просто прибираємо «годинник» в клієнті."""
    await callback.answer()


# ── helpers ───────────────────────────────────────────────────────────────────

def _extract_url(message: Message) -> str | None:
    try:
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                if getattr(btn, "url", None):
                    return btn.url
    except Exception:
        pass
    return None


# ── entry point ───────────────────────────────────────────────────────────────

async def run_bot(
    token: str,
    repo: TelegramUserRepository,
    feedback_factory=None,
) -> None:
    setup(repo, feedback_factory)
    bot = Bot(token=token)
    try:
        me = await bot.get_me()
        logger.info("telegram bot: logged in as @%s", me.username)
    except Exception as exc:
        logger.error("telegram bot: invalid token or network error: %s", exc)
        return
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])