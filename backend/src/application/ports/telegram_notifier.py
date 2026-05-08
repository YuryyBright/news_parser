"""
ITelegramNotifier — port (абстракція) для відправки повідомлень у Telegram.

Живе в application/ports/ — application шар залежить від абстракції,
а не від конкретної бібліотеки (aiogram / httpx).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ArticleNotification:
    title: str
    body: str
    url: str
    score: float
    tags: list[str]
    language: str
    full_text: str = ""
    style_context: str = ""
    rewritten_text: str = ""  


class ITelegramNotifier(ABC):
    @abstractmethod
    async def notify_all(self, article: ArticleNotification) -> int:
        """Відправити повідомлення всім підписникам. Повертає кількість відправлень."""
        ...