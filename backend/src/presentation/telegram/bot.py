from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import BotCommand, CallbackQuery, Message

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
            "✅ Підписано! Надсилатиму важливі новини (score ≥ 74%).\n\n"
            "🌐 За замовчуванням отримуєш <b>всі мови</b>.\n"
            "Обери конкретні: /uk  /en  /ro  /sk\n"
            "Скинути фільтр: /all\n"
            "Поточні налаштування: /langs\n\n"
            "/stop — відписатись.",
            parse_mode="HTML",
        )
    else:
        await message.answer(
            "Ти вже підписаний.\n"
            "Мовний фільтр: /langs\n"
            "/stop — відписатись."
        )


# ── /stop ─────────────────────────────────────────────────────────────────────

@router.message(Command("stop"))
async def cmd_stop(message: Message) -> None:
    assert user_repo is not None
    user_repo.remove(message.chat.id)
    await message.answer("❌ Відписано. /start — підписатись знову.")


# ── мовні команди ─────────────────────────────────────────────────────────────

_LANG_LABELS: dict[str, str] = {
    "uk": "🇺🇦 Українська",
    "en": "🇬🇧 English",
    "ro": "🇷🇴 Română",
    "sk": "🇸🇰 Slovenčina",
}


def _langs_text(langs: set[str]) -> str:
    if not langs:
        return "🌐 Всі мови"
    return "  ".join(_LANG_LABELS.get(l, l.upper()) for l in sorted(langs))


async def _toggle_lang(message: Message, lang: str) -> None:
    assert user_repo is not None
    # Якщо юзер ще не підписаний — підписуємо автоматично
    user_repo.add(message.chat.id)
    new_langs = user_repo.toggle_lang(message.chat.id, lang)
    label = _langs_text(new_langs)
    hint = (
        f"Активна мова: {_LANG_LABELS[lang]} — повторна команда <b>прибирає</b> її.\n"
        f"Щоб отримувати <b>всі</b> мови — /all"
    )
    await message.answer(
        f"✅ Фільтр оновлено: {label}\n\n{hint}",
        parse_mode="HTML",
    )


@router.message(Command("uk"))
async def cmd_uk(message: Message) -> None:
    await _toggle_lang(message, "uk")


@router.message(Command("en"))
async def cmd_en(message: Message) -> None:
    await _toggle_lang(message, "en")


@router.message(Command("ro"))
async def cmd_ro(message: Message) -> None:
    await _toggle_lang(message, "ro")


@router.message(Command("sk"))
async def cmd_sk(message: Message) -> None:
    await _toggle_lang(message, "sk")


@router.message(Command("all"))
async def cmd_all(message: Message) -> None:
    assert user_repo is not None
    user_repo.add(message.chat.id)
    user_repo.set_langs(message.chat.id, set())   # порожня = всі
    await message.answer(
        "🌐 Фільтр скинуто — отримуватимеш <b>всі мови</b>.\n"
        "Обрати конкретні: /uk  /en  /ro  /sk",
        parse_mode="HTML",
    )


@router.message(Command("langs"))
async def cmd_langs(message: Message) -> None:
    assert user_repo is not None
    langs = user_repo.get_langs(message.chat.id)
    await message.answer(
        f"Поточний фільтр: <b>{_langs_text(langs)}</b>\n\n"
        "Команди (натисни повторно — вимкне):\n"
        "/uk — 🇺🇦 Українська\n"
        "/en — 🇬🇧 English\n"
        "/ro — 🇷🇴 Română\n"
        "/sk — 🇸🇰 Slovenčina\n"
        "/all — скинути, отримувати всі",
        parse_mode="HTML",
    )


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

    await bot.set_my_commands([
        BotCommand(command="start", description="Підписатись на новини"),
        BotCommand(command="stop",  description="Відписатись"),
        BotCommand(command="langs", description="Мій поточний фільтр мов"),
        BotCommand(command="uk",    description="🇺🇦 Увімк/вимк українські новини"),
        BotCommand(command="en",    description="🇬🇧 Toggle English news"),
        BotCommand(command="ro",    description="🇷🇴 Toggle știri române"),
        BotCommand(command="sk",    description="🇸🇰 Toggle slovenské správy"),
        BotCommand(command="all",   description="🌐 Отримувати всі мови"),
    ])

    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])