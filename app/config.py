from dotenv import load_dotenv
import os

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "45"))
OLLAMA_ENABLED = os.getenv("OLLAMA_ENABLED", "true").lower() in {"1", "true", "yes", "on"}

LLM_PRIMARY = os.getenv("LLM_PRIMARY", "gemini").lower()
LLM_FALLBACK_ENABLED = os.getenv("LLM_FALLBACK_ENABLED", "true").lower() in {"1", "true", "yes", "on"}

GEMINI_TRANSIENT_COOLDOWN_SECONDS = float(os.getenv("GEMINI_TRANSIENT_COOLDOWN_SECONDS", "30"))
GEMINI_QUOTA_COOLDOWN_SECONDS = float(os.getenv("GEMINI_QUOTA_COOLDOWN_SECONDS", "900"))
GEMINI_MAX_OUTPUT_TOKENS = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "900"))

PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")