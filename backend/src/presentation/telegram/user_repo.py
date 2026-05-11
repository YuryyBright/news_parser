from __future__ import annotations

import json
import uuid
from pathlib import Path


class TelegramUserRepository:
    """
    Зберігає підписників у JSON-файлі.

    Формат файлу:
    {
        "user_map": {
            "<chat_id>": {
                "uuid": "...",
                "langs": ["uk", "en"]   // порожній список = всі мови
            }
        }
    }
    """

    def __init__(self, path: str = "./data/telegram_subscribers.json") -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # chat_id (int) -> {"uuid": str, "langs": set[str]}
        self._users: dict[int, dict] = self._load()

    # ── persistence ───────────────────────────────────────────────────────────

    def _load(self) -> dict[int, dict]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text())
        except Exception:
            return {}

        # ── backward compat ───────────────────────────────────────────────────
        # Старий формат 1: просто список chat_id
        if isinstance(raw, list):
            return {
                cid: {
                    "uuid": str(uuid.uuid5(uuid.NAMESPACE_URL, f"tg:{cid}")),
                    "langs": set(),
                }
                for cid in raw
            }

        # Старий формат 2: {"subscribers": [...], "user_map": {...}}
        if "subscribers" in raw:
            umap = raw.get("user_map", {})
            users: dict[int, dict] = {}
            for cid in raw["subscribers"]:
                icid = int(cid)
                users[icid] = {
                    "uuid": umap.get(
                        str(cid),
                        str(uuid.uuid5(uuid.NAMESPACE_URL, f"tg:{cid}"))
                    ),
                    "langs": set(),
                }
            return users

        # Новий формат: {"user_map": {"<chat_id>": {"uuid": ..., "langs": [...]}}}
        users = {}
        for key, entry in raw.get("user_map", {}).items():
            icid = int(key)
            users[icid] = {
                "uuid":  entry.get(
                    "uuid",
                    str(uuid.uuid5(uuid.NAMESPACE_URL, f"tg:{icid}"))
                ),
                "langs": set(entry.get("langs", [])),
            }
        return users

    def _save(self) -> None:
        payload = {
            "user_map": {
                str(cid): {
                    "uuid":  entry["uuid"],
                    "langs": sorted(entry["langs"]),   # set -> sorted list для JSON
                }
                for cid, entry in self._users.items()
            }
        }
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    # ── підписка ──────────────────────────────────────────────────────────────

    def add(self, chat_id: int) -> bool:
        """Додає підписника. Повертає True якщо юзер новий."""
        if chat_id in self._users:
            return False
        self._users[chat_id] = {
            "uuid":  str(uuid.uuid5(uuid.NAMESPACE_URL, f"tg:{chat_id}")),
            "langs": set(),
        }
        self._save()
        return True

    def remove(self, chat_id: int) -> None:
        if chat_id in self._users:
            del self._users[chat_id]
            self._save()

    def all(self) -> list[int]:
        return list(self._users.keys())

    # ── мовні фільтри ─────────────────────────────────────────────────────────

    def get_langs(self, chat_id: int) -> set[str]:
        """Повертає вибрані мови. Порожня множина = всі."""
        entry = self._users.get(chat_id)
        return set(entry["langs"]) if entry else set()

    def set_langs(self, chat_id: int, langs: set[str]) -> None:
        """Встановлює мовний фільтр. langs=set() означає 'all'."""
        self.add(chat_id)   # no-op якщо вже є
        self._users[chat_id]["langs"] = set(langs)
        self._save()

    def toggle_lang(self, chat_id: int, lang: str) -> set[str]:
        """
        Додає мову якщо її немає, прибирає якщо вже є.
        Повертає актуальний набір після зміни.
        """
        self.add(chat_id)   # no-op якщо вже є
        langs = self._users[chat_id]["langs"]
        if lang in langs:
            langs.discard(lang)
        else:
            langs.add(lang)
        self._save()
        return set(langs)

    def subscribers_for_lang(self, lang: str) -> list[int]:
        """
        Повертає chat_id підписників, яким потрібна ця мова.
        Юзери з порожнім фільтром (all) отримують усі мови.
        """
        return [
            cid for cid, entry in self._users.items()
            if not entry["langs"] or lang in entry["langs"]
        ]

    # ── uuid ──────────────────────────────────────────────────────────────────

    def get_user_uuid(self, chat_id: int) -> uuid.UUID:
        """Повертає стабільний UUID для telegram chat_id."""
        self.add(chat_id)   # no-op якщо вже є
        return uuid.UUID(self._users[chat_id]["uuid"])