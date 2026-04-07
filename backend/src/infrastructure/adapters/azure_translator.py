"""
AzureTranslatorAdapter — реалізує ITranslator через Azure Cognitive Services Translator.

Документація: https://learn.microsoft.com/azure/ai-services/translator/reference/v3-0-translate
Endpoint: https://api.cognitive.microsofttranslator.com/translate?api-version=3.0

Конфігурація (settings):
    azure_translator.api_key     — ключ з Azure Portal
    azure_translator.region      — наприклад "westeurope"
    azure_translator.endpoint    — (опціонально) custom endpoint
    azure_translator.target_language — "en" за замовчуванням
    azure_translator.skip_languages  — ["en", "unknown"] — не перекладати

Rate limits Azure Free tier: 2M chars/місяць.
"""
from __future__ import annotations

import logging
import uuid

import httpx

from src.application.ports.translator import ITranslator, TranslationResult, TranslationError

logger = logging.getLogger(__name__)

_AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com/"
_API_VERSION = "3.0"


class AzureTranslatorAdapter(ITranslator):

    def __init__(
        self,
        api_key: str,
        region: str,
        target_language: str = "en",
        skip_languages: list[str] | None = None,
        endpoint: str = _AZURE_ENDPOINT,
        timeout: float = 10.0,
    ) -> None:
        self._api_key = api_key
        self._region = region
        self._target_language = target_language
        self._skip_languages = set(skip_languages or ["en", "unknown"])
        self._endpoint = endpoint
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def translate(
        self,
        text: str,
        target_language: str | None = None,  # ЗМІНЕНО: Прибираємо жорстке "en"
        source_language: str | None = None,
    ) -> TranslationResult:
        if not text or not text.strip():
            return TranslationResult(text=text, detected_language=source_language)

        # ЗМІНЕНО: Беремо мову з аргументу, або ту, що в конфігурації (self._target_language)
        actual_target = target_language or self._target_language

        params = {
            "api-version": _API_VERSION,
            "to": actual_target, 
        }
        if source_language and source_language not in ("unknown", ""):
            params["from"] = source_language

        headers = {
            "Ocp-Apim-Subscription-Key": self._api_key,
            "Ocp-Apim-Subscription-Region": self._region,
            "Content-Type": "application/json",
            "X-ClientTraceId": str(uuid.uuid4()),
        }

        body = [{"text": text}]
        
        # ЗМІНЕНО: Додаємо шлях /translate до базового endpoint
        url = f"{self._endpoint.rstrip('/')}/translate"

        try:
            client = self._get_client()
            response = await client.post(
                url,  # Використовуємо правильний URL
                params=params,
                headers=headers,
                json=body,
            )
            response.raise_for_status()
            data = response.json()

            translated_text = data[0]["translations"][0]["text"]
            detected_lang = (
                data[0].get("detectedLanguage", {}).get("language")
                if source_language is None
                else source_language
            )
            return TranslationResult(text=translated_text, detected_language=detected_lang)

        except httpx.HTTPStatusError as exc:
            logger.error(
                "Azure Translator HTTP error: status=%d body=%s",
                exc.response.status_code,
                exc.response.text[:200],
            )
            raise TranslationError(f"Azure Translator failed: {exc.response.status_code}") from exc
        except Exception as exc:
            logger.error("Azure Translator unexpected error: %s", exc)
            raise TranslationError(f"Azure Translator error: {exc}") from exc

    def should_translate(self, language: str, target_language: str | None = None) -> bool:
        """
        True якщо мову треба перекладати.
        Skip: вже цільова мова, unknown, або явно в skip_languages.
        """
        if not language or language in self._skip_languages:
            return False
            
        actual_target = target_language or self._target_language
        if language == actual_target:
            return False
        return True

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()