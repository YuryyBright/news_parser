# infrastructure/adapters/lang_detect_adapter.py
"""
LangDetectAdapter — реалізує ILanguageDetector через бібліотеку langdetect.

Application layer знає тільки про ILanguageDetector.
Заміна langdetect → fasttext → lingua не потребує змін у use cases.
"""
from __future__ import annotations

import logging

from src.application.ports.language_detector import ILanguageDetector

logger = logging.getLogger(__name__)


class LangDetectAdapter(ILanguageDetector):

    async def detect(self, text: str) -> str:
        """
        Визначити мову тексту.

        langdetect є синхронною бібліотекою — для production
        краще винести в executor, але для MVP достатньо.
        """
        if not text or len(text.strip()) < 20:
            return "unknown"
        try:
            from langdetect import detect
            lang = detect(text)
            return lang
        except Exception as exc:
            logger.debug("langdetect failed: %s", exc)
            return "unknown"