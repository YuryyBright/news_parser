"""
Telegram bot handlers — /start та /stop.

Використовує aiogram v3. Якщо aiogram не встановлений,
можна замінити на bare httpx polling (див. polling.py).

Запуск: python -m presentation.telegram.bot
"""
from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message

from src.presentation.telegram.user_repo import TelegramUserRepository

logger = logging.getLogger(__name__)

router   = Router()
user_repo: TelegramUserRepository | None = None   # ін'єкція через setup()


def setup(repo: TelegramUserRepository) -> None:
    global user_repo
    user_repo = repo


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


@router.message(Command("stop"))
async def cmd_stop(message: Message) -> None:
    assert user_repo is not None
    user_repo.remove(message.chat.id)
    await message.answer("❌ Відписано. /start — підписатись знову.")


async def run_bot(token: str, repo: TelegramUserRepository) -> None:
    setup(repo)
    bot = Bot(token=token)
    try:
        me = await bot.get_me()
        logger.info("telegram bot: logged in as @%s", me.username)
    except Exception as exc:
        logger.error("telegram bot: invalid token or network error: %s", exc)
        return
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot, allowed_updates=["message"])