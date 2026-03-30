from langdetect import detect, LangDetectException
from src.application.ports.language_detector import ILanguageDetector

class LangDetectAdapter(ILanguageDetector):
    async def detect(self, text: str) -> str:
        try:
            return detect(text[:500])
        except LangDetectException:
            return "unknown"