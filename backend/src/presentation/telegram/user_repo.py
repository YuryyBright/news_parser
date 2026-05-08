import json
import uuid
from pathlib import Path


class TelegramUserRepository:
    def __init__(self, path: str = "./data/telegram_subscribers.json"):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict = self._load()   # {"subscribers": [...], "user_map": {...}}

    def _load(self) -> dict:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text())
                # backward compat: старий формат був просто списком
                if isinstance(data, list):
                    return {"subscribers": data, "user_map": {}}
                return data
            except Exception:
                pass
        return {"subscribers": [], "user_map": {}}

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._data))

    def add(self, chat_id: int) -> bool:
        subs = self._data["subscribers"]
        is_new = chat_id not in subs
        if is_new:
            subs.append(chat_id)
        # Генеруємо детермінований UUID якщо ще немає
        umap = self._data.setdefault("user_map", {})
        if str(chat_id) not in umap:
            umap[str(chat_id)] = str(uuid.uuid5(uuid.NAMESPACE_URL, f"tg:{chat_id}"))
        self._save()
        return is_new

    def remove(self, chat_id: int) -> None:
        self._data["subscribers"].discard  # set-compatible
        subs = self._data["subscribers"]
        if chat_id in subs:
            subs.remove(chat_id)
        self._save()

    def all(self) -> list[int]:
        return list(self._data["subscribers"])

    def get_user_uuid(self, chat_id: int) -> uuid.UUID:
        """Повертає стабільний UUID для telegram chat_id."""
        umap = self._data.get("user_map", {})
        raw = umap.get(str(chat_id))
        if raw:
            return uuid.UUID(raw)
        # fallback — детермінований
        return uuid.uuid5(uuid.NAMESPACE_URL, f"tg:{chat_id}")