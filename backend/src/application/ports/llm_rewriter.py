from __future__ import annotations
from abc import ABC, abstractmethod


class ILLMRewriter(ABC):
    """
    Порт для LLM-рерайту тексту.
    Відокремлений від ILLMClient щоб application layer
    не залежав від RAG-специфічного інтерфейсу.
    """
    @abstractmethod
    async def rewrite(
        self,
        title: str,
        full_text: str,
        url: str,
        style_context: str = "",
    ) -> str:
        """
        Повертає рерайт для Telegram-посту.
        При будь-якій помилці — повертає порожній рядок (не кидає виняток).
        """
        ...