from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from groq import (
    APIError,
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    Groq,
    RateLimitError,
)

from app.ai.llm_client import (
    LLMClient,
    LLMConfigurationError,
    LLMRequestError,
    LLMResponseError,
)
from app.utils.logger import app_logger


class GroqClient(LLMClient):
    """
    Groq client using Strict JSON Schema structured outputs.

    Does NOT raise on construction if the API key is missing.
    Configuration errors are raised on first request.
    """

    def __init__(
        self,
        api_key: Optional[str],
        base_url: Optional[str],
        model: Optional[str],
        *,
        timeout: float = 30.0,
        max_retries: int = 2,
        backoff_base: float = 0.8,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        reasoning_effort: Optional[str] = "medium",
    ):

        self._api_key = (api_key or "").strip()
        self._base_url = (base_url or "").strip() or None
        self._model = (model or "").strip()
        self._timeout = float(timeout)
        self._max_retries = int(max_retries)
        self._backoff_base = float(backoff_base)
        self._temperature = float(temperature)
        self._max_tokens = int(max_tokens)
        self._reasoning_effort = reasoning_effort

        self._client: Optional[Groq] = None

    # ----------------------------------------------------------
    # PROPERTIES
    # ----------------------------------------------------------

    @property
    def provider(self) -> str:
        return "groq"

    @property
    def model(self) -> str:
        return self._model

    # ----------------------------------------------------------
    # CONFIG / CLIENT LAZY INIT
    # ----------------------------------------------------------

    def _ensure_configured(self) -> None:

        missing = []

        if not self._api_key:
            missing.append("GROQ_API_KEY")

        if not self._model:
            missing.append("LLM_MODEL")

        if missing:
            raise LLMConfigurationError(
                "GroqClient missing configuration: "
                + ", ".join(missing)
            )

    def _get_client(self) -> Groq:

        if self._client is not None:
            return self._client

        kwargs: Dict[str, Any] = {
            "api_key": self._api_key,
            "timeout": self._timeout,
            "max_retries": 0,
        }

        if self._base_url:
            kwargs["base_url"] = self._base_url

        self._client = Groq(**kwargs)

        return self._client

    # ----------------------------------------------------------
    # PUBLIC
    # ----------------------------------------------------------

    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> str:

        messages = self._build_messages(prompt, system)

        response = self._call(
            messages=messages,
            response_format=None,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

        return self._extract_text(response)

    def generate_structured(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        schema_name: str = "response",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:

        if not isinstance(schema, dict) or not schema:
            raise LLMConfigurationError(
                "generate_structured requires a JSON schema"
            )

        messages = self._build_messages(prompt, system)

        response_format: Dict[str, Any] = {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": schema,
            },
        }

        response = self._call(
            messages=messages,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

        text = self._extract_text(response)

        return self._parse_json_object(text)

    def health_check(self) -> bool:

        try:

            self._ensure_configured()

            # Reasoning models may return empty content with a tiny
            # max_tokens budget. Use a larger budget and accept either
            # the content or reasoning field.
            text = self.generate(
                "Reply with the single word: ok",
                max_tokens=64,
                timeout=min(self._timeout, 15.0),
            )

            return bool(text and text.strip())

        except Exception as error:

            app_logger.warning(
                f"[GroqClient] health_check failed: {error}"
            )

            return False

    # ----------------------------------------------------------
    # MESSAGES
    # ----------------------------------------------------------

    @staticmethod
    def _build_messages(
        prompt: str,
        system: Optional[str],
    ):

        messages = []

        if system:
            messages.append(
                {"role": "system", "content": system}
            )

        messages.append(
            {"role": "user", "content": prompt}
        )

        return messages

    # ----------------------------------------------------------
    # CALL + RETRY
    # ----------------------------------------------------------

    def _call(
        self,
        *,
        messages,
        response_format: Optional[Dict[str, Any]],
        temperature: Optional[float],
        max_tokens: Optional[int],
        timeout: Optional[float],
    ):

        self._ensure_configured()

        client = self._get_client()

        effective_timeout = (
            self._timeout
            if timeout is None
            else float(timeout)
        )

        kwargs: Dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": (
                self._temperature
                if temperature is None
                else float(temperature)
            ),
            "max_tokens": (
                self._max_tokens
                if max_tokens is None
                else int(max_tokens)
            ),
        }

        if response_format is not None:
            kwargs["response_format"] = response_format

        if self._reasoning_effort:
            kwargs["reasoning_effort"] = self._reasoning_effort

        last_error: Optional[Exception] = None

        for attempt in range(self._max_retries + 1):

            started = time.perf_counter()

            try:

                response = client.chat.completions.create(
                    **kwargs,
                    timeout=effective_timeout,
                )

                latency = time.perf_counter() - started

                app_logger.info(
                    "[GroqClient] "
                    f"provider=groq "
                    f"model={self._model} "
                    f"latency={latency:.2f}s "
                    f"attempt={attempt + 1}"
                )

                return response

            except RateLimitError as error:

                last_error = error

                retry_after = self._parse_retry_after(error)

                if attempt < self._max_retries:

                    delay = (
                        retry_after
                        if retry_after is not None
                        else self._backoff_base * (2 ** attempt)
                    )

                    app_logger.warning(
                        "[GroqClient] rate limited "
                        f"attempt={attempt + 1}/"
                        f"{self._max_retries + 1} "
                        f"retry_after={delay:.2f}s"
                    )

                    time.sleep(delay)
                    continue

                break

            except (
                APIConnectionError,
                APITimeoutError,
            ) as error:

                last_error = error

                if attempt < self._max_retries:

                    delay = self._backoff_base * (2 ** attempt)

                    app_logger.warning(
                        "[GroqClient] network error "
                        f"attempt={attempt + 1}/"
                        f"{self._max_retries + 1} "
                        f"delay={delay:.2f}s "
                        f"error={type(error).__name__}"
                    )

                    time.sleep(delay)
                    continue

                break

            except APIStatusError as error:

                last_error = error

                status = getattr(error, "status_code", None)

                if (
                    status in (500, 502, 503, 504)
                    and attempt < self._max_retries
                ):

                    delay = self._backoff_base * (2 ** attempt)

                    app_logger.warning(
                        "[GroqClient] server error "
                        f"status={status} "
                        f"attempt={attempt + 1}/"
                        f"{self._max_retries + 1} "
                        f"delay={delay:.2f}s"
                    )

                    time.sleep(delay)
                    continue

                break

            except APIError as error:

                last_error = error
                break

        raise LLMRequestError(
            "Groq request failed: "
            f"{type(last_error).__name__}: {last_error}"
        )

    @staticmethod
    def _parse_retry_after(error: Exception) -> Optional[float]:

        response = getattr(error, "response", None)

        if response is None:
            return None

        headers = getattr(response, "headers", None)

        if not headers:
            return None

        value = headers.get("retry-after")

        if value is None:
            return None

        try:
            return max(0.5, float(value))

        except (TypeError, ValueError):
            return None

    # ----------------------------------------------------------
    # EXTRACTION
    # ----------------------------------------------------------

    @staticmethod
    def _extract_text(response) -> str:

        try:
            choices = response.choices

        except AttributeError as error:
            raise LLMResponseError(
                f"Groq response missing choices: {error}"
            )

        if not choices:
            raise LLMResponseError(
                "Groq returned no choices"
            )

        message = choices[0].message

        content = getattr(message, "content", None)

        if isinstance(content, str) and content.strip():
            return content

        # Some reasoning models on Groq place output in `reasoning`
        # when content is empty.
        reasoning = getattr(message, "reasoning", None)

        if isinstance(reasoning, str) and reasoning.strip():
            return reasoning

        raise LLMResponseError(
            "Groq returned empty content and empty reasoning"
        )

    @staticmethod
    def _parse_json_object(text: str) -> Dict[str, Any]:

        candidate = text.strip()

        if candidate.startswith("```"):

            candidate = candidate.strip("`")

            if candidate.lower().startswith("json"):
                candidate = candidate[4:]

            candidate = candidate.strip()

        try:
            parsed = json.loads(candidate)

        except json.JSONDecodeError as error:

            raise LLMResponseError(
                f"Groq response was not valid JSON: {error}"
            )

        if not isinstance(parsed, dict):
            raise LLMResponseError(
                "Groq response JSON was not an object"
            )

        return parsed