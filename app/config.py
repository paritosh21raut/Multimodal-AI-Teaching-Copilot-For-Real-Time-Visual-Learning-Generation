from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


# --------------------------------------------------------------
# LLM CONFIGURATION (Phase 1 — Groq only)
# --------------------------------------------------------------

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").strip().lower()

LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "openai/gpt-oss-120b",
).strip()

# Groq SDK already targets https://api.groq.com/openai/v1 by default.
# Only override LLM_BASE_URL if you need a non-default endpoint.
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").strip() or None

LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "30"))

LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))

LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2048"))

LLM_REASONING_EFFORT = (
    os.getenv("LLM_REASONING_EFFORT", "medium").strip() or None
)


# --------------------------------------------------------------
# GROQ
# --------------------------------------------------------------

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


# --------------------------------------------------------------
# IMAGES (unchanged, outside Phase 1 scope)
# --------------------------------------------------------------

PIXABAY_API_KEY = "57059568-74dfdc6ee55bf8f5dbfe36051"