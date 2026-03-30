# application/ports/language_detector.py
from abc import ABC, abstractmethod

class ILanguageDetector(ABC):
    @abstractmethod
    async def detect(self, text: str) -> str: ...  # повертає ISO 639-1 або "unknown"


