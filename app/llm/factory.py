"""Resolve the configured LLM provider (the only seam /ask imports)."""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

from app.llm.base import LLMProvider

load_dotenv()


@lru_cache(maxsize=1)
def get_provider() -> LLMProvider:
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider == "gemini":
        from app.llm.gemini import GeminiProvider

        return GeminiProvider()
    raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}")
