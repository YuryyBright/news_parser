# infrastructure/llm/vllm_client.py
"""
VLLMClient — реалізує ILLMClient через vLLM OpenAI-compatible API.

vLLM запускає локальний сервер з ендпоінтами OpenAI:
  POST /v1/chat/completions
  POST /v1/completions
  GET  /v1/models

Конфігурація в settings:
  vllm.base_url          — http://localhost:8000 (або IP контейнера)
  vllm.model             — "mistralai/Mistral-7B-Instruct-v0.3" або будь-яка завантажена
  vllm.timeout           — 120.0 секунд (генерація може тривати довго)
  vllm.max_tokens        — 1200 за замовч.
  vllm.temperature       — 0.7
  vllm.api_key           — "EMPTY" (vLLM не вимагає, але поле обов'язкове)

Чому НЕ openai SDK:
  Зайва залежність для локального інференсу.
  httpx вже є в проекті (azure_translator.py).
  Повний контроль над retry / timeout / логами.

Сумісність:
  ILLMClient порт — той самий що AnthropicLLMClient.
  Взаємозамінні через DI в container.py.

Перевірка доступності:
  await client.health_check() → bool
  Перед генерацією корисно переконатись що vLLM server запущений.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from src.application.ports.rag_ports import ILLMClient, LLMResponse

logger = logging.getLogger(__name__)

_CHAT_ENDPOINT       = "/v1/chat/completions"
_COMPLETIONS_ENDPOINT = "/v1/completions"
_MODELS_ENDPOINT     = "/v1/models"
_DEFAULT_MODEL       = "mistralai/Mistral-7B-Instruct-v0.3"


class VLLMUnavailableError(Exception):
    """vLLM сервер недоступний. Перевір що vllm serve запущений."""


class VLLMCallError(Exception):
    """Помилка виклику vLLM API."""
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class VLLMClient(ILLMClient):
    """
    ILLMClient → vLLM OpenAI-compatible API (/v1/chat/completions).

    Підтримує будь-яку модель завантажену у vLLM:
      Mistral, LLaMA, Qwen, Gemma, DeepSeek тощо.

    Args:
        base_url:    URL vLLM сервера (без trailing slash)
                     Приклад: "http://localhost:8000"
        model:       назва моделі — має збігатись з --model при запуску vLLM
        api_key:     "EMPTY" для локального vLLM без автентифікації
        timeout:     таймаут HTTP запиту (генерація може бути повільною)
        temperature: температура семплінгу (0.0 = детермінований)
        top_p:       nucleus sampling (None = вимкнено)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        model: str = _DEFAULT_MODEL,
        api_key: str = "EMPTY",
        timeout: float = 120.0,
        temperature: float = 0.7,
        top_p: float | None = None,
    ) -> None:
        # Нормалізуємо URL — прибираємо trailing slash
        self._base_url    = base_url.rstrip("/")
        self._model       = model
        self._api_key     = api_key
        self._timeout     = timeout
        self._temperature = temperature
        self._top_p       = top_p
        self._client: httpx.AsyncClient | None = None

    # ── ILLMClient ────────────────────────────────────────────────────────────

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """
        Виклик vLLM /v1/chat/completions.

        Формат повідомлень (OpenAI Chat):
          system → {"role": "system", "content": system_prompt}
          user   → {"role": "user",   "content": user_prompt}

        Returns:
            LLMResponse з текстом і статистикою токенів.

        Raises:
            VLLMCallError     — HTTP помилка або невалідна відповідь
            VLLMUnavailableError — сервер не відповідає (Connection refused)
        """
        payload: dict[str, Any] = {
            "model":       self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            "max_tokens":  max_tokens,
            "temperature": self._temperature,
            "stream":      False,
        }
        if self._top_p is not None:
            payload["top_p"] = self._top_p

        url = self._base_url + _CHAT_ENDPOINT

        logger.info(
            "[vllm] Request: model=%s max_tokens=%d temp=%.2f "
            "system_len=%d user_len=%d",
            self._model, max_tokens, self._temperature,
            len(system_prompt), len(user_prompt),
        )

        client   = self._get_client()
        response = await self._post(client, url, payload)
        data     = response.json()

        # ── Парсинг відповіді (OpenAI Chat format) ────────────────────────────
        try:
            choice  = data["choices"][0]
            text    = choice["message"]["content"].strip()
            reason  = choice.get("finish_reason", "unknown")
        except (KeyError, IndexError) as exc:
            raise VLLMCallError(
                f"Unexpected vLLM response format: {data}"
            ) from exc

        usage         = data.get("usage", {})
        input_tokens  = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        logger.info(
            "[vllm] Response: model=%s finish=%s tokens_in=%d tokens_out=%d len=%d",
            self._model, reason, input_tokens, output_tokens, len(text),
        )

        if reason == "length":
            logger.warning(
                "[vllm] Response truncated by max_tokens=%d. "
                "Increase vllm.max_tokens in settings.",
                max_tokens,
            )

        return LLMResponse(
            text=text,
            model=self._model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    # ── Health check ──────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """
        Перевіряє доступність vLLM сервера через GET /v1/models.

        Returns:
            True  — сервер відповідає і вказана модель завантажена.
            False — сервер недоступний або модель не знайдена.
        """
        url    = self._base_url + _MODELS_ENDPOINT
        client = self._get_client()

        try:
            response = await client.get(
                url,
                headers=self._headers(),
                timeout=5.0,
            )
            response.raise_for_status()
            data   = response.json()
            models = [m["id"] for m in data.get("data", [])]

            if self._model not in models:
                logger.warning(
                    "[vllm] Health check: model %r not found. Available: %s",
                    self._model, models,
                )
                return False

            logger.info("[vllm] Health check OK: model=%s available", self._model)
            return True

        except (httpx.ConnectError, httpx.ConnectTimeout):
            logger.warning("[vllm] Health check failed: server unreachable at %s", self._base_url)
            return False
        except Exception as exc:
            logger.warning("[vllm] Health check error: %s", exc)
            return False

    async def list_models(self) -> list[str]:
        """Повертає список завантажених моделей (для діагностики)."""
        url    = self._base_url + _MODELS_ENDPOINT
        client = self._get_client()
        try:
            response = await client.get(url, headers=self._headers(), timeout=5.0)
            response.raise_for_status()
            return [m["id"] for m in response.json().get("data", [])]
        except Exception as exc:
            logger.warning("[vllm] list_models failed: %s", exc)
            return []

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def close(self) -> None:
        """Закриває HTTP з'єднання. Викликати при shutdown."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.debug("[vllm] HTTP client closed")

    # ── Private ───────────────────────────────────────────────────────────────

    def _get_client(self) -> httpx.AsyncClient:
        """Lazy singleton httpx клієнт (thread-safe в asyncio)."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type":  "application/json",
        }

    async def _post(
        self,
        client: httpx.AsyncClient,
        url: str,
        payload: dict,
    ) -> httpx.Response:
        """
        HTTP POST з обробкою помилок.

        Connection refused → VLLMUnavailableError (зрозуміліша помилка
        ніж голий httpx.ConnectError).
        """
        try:
            response = await client.post(
                url,
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            return response

        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise VLLMUnavailableError(
                f"vLLM server unreachable at {self._base_url}. "
                f"Make sure 'vllm serve {self._model}' is running."
            ) from exc

        except httpx.TimeoutException as exc:
            raise VLLMCallError(
                f"vLLM request timed out after {self._timeout}s. "
                f"Increase vllm.timeout in settings or reduce max_tokens."
            ) from exc

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            body   = exc.response.text[:400]

            if status == 400:
                raise VLLMCallError(
                    f"vLLM bad request (400) — can be wrong model name or "
                    f"context length exceeded. Body: {body}",
                    status_code=400,
                ) from exc
            if status == 404:
                raise VLLMCallError(
                    f"vLLM model not found (404). "
                    f"Check that model={self._model!r} is loaded.",
                    status_code=404,
                ) from exc

            raise VLLMCallError(
                f"vLLM API error: HTTP {status}. Body: {body}",
                status_code=status,
            ) from exc

        except Exception as exc:
            raise VLLMCallError(f"Unexpected vLLM error: {exc}") from exc