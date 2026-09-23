from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").strip().lower()

LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "openai/gpt-oss-120b",
).strip()

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").strip() or None

LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "30"))

LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))

LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2048"))

LLM_REASONING_EFFORT = (
    os.getenv("LLM_REASONING_EFFORT", "medium").strip() or None
)


GROQ_API_KEY = os.getenv("GROQ_API_KEY")


LSI_REASONER_ENABLED = (
    os.getenv("LSI_REASONER_ENABLED", "true").strip().lower()
    in ("1", "true", "yes", "on")
)

LSI_REASONER_REASONING_EFFORT = (
    os.getenv("LSI_REASONER_REASONING_EFFORT", "low").strip() or None
)

LSI_REASONER_MAX_TOKENS = int(
    os.getenv("LSI_REASONER_MAX_TOKENS", "320")
)

LSI_CONTINUE_THRESHOLD = float(
    os.getenv("LSI_CONTINUE_THRESHOLD", "0.45")
)

LSI_RELATED_FLOOR = float(
    os.getenv("LSI_RELATED_FLOOR", "0.30")
)

LSI_RETURN_FLOOR = float(
    os.getenv("LSI_RETURN_FLOOR", "0.55")
)

LSI_TOP_K_CANDIDATES = int(
    os.getenv("LSI_TOP_K_CANDIDATES", "5")
)

LSI_MAX_NODES = int(
    os.getenv("LSI_MAX_NODES", "200")
)


SEMANTIC_ENABLED = (
    os.getenv("SEMANTIC_ENABLED", "true").strip().lower()
    in ("1", "true", "yes", "on")
)

SEMANTIC_REASONER_MODEL = os.getenv(
    "SEMANTIC_REASONER_MODEL",
    "openai/gpt-oss-120b",
).strip()

SEMANTIC_FALLBACK_MODEL = os.getenv(
    "SEMANTIC_FALLBACK_MODEL",
    "openai/gpt-oss-20b",
).strip()

SEMANTIC_REASONER_REASONING_EFFORT = (
    os.getenv("SEMANTIC_REASONER_REASONING_EFFORT", "low").strip() or None
)

SEMANTIC_REASONER_MAX_TOKENS = int(
    os.getenv("SEMANTIC_REASONER_MAX_TOKENS", "1600")
)

SEMANTIC_QUEUE_MAX_SIZE = int(
    os.getenv("SEMANTIC_QUEUE_MAX_SIZE", "64")
)

SEMANTIC_BATCH_SIZE = int(
    os.getenv("SEMANTIC_BATCH_SIZE", "2")
)

SEMANTIC_BATCH_TIMEOUT = float(
    os.getenv("SEMANTIC_BATCH_TIMEOUT", "6.0")
)

SEMANTIC_MAX_CALLS_PER_MINUTE = int(
    os.getenv("SEMANTIC_MAX_CALLS_PER_MINUTE", "2")
)

SEMANTIC_MIN_INTERVAL_SECONDS = float(
    os.getenv("SEMANTIC_MIN_INTERVAL_SECONDS", "20.0")
)


PIXABAY_API_KEY = "57059568-74dfdc6ee55bf8f5dbfe36051"