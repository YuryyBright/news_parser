from __future__ import annotations
import logging
from typing import Any
import httpx
from src.application.ports.rag_ports import ILLMClient, LLMResponse

logger = logging.getLogger(__name__)

_CHAT_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterClient(ILLMClient):
    """
    ILLMClient → OpenRouter API (OpenAI-compatible).

    Підтримує будь-яку модель з openrouter.ai:
      google/gemma-3-27b-it:free
      mistralai/mistral-7b-instruct:free
      meta-llama/llama-3.1-8b-instruct:free
      тощо

    Конфігурація в settings:
      openrouter.api_key   — sk-or-v1-...
      openrouter.model     — назва моделі
      openrouter.timeout   — 60.0
      openrouter.temperature — 0.7
    """

    def __init__(
        self,
        api_key: str,
        model: str = "google/gemma-3-27b-it:free",
        timeout: float = 60.0,
        temperature: float = 0.7,
        site_url: str = "https://github.com/yourproject",
        site_name: str = "NewsBot",
    ) -> None:
        self._api_key     = api_key
        self._model       = model
        self._timeout     = timeout
        self._temperature = temperature
        self._site_url    = site_url
        self._site_name   = site_name
        self._client: httpx.AsyncClient | None = None

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            "max_tokens":  max_tokens,
            "temperature": self._temperature,
        }

        client = self._get_client()
        try:
            response = await client.post(
                _CHAT_ENDPOINT,
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise RuntimeError(f"OpenRouter timeout after {self._timeout}s") from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"OpenRouter HTTP {exc.response.status_code}: {exc.response.text[:300]}"
            ) from exc

        data = response.json()

        try:
            text   = data["choices"][0]["message"]["content"].strip()
            reason = data["choices"][0].get("finish_reason", "unknown")
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Unexpected OpenRouter response: {data}") from exc

        usage         = data.get("usage", {})
        input_tokens  = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        logger.info(
            "[openrouter] model=%s finish=%s tokens_in=%d tokens_out=%d",
            self._model, reason, input_tokens, output_tokens,
        )

        if reason == "length":
            logger.warning("[openrouter] Response truncated by max_tokens=%d", max_tokens)

        return LLMResponse(
            text=text,
            model=self._model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    async def health_check(self) -> bool:
        """Перевірка через легкий запит до /api/v1/models."""
        try:
            client = self._get_client()
            resp = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers=self._headers(),
                timeout=5.0,
            )
            resp.raise_for_status()
            logger.info("[openrouter] Health check OK")
            return True
        except Exception as exc:
            logger.warning("[openrouter] Health check failed: %s", exc)
            return False

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization":  f"Bearer {self._api_key}",
            "Content-Type":   "application/json",
            # OpenRouter рекомендує передавати ці заголовки для трасування
            "HTTP-Referer":   self._site_url,
            "X-Title":        self._site_name,
        }