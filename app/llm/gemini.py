"""Google Gemini provider (free tier) using the google-genai SDK.

Config from the environment: GEMINI_API_KEY, GEMINI_MODEL (a current Flash id),
GEMINI_FALLBACK_MODELS (comma-separated), ASK_MAX_TOKENS. Temperature is fixed at
0 for factual, low-variance answers.

Gemini 2.5 Flash is a "thinking" model whose internal reasoning counts against
max_output_tokens; we disable thinking so the whole budget goes to the answer
(and so a small budget doesn't yield an empty response).

Resilience (retry transient, fail-fast on quota, fall back across models, raise a
typed LLMError on exhaustion) lives in app.llm.base.run_with_resilience.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from app.llm.base import LLMProvider, run_with_resilience

load_dotenv()

DEFAULT_MODEL = "gemini-flash-latest"  # alias that tracks the current Flash
# A different model family so it has its own free-tier quota bucket and isn't
# subject to the same overload when the primary returns 503/429.
DEFAULT_FALLBACKS = "gemini-2.5-flash-lite"


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None,
                 max_tokens: int | None = None,
                 fallback_models: list[str] | str | None = None) -> None:
        from google import genai  # imported here so importing the module is cheap

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set (.env).")
        self.model = model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)

        fb = fallback_models if fallback_models is not None \
            else os.getenv("GEMINI_FALLBACK_MODELS", DEFAULT_FALLBACKS)
        if isinstance(fb, str):
            fb = [m.strip() for m in fb.split(",") if m.strip()]
        # Try the primary first, then each distinct fallback in order.
        self.models = [self.model] + [m for m in fb if m and m != self.model]

        self.max_tokens = int(max_tokens or os.getenv("ASK_MAX_TOKENS", "1024"))
        self._client = genai.Client(api_key=self.api_key)

    def _generate(self, model: str, system: str, user: str) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0,
            max_output_tokens=self.max_tokens,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
        response = self._client.models.generate_content(
            model=model, contents=user, config=config
        )
        return response.text or ""

    def complete(self, system: str, user: str) -> str:
        return run_with_resilience(
            lambda model: self._generate(model, system, user),
            self.models,
        )
