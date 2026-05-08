import json, os
from pathlib import Path

class TelegramUserRepository:
    def __init__(self, path: str = "./data/telegram_subscribers.json"):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._subscribers: set[int] = self._load()

    def _load(self) -> set[int]:
        if self._path.exists():
            return set(json.loads(self._path.read_text()))
        return set()

    def _save(self) -> None:
        self._path.write_text(json.dumps(list(self._subscribers)))

    def add(self, chat_id: int) -> bool:
        is_new = chat_id not in self._subscribers
        self._subscribers.add(chat_id)
        self._save()
        return is_new

    def remove(self, chat_id: int) -> None:
        self._subscribers.discard(chat_id)
        self._save()

    def all(self) -> list[int]:
        return list(self._subscribers)