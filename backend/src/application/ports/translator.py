# src/application/ports/translator.py
from abc import ABC, abstractmethod

class ITranslator(ABC):
    @abstractmethod
    async def translate(self, text: str, target_lang: str, source_lang: str | None = None) -> str:
        """
        Перекладає текст на target_lang.
        Якщо source_lang не вказано, Azure визначить його автоматично.
        """
        pass