"""Google Gemini provider (free tier) using the google-genai SDK.

Config from the environment: GEMINI_API_KEY, GEMINI_MODEL (a current Flash id),
ASK_MAX_TOKENS. Temperature is fixed at 0 for factual, low-variance answers.

Gemini 2.5 Flash is a "thinking" model whose internal reasoning counts against
max_output_tokens; we disable thinking so the whole budget goes to the answer
(and so a small budget doesn't yield an empty response).
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from app.llm.base import LLMProvider

load_dotenv()

DEFAULT_MODEL = "gemini-flash-latest"  # alias that tracks the current Flash


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None,
                 max_tokens: int | None = None) -> None:
        from google import genai  # imported here so importing the module is cheap

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set (.env).")
        self.model = model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
        self.max_tokens = int(max_tokens or os.getenv("ASK_MAX_TOKENS", "1024"))
        self._client = genai.Client(api_key=self.api_key)

    def complete(self, system: str, user: str) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0,
            max_output_tokens=self.max_tokens,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
        response = self._client.models.generate_content(
            model=self.model, contents=user, config=config
        )
        return response.text or ""
