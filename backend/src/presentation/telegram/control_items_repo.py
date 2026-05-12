from __future__ import annotations

"""
ControlItemsRepository — зберігає «Заходи на контролі» у JSON-файлі.

Формат файлу:
{
  "items": [
    {
      "id": "uuid4",
      "country": "Словацька Республіка",
      "text": "відстеження можливого візиту прем'єр-міністра СР Р. Фіцо до України",
      "date": "2026-04-27",        // ISO, null якщо немає
      "added_by": 123456789,       // chat_id Telegram
      "added_at": "2026-05-12T10:00:00",
      "active": true
    }
  ]
}

Використання:
    repo = ControlItemsRepository()
    repo.add(country="Угорщина", text="...", added_by=chat_id)
    items = repo.list_active()
    repo.deactivate(item_id)
    text_block = repo.format_block()   # готовий текст для Telegram
"""

import json
import re
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import TypedDict


class ControlItem(TypedDict):
    id: str
    country: str
    text: str
    date: str | None          # ISO date або None
    added_by: int             # Telegram chat_id
    added_at: str             # ISO datetime
    active: bool


# Відомі країни/регіони (для автовизначення з тексту)
_KNOWN_COUNTRIES = [
    "Словацька Республіка",
    "Словаччина",
    "Угорщина",
    "Румунія",
    "Молдова",
    "Польща",
    "Австрія",
    "Чехія",
    "Сербія",
    "Хорватія",
]


def _detect_country(text: str) -> str:
    """Намагається визначити країну з тексту. Fallback → 'Інше'."""
    t = text.lower()
    mapping = {
        "словацьк": "Словацька Республіка",
        "словаччин": "Словацька Республіка",
        "угорщин": "Угорщина",
        "угорськ": "Угорщина",
        "румун": "Румунія",
        "молдов": "Молдова",
        "польськ": "Польща",
        "австрі": "Австрія",
        "чеськ": "Чехія",
        "серб": "Сербія",
        "хорват": "Хорватія",
    }
    for key, country in mapping.items():
        if key in t:
            return country
    return "Інше"


def _extract_date(text: str) -> str | None:
    """
    Витягує першу дату з тексту у форматах:
      27.04.2026  |  27-04-2026  |  2026-04-27
    Повертає ISO-рядок (YYYY-MM-DD) або None.
    """
    patterns = [
        r"(\d{2})\.(\d{2})\.(\d{4})",   # DD.MM.YYYY
        r"(\d{2})-(\d{2})-(\d{4})",     # DD-MM-YYYY
        r"(\d{4})-(\d{2})-(\d{2})",     # YYYY-MM-DD (ISO)
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            groups = m.groups()
            try:
                if len(groups[0]) == 4:          # ISO вже
                    y, mo, d = groups
                else:
                    d, mo, y = groups
                return date(int(y), int(mo), int(d)).isoformat()
            except ValueError:
                continue
    return None


class ControlItemsRepository:
    """
    JSON-репозиторій для заходів на контролі.

    Методи:
        add()            — додати новий захід
        add_bulk()       — розпарсити і додати блок тексту (формат документа 8)
        list_active()    — всі активні заходи
        list_by_country()— заходи по конкретній країні
        deactivate()     — позначити захід як виконаний/знятий
        clear_all()      — очистити всі заходи (для адміна)
        format_block()   — відформатований текст для Telegram
    """

    def __init__(self, path: str = "./data/control_items.json") -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._items: list[ControlItem] = self._load()

    # ── persistence ───────────────────────────────────────────────────────────

    def _load(self) -> list[ControlItem]:
        if not self._path.exists():
            return []
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return raw.get("items", [])
        except Exception:
            return []

    def _save(self) -> None:
        payload = {"items": self._items}
        self._path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def add(
        self,
        text: str,
        added_by: int,
        country: str | None = None,
        item_date: str | None = None,
    ) -> ControlItem:
        """
        Додає один захід.

        Args:
            text:      текст заходу
            added_by:  Telegram chat_id автора
            country:   якщо None — автовизначення з тексту
            item_date: ISO-дата або None — автовизначення з тексту
        """
        resolved_country = country or _detect_country(text)
        resolved_date    = item_date or _extract_date(text)

        item: ControlItem = {
            "id":       str(uuid.uuid4()),
            "country":  resolved_country,
            "text":     text.strip(),
            "date":     resolved_date,
            "added_by": added_by,
            "added_at": datetime.now().isoformat(timespec="seconds"),
            "active":   True,
        }
        self._items.append(item)
        self._save()
        return item

    def add_bulk(self, raw_text: str, added_by: int) -> list[ControlItem]:
        """
        Розпарсує блок тексту у форматі документа 8 (заходи по країнах).

        Формат:
            Країна:
            - захід 1
            - захід 2

        Повертає список доданих заходів.
        """
        added: list[ControlItem] = []
        current_country: str = "Інше"

        for line in raw_text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            # Рядок-заголовок країни (наприклад "Словацька Республіка:" або "Угорщина:")
            if stripped.endswith(":") and not stripped.startswith("-"):
                candidate = stripped.rstrip(":").strip()
                # Перевіряємо що це не пункт (занадто довгий = не заголовок)
                if len(candidate) < 60:
                    current_country = candidate
                    continue

            # Рядок-пункт
            if stripped.startswith("-"):
                text = stripped.lstrip("-").strip()
                if text:
                    item = self.add(
                        text=text,
                        added_by=added_by,
                        country=current_country,
                        item_date=_extract_date(text),
                    )
                    added.append(item)

        return added

    def list_active(self) -> list[ControlItem]:
        """Всі активні заходи, відсортовані по країні та даті."""
        active = [i for i in self._items if i.get("active", True)]
        return sorted(
            active,
            key=lambda x: (x["country"], x["date"] or "9999-99-99"),
        )

    def list_by_country(self, country: str) -> list[ControlItem]:
        """Активні заходи конкретної країни (пошук без урахування регістру)."""
        q = country.lower()
        return [
            i for i in self.list_active()
            if q in i["country"].lower()
        ]

    def get(self, item_id: str) -> ControlItem | None:
        for i in self._items:
            if i["id"] == item_id:
                return i
        return None

    def deactivate(self, item_id: str) -> bool:
        """Знімає захід з контролю. Повертає True якщо знайдено."""
        for i in self._items:
            if i["id"] == item_id:
                i["active"] = False
                self._save()
                return True
        return False

    def clear_all(self) -> int:
        """Деактивує всі активні заходи. Повертає кількість."""
        count = 0
        for i in self._items:
            if i.get("active", True):
                i["active"] = False
                count += 1
        if count:
            self._save()
        return count

    def count_active(self) -> int:
        return sum(1 for i in self._items if i.get("active", True))

    # ── Форматування ──────────────────────────────────────────────────────────

    def format_block(self, country_filter: str | None = None) -> str:
        """
        Форматує активні заходи у Telegram-блок.

        Args:
            country_filter: якщо передано — тільки ця країна

        Повертає готовий HTML-текст для Telegram або порожній рядок.

        Приклад виводу:
            📋 <b>Заходи на контролі</b>

            <b>🇸🇰 Словацька Республіка:</b>
            • 27.04.2026 — відстеження візиту Р. Фіцо до України
            • відстеження змін до виборчого законодавства

            <b>🇭🇺 Угорщина:</b>
            • 28.04.2026 — загальна конференція партії «Фідес»
        """
        items = (
            self.list_by_country(country_filter)
            if country_filter
            else self.list_active()
        )

        if not items:
            return ""

        # Групуємо по країнах
        groups: dict[str, list[ControlItem]] = {}
        for item in items:
            groups.setdefault(item["country"], []).append(item)

        lines = ["📋 <b>Заходи на контролі</b>\n"]

        for country, citems in groups.items():
            flag = _country_flag(country)
            lines.append(f"<b>{flag}{country}:</b>")
            for ci in citems:
                date_prefix = ""
                if ci.get("date"):
                    try:
                        d = date.fromisoformat(ci["date"])
                        date_prefix = f"{d.strftime('%d.%m.%Y')} — "
                    except ValueError:
                        pass
                # Обрізаємо якщо дуже довгий
                text = ci["text"]
                if len(text) > 200:
                    text = text[:197] + "…"
                lines.append(f"• {date_prefix}{_escape(text)}")
            lines.append("")

        return "\n".join(lines).strip()

    def format_short_block(self) -> str:
        """Короткий блок: тільки кількість та країни (для хедера повідомлення)."""
        items = self.list_active()
        if not items:
            return ""
        countries = sorted({i["country"] for i in items})
        return (
            f"📋 На контролі: {len(items)} заходів "
            f"({', '.join(countries)})"
        )


# ── helpers ───────────────────────────────────────────────────────────────────

def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_FLAG_MAP = {
    "словацьк": "🇸🇰 ",
    "словаччин": "🇸🇰 ",
    "угорщин": "🇭🇺 ",
    "румун": "🇷🇴 ",
    "молдов": "🇲🇩 ",
    "польськ": "🇵🇱 ",
    "австрі": "🇦🇹 ",
    "чеськ": "🇨🇿 ",
    "серб": "🇷🇸 ",
    "хорват": "🇭🇷 ",
}


def _country_flag(country: str) -> str:
    cl = country.lower()
    for key, flag in _FLAG_MAP.items():
        if key in cl:
            return flag
    return ""