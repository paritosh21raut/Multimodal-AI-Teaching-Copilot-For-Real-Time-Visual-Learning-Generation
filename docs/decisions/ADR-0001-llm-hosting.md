# ADR-0001: LLM hosting — hybrid free tier
Status: accepted (2026-10-05)

**Context.** RTX 3050 Laptop with 4 GB VRAM. Whisper needs ~1 GB. A local LLM that is good enough for structured
lecture interpretation (≥ 7B) won't fit alongside it at usable speed. No paid APIs and no Gemini are allowed.
Internet is usually available.

**Decision.** `LLMRouter` with an ordered provider list: **Groq free tier** (primary; fast, OpenAI-compatible) →
**OpenRouter free models** (secondary) → **Ollama local small model** (e.g. qwen2.5:3b / llama3.2:3b, offline fallback).
All calls are schema-validated JSON, rate-limited, and budgeted. Model ids live in config, not code.

**Consequences.** + Good quality and latency at zero cost. − Depends on the network and free-tier limits →
the gate keeps calls ≤ 8/min; the fallback chain plus the deterministic fallback keeps the display alive offline.
The user must create a free Groq key; Ollama must be installed for offline use.
