# src/infrastructure/adapters/azure_translator.py
import httpx
import logging
from src.application.ports.translator import ITranslator

logger = logging.getLogger(__name__)

class AzureTranslator(ITranslator):
    def __init__(self, endpoint: str, api_key: str, region: str):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.region = region

    async def translate(self, text: str, target_lang: str, source_lang: str | None = None) -> str:
        if not text:
            return ""

        path = '/translate'
        url = self.endpoint + path
        
        params = {
            'api-version': '3.0',
            'to': target_lang
        }
        if source_lang and source_lang != "unknown":
            params['from'] = source_lang

        headers = {
            'Ocp-Apim-Subscription-Key': self.api_key,
            'Ocp-Apim-Subscription-Region': self.region,
            'Content-type': 'application/json'
        }
        
        # Azure приймає масив об'єктів
        body = [{'text': text}]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, params=params, headers=headers, json=body)
                response.raise_for_status()
                result = response.json()
                
                # Повертаємо перекладений текст
                return result[0]['translations'][0]['text']
        except Exception as exc:
            logger.error(f"Azure Translation failed: {exc}")
            # У разі помилки можна повертати оригінал або кидати кастомний exception
            return text