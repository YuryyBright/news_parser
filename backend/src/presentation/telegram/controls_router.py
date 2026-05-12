from __future__ import annotations

"""
presentation/telegram/controls_router.py
─────────────────────────────────────────
Telegram-команди для управління «Заходами на контролі».

Команди:
    /controls           — LLM-звіт по всіх заходах на основі останніх новин
    /controls sk|hu|ro  — звіт тільки по одній країні
    /controls_list      — просто список заходів БЕЗ LLM (швидко)
    /add_control        — додати один захід
    /add_controls       — масово додати заходи (блок у форматі документа 8)
    /del_control <id>   — зняти захід з контролю
    /clear_controls     — очистити всі (тільки адміни)

Інтеграція в bot.py:
    from src.presentation.telegram.controls_router import controls_router, setup_controls
    setup_controls(
        controls_repo=ControlItemsRepository(),
        report_use_case=GenerateControlsReportUseCase(...),
        admin_ids={123456789},
    )
    dp.include_router(controls_router)
"""

import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

logger = logging.getLogger(__name__)

controls_router = Router()

_controls_repo   = None    # ControlItemsRepository
_report_use_case = None    # GenerateControlsReportUseCase
_admin_ids: set[int] = set()

_MAX_MSG_LEN = 4000

_COUNTRY_ALIASES = {
    "sk": "Словацька Республіка",
    "hu": "Угорщина",
    "ro": "Румунія",
    "md": "Молдова",
    "pl": "Польща",
    "at": "Австрія",
    "cz": "Чехія",
}


def setup_controls(
    controls_repo,
    report_use_case=None,
    admin_ids: set[int] | None = None,
) -> None:
    """
    Ініціалізує роутер. Викликати перед dp.include_router().

    Args:
        controls_repo:   ControlItemsRepository
        report_use_case: GenerateControlsReportUseCase (якщо None — /controls
                         повертає просто список без LLM-аналізу)
        admin_ids:       chat_id адміністраторів для /clear_controls
    """
    global _controls_repo, _report_use_case, _admin_ids
    _controls_repo   = controls_repo
    _report_use_case = report_use_case
    _admin_ids       = set(admin_ids) if admin_ids else set()


def _is_admin(chat_id: int) -> bool:
    return not _admin_ids or chat_id in _admin_ids


def _resolve_country(arg: str | None) -> str | None:
    if not arg:
        return None
    stripped = arg.strip().lower()
    return _COUNTRY_ALIASES.get(stripped, arg.strip())


# ── /controls [country] — LLM-звіт ───────────────────────────────────────────

@controls_router.message(Command("controls"))
async def cmd_controls(message: Message, command: CommandObject) -> None:
    """
    Генерує LLM-аналітичний звіт по заходах на контролі
    на основі останніх відправлених в Telegram статей.

    /controls       — всі заходи
    /controls sk    — тільки Словаччина
    /controls hu    — тільки Угорщина
    """
    assert _controls_repo is not None, "setup_controls() не викликано"

    country_filter = _resolve_country(command.args)

    # Якщо use case не підключено — fallback на простий список
    if _report_use_case is None:
        block = _controls_repo.format_block(country_filter)
        if not block:
            await message.answer("📋 Активних заходів на контролі немає.")
        else:
            for chunk in _split_text(block, _MAX_MSG_LEN):
                await message.answer(chunk, parse_mode="HTML")
        return

    country_label = f" ({country_filter})" if country_filter else ""
    wait_msg = await message.answer(
        f"⏳ Генерую аналітичний звіт по заходах на контролі{country_label}…\n"
        f"Аналізую останні новини, зачекайте."
    )

    try:
        result = await _report_use_case.execute(country_filter=country_filter)
    except Exception as exc:
        logger.error("controls_report failed: %s", exc)
        await wait_msg.delete()
        await message.answer(
            "❌ Помилка генерації звіту. "
            "Спробуйте /controls_list для простого списку."
        )
        return

    await wait_msg.delete()

    if not result.report_text:
        await message.answer("📋 Активних заходів на контролі немає.")
        return

    footer = (
        f"\n\n<i>📊 Проаналізовано {result.articles_used} новин · "
        f"{result.generated_at.strftime('%d.%m.%Y %H:%M')}</i>"
    )

    full_text = _escape(result.report_text) + footer

    for chunk in _split_text(full_text, _MAX_MSG_LEN):
        await message.answer(chunk, parse_mode="HTML")

    logger.info(
        "controls_report sent: country=%s articles=%d to=%d",
        country_filter, result.articles_used, message.chat.id,
    )


# ── /controls_list — простий список без LLM ──────────────────────────────────

@controls_router.message(Command("controls_list"))
async def cmd_controls_list(message: Message, command: CommandObject) -> None:
    """Показує список заходів без LLM-аналізу (швидко)."""
    assert _controls_repo is not None

    country_filter = _resolve_country(command.args)
    block = _controls_repo.format_block(country_filter)

    if not block:
        label = f" для «{country_filter}»" if country_filter else ""
        await message.answer(f"📋 Активних заходів на контролі{label} немає.")
        return

    for chunk in _split_text(block, _MAX_MSG_LEN):
        await message.answer(chunk, parse_mode="HTML")


# ── /add_control ──────────────────────────────────────────────────────────────

@controls_router.message(Command("add_control"))
async def cmd_add_control(message: Message, command: CommandObject) -> None:
    """
    Додає один захід.

    Приклади:
        /add_control Угорщина: відстеження конференції Фідес 28.04.2026
        /add_control відстеження візиту Фіцо до України
    """
    assert _controls_repo is not None

    if not command.args or not command.args.strip():
        await message.answer(
            "ℹ️ Вкажіть текст заходу після команди.\n\n"
            "Приклади:\n"
            "<code>/add_control Угорщина: відстеження конференції Фідес 28.04.2026</code>\n"
            "<code>/add_control відстеження візиту Фіцо до України</code>",
            parse_mode="HTML",
        )
        return

    raw = command.args.strip()

    country: str | None = None
    text = raw
    if ":" in raw:
        parts     = raw.split(":", 1)
        candidate = parts[0].strip()
        if len(candidate) < 60 and not candidate.startswith("-"):
            country = candidate
            text    = parts[1].strip()

    if not text:
        await message.answer("❌ Текст заходу не може бути порожнім.")
        return

    item = _controls_repo.add(text=text, added_by=message.chat.id, country=country)

    date_info = f"\n🗓 {item['date']}" if item.get("date") else ""
    await message.answer(
        f"✅ Захід додано до контролю.\n\n"
        f"<b>{_escape(item['country'])}</b>{date_info}\n"
        f"• {_escape(item['text'])}\n\n"
        f"ID: <code>{item['id'][:8]}</code>",
        parse_mode="HTML",
    )
    logger.info("control_item added: id=%s country=%s", item["id"][:8], item["country"])


# ── /add_controls (bulk) ──────────────────────────────────────────────────────

@controls_router.message(Command("add_controls"))
async def cmd_add_controls_bulk(message: Message, command: CommandObject) -> None:
    """
    Масове додавання заходів у форматі документа 8.

    /add_controls
    Словацька Республіка:
    - 27.04.2026 відстеження візиту Фіцо до України
    - відстеження змін до виборчого законодавства

    Угорщина:
    - 28.04.2026 конференція Фідес
    """
    assert _controls_repo is not None

    if not command.args or not command.args.strip():
        await message.answer(
            "ℹ️ Вставте блок заходів одразу після команди.\n\n"
            "Формат:\n"
            "<code>/add_controls\n"
            "Словацька Республіка:\n"
            "- відстеження візиту Фіцо\n"
            "- зміни до виборчого законодавства\n\n"
            "Угорщина:\n"
            "- конференція Фідес 28.04.2026</code>",
            parse_mode="HTML",
        )
        return

    added = _controls_repo.add_bulk(raw_text=command.args, added_by=message.chat.id)

    if not added:
        await message.answer(
            "⚠️ Не вдалося розпізнати жодного заходу.\n"
            "Рядки-пункти мають починатися з «-»."
        )
        return

    by_country: dict[str, int] = {}
    for item in added:
        by_country[item["country"]] = by_country.get(item["country"], 0) + 1

    summary = [f"✅ Додано <b>{len(added)}</b> заходів на контроль:\n"]
    for country, cnt in sorted(by_country.items()):
        summary.append(f"• {_escape(country)}: {cnt} шт.")
    summary.append("\n/controls — переглянути аналіз по новинах")

    await message.answer("\n".join(summary), parse_mode="HTML")
    logger.info("control_items bulk added: count=%d by=%d", len(added), message.chat.id)


# ── /del_control <id> ─────────────────────────────────────────────────────────

@controls_router.message(Command("del_control"))
async def cmd_del_control(message: Message, command: CommandObject) -> None:
    """Знімає захід з контролю за першими 8 символами ID."""
    assert _controls_repo is not None

    if not command.args or not command.args.strip():
        await message.answer(
            "ℹ️ Вкажіть ID заходу (перші 8 символів).\n"
            "ID видно у /controls_list або після /add_control.\n\n"
            "Приклад: <code>/del_control a1b2c3d4</code>",
            parse_mode="HTML",
        )
        return

    short_id = command.args.strip().lower()
    items    = _controls_repo.list_active()
    matches  = [i for i in items if i["id"].startswith(short_id)]

    if not matches:
        await message.answer(
            f"❌ Захід з ID <code>{_escape(short_id)}</code> не знайдено.\n"
            f"Список: /controls_list",
            parse_mode="HTML",
        )
        return

    if len(matches) > 1:
        lines = ["⚠️ Знайдено кілька заходів:\n"]
        for m in matches:
            lines.append(
                f"• <code>{m['id'][:8]}</code> — "
                f"{_escape(m['country'])}: {_escape(m['text'][:60])}…"
            )
        lines.append("\nВкажіть більше символів ID.")
        await message.answer("\n".join(lines), parse_mode="HTML")
        return

    item = matches[0]
    _controls_repo.deactivate(item["id"])

    await message.answer(
        f"✅ Захід знято з контролю:\n\n"
        f"<b>{_escape(item['country'])}</b>\n"
        f"• {_escape(item['text'])}",
        parse_mode="HTML",
    )
    logger.info("control_item deactivated: id=%s by=%d", item["id"][:8], message.chat.id)


# ── /clear_controls ───────────────────────────────────────────────────────────

@controls_router.message(Command("clear_controls"))
async def cmd_clear_controls(message: Message) -> None:
    """Очищує всі активні заходи. Тільки для адмінів."""
    assert _controls_repo is not None

    if not _is_admin(message.chat.id):
        await message.answer("❌ Ця команда доступна тільки адміністраторам.")
        return

    count = _controls_repo.clear_all()
    await message.answer(
        f"🗑 Очищено <b>{count}</b> заходів на контролі.",
        parse_mode="HTML",
    )
    logger.info("control_items cleared: count=%d by=%d", count, message.chat.id)


# ── helpers ───────────────────────────────────────────────────────────────────

def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _split_text(text: str, max_len: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in text.splitlines(keepends=True):
        if current_len + len(line) > max_len and current:
            chunks.append("".join(current))
            current     = []
            current_len = 0
        current.append(line)
        current_len += len(line)

    if current:
        chunks.append("".join(current))

    return chunks