from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional

from app.ai.gemini_client import (
    GeminiClient,
    GeminiPermanentError,
    GeminiQuotaError,
    GeminiTransientError,
)

from app.config import (
    GEMINI_QUOTA_COOLDOWN_SECONDS,
    GEMINI_TRANSIENT_COOLDOWN_SECONDS,
    LLM_FALLBACK_ENABLED,
    LLM_PRIMARY,
    OLLAMA_ENABLED,
)

from app.llm.ollama_client import (
    OllamaClient,
    OllamaUnavailableError,
)


class LLMOrchestrator:
    """
    Quality-first Gemini + local Ollama fallback.

    Gemini is used normally.
    Ollama takes over when Gemini is unavailable,
    rate-limited, quota-exhausted, or otherwise fails.
    """

    def __init__(
        self,
        gemini: Optional[
            GeminiClient
        ] = None,
        ollama: Optional[
            OllamaClient
        ] = None,
    ) -> None:

        self.gemini = (
            gemini
            or GeminiClient()
        )

        self.ollama = (
            ollama
            or OllamaClient()
        )

        self.lock = (
            threading.RLock()
        )

        self.primary = LLM_PRIMARY

        self.fallback_enabled = (
            LLM_FALLBACK_ENABLED
        )

        self.ollama_enabled = (
            OLLAMA_ENABLED
        )

        self.gemini_cooldown_until = 0.0

        self.gemini_cooldown_reason = ""

        self.ollama_available_cache = False

        self.ollama_check_time = 0.0

        self.total_requests = 0

        self.gemini_requests = 0

        self.ollama_requests = 0

        self.fallbacks = 0

        self.last_provider = "NONE"

        self.last_status = "READY"

        self.last_error = ""

    # ==========================================================
    # OLLAMA AVAILABILITY
    # ==========================================================

    def _ollama_available(self) -> bool:

        now = time.time()

        if (
            now
            - self.ollama_check_time
            < 10
        ):

            return (
                self.ollama_available_cache
            )

        with self.lock:

            self.ollama_check_time = now

            if not self.ollama_enabled:

                self.ollama_available_cache = (
                    False
                )

                return False

            self.ollama_available_cache = (
                self.ollama.is_available()
            )

            return (
                self.ollama_available_cache
            )

    # ==========================================================
    # GEMINI AVAILABILITY
    # ==========================================================

    def _gemini_available(self) -> bool:

        return (
            time.time()
            >= self.gemini_cooldown_until
        )

    # ==========================================================
    # GEMINI COOLDOWN
    # ==========================================================

    def _set_gemini_cooldown(
        self,
        seconds: float,
        reason: str,
    ) -> None:

        with self.lock:

            self.gemini_cooldown_until = (
                time.time()
                + seconds
            )

            self.gemini_cooldown_reason = (
                reason
            )

    # ==========================================================
    # OLLAMA GENERATION
    # ==========================================================

    def _generate_with_ollama(
        self,
        topic: str,
        context: str,
    ) -> Dict[str, Any]:

        self.ollama_requests += 1

        result = (
            self.ollama.generate_slide(
                prompt="",
                topic=topic,
                context=context,
            )
        )

        self.last_provider = "OLLAMA"

        self.last_status = "OLLAMA_SUCCESS"

        self.last_error = ""

        return result

    # ==========================================================
    # MAIN GENERATION
    # ==========================================================

    def generate_slide(
        self,
        topic: str,
        context: str,
    ) -> Dict[str, Any]:

        self.total_requests += 1

        # ------------------------------------------------------
        # Explicit Ollama-primary mode.
        # ------------------------------------------------------

        if self.primary == "ollama":

            if (
                self.ollama_enabled
                and self._ollama_available()
            ):

                try:

                    return (
                        self._generate_with_ollama(
                            topic,
                            context,
                        )
                    )

                except OllamaUnavailableError as error:

                    self.last_status = (
                        "OLLAMA_FAILED"
                    )

                    self.last_error = str(
                        error
                    )

            # If primary Ollama fails, allow
            # Gemini as recovery path.
            if not self.fallback_enabled:

                raise RuntimeError(
                    "Ollama is unavailable."
                )

        # ------------------------------------------------------
        # GEMINI PRIMARY PATH
        # ------------------------------------------------------

        if self._gemini_available():

            try:

                self.gemini_requests += 1

                result = (
                    self.gemini.generate_slide(
                        topic=topic,
                        context=context,
                    )
                )

                self.last_provider = (
                    "GEMINI"
                )

                self.last_status = (
                    "GEMINI_SUCCESS"
                )

                self.last_error = ""

                return result

            except GeminiQuotaError as error:

                self._set_gemini_cooldown(
                    GEMINI_QUOTA_COOLDOWN_SECONDS,
                    "quota_or_daily_limit",
                )

                self.last_status = (
                    "GEMINI_QUOTA"
                )

                self.last_error = str(
                    error
                )

            except GeminiTransientError as error:

                self._set_gemini_cooldown(
                    GEMINI_TRANSIENT_COOLDOWN_SECONDS,
                    "temporary_failure_or_rate_limit",
                )

                self.last_status = (
                    "GEMINI_TEMPORARY_FAILURE"
                )

                self.last_error = str(
                    error
                )

            except GeminiPermanentError as error:

                self.last_status = (
                    "GEMINI_ERROR"
                )

                self.last_error = str(
                    error
                )

        else:

            self.last_status = (
                "GEMINI_COOLDOWN"
            )

        # ------------------------------------------------------
        # OLLAMA FALLBACK
        # ------------------------------------------------------

        if (
            self.fallback_enabled
            and self.ollama_enabled
            and self._ollama_available()
        ):

            try:

                self.fallbacks += 1

                print(
                    "[LLM] Gemini unavailable "
                    "-> using local Ollama"
                )

                return (
                    self._generate_with_ollama(
                        topic,
                        context,
                    )
                )

            except OllamaUnavailableError as error:

                self.last_provider = (
                    "NONE"
                )

                self.last_status = (
                    "ALL_PROVIDERS_FAILED"
                )

                self.last_error = str(
                    error
                )

        raise RuntimeError(
            "No LLM provider is currently available. "
            f"Last error: {self.last_error}"
        )

    # ==========================================================
    # STATUS
    # ==========================================================

    def status(
        self,
    ) -> Dict[str, Any]:

        gemini_status = (
            self.gemini.status()
        )

        cooldown_remaining = max(
            0.0,
            (
                self.gemini_cooldown_until
                - time.time()
            ),
        )

        return {

            "primary": self.primary,

            "last_provider":
                self.last_provider,

            "last_status":
                self.last_status,

            "total_requests":
                self.total_requests,

            "gemini_requests":
                self.gemini_requests,

            "ollama_requests":
                self.ollama_requests,

            "fallbacks":
                self.fallbacks,

            "gemini":
                gemini_status,

            "gemini_cooldown_seconds":
                round(
                    cooldown_remaining,
                    1,
                ),

            "gemini_cooldown_reason":
                self.gemini_cooldown_reason,

            "ollama_enabled":
                self.ollama_enabled,

            "ollama_available":
                self._ollama_available(),
        }

    # ==========================================================
    # PRINT STATUS
    # ==========================================================

    def print_status(self) -> None:

        status = self.status()

        print(
            "=" * 60
        )

        print(
            "LLM STATUS"
        )

        print(
            "=" * 60
        )

        print(
            "Provider          :",
            status[
                "last_provider"
            ],
        )

        print(
            "Status            :",
            status[
                "last_status"
            ],
        )

        print(
            "Gemini calls      :",
            status[
                "gemini"
            ][
                "calls"
            ],
        )

        print(
            "Gemini successes  :",
            status[
                "gemini"
            ][
                "successes"
            ],
        )

        print(
            "Gemini failures   :",
            status[
                "gemini"
            ][
                "failures"
            ],
        )

        print(
            "Input tokens      :",
            status[
                "gemini"
            ][
                "input_tokens"
            ],
        )

        print(
            "Output tokens     :",
            status[
                "gemini"
            ][
                "output_tokens"
            ],
        )

        print(
            "Total tokens      :",
            status[
                "gemini"
            ][
                "total_tokens"
            ],
        )

        print(
            "Ollama requests   :",
            status[
                "ollama_requests"
            ],
        )

        print(
            "Fallbacks         :",
            status[
                "fallbacks"
            ],
        )

        print(
            "Ollama available  :",
            status[
                "ollama_available"
            ],
        )

        if (
            status[
                "gemini_cooldown_seconds"
            ]
            > 0
        ):

            print(
                "Gemini cooldown   :",
                f"{status['gemini_cooldown_seconds']}s",
            )

        print(
            "=" * 60
        )