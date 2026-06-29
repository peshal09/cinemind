"""Preference agent — understand the ask.

Reads the user's taste (their liked movies) and parses the natural-language request
into a structured Intent via one LLM call. Constraints we have no data for (runtime,
rating) are routed into `unsupported` so the Critic can be honest about them.
"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.concierge.state import ConciergeState, Intent
from app.llm.base import LLMProvider
from app.rag.explain import _liked_movies

NAME = "preference"

SYSTEM_PROMPT = (
    "You convert a movie-discovery request into a JSON object describing the user's "
    "intent. Output ONLY the JSON object, no markdown or code fences.\n"
    "Schema (omit a field or use null/[] when not implied):\n"
    '{\n'
    '  "semantic_query": "a concise description of the vibe/theme/plot to search for, '
    'EXCLUDING hard filters like year or genre",\n'
    '  "genres": ["Comedy", ...],            // canonical genre words\n'
    '  "moods": ["dark", "feel-good", ...],\n'
    '  "decade": "1990s" | null,\n'
    '  "year_min": 1990 | null, "year_max": 1999 | null,\n'
    '  "cast": ["Tom Hanks", ...],\n'
    '  "similar_to": ["Inception", ...],     // movies the user references\n'
    '  "min_popularity": null,               // only if they ask for "popular"\n'
    '  "unsupported": ["max_runtime: 120", "min_rating: 7"]  // constraints about '
    'runtime, IMDb/TMDB rating, or streaming availability — we cannot filter these\n'
    "}\n"
    "Always include semantic_query (fall back to the raw request if unsure)."
)


def _parse_json_object(text: str) -> dict:
    """Tolerantly extract a JSON object from the model's text (same approach as the
    /ask parser): strip code fences, else grab the outermost { ... }."""
    candidate = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", candidate, re.DOTALL)
    if fence:
        candidate = fence.group(1).strip()
    if not candidate.startswith("{"):
        brace = re.search(r"\{.*\}", candidate, re.DOTALL)
        if brace:
            candidate = brace.group(0)
    try:
        data = json.loads(candidate)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()]


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_intent(raw_request: str, data: dict) -> Intent:
    return Intent(
        semantic_query=str(data.get("semantic_query") or raw_request).strip() or raw_request,
        raw_request=raw_request,
        genres=_as_str_list(data.get("genres")),
        moods=_as_str_list(data.get("moods")),
        decade=(str(data["decade"]).strip() if data.get("decade") else None),
        year_min=_as_int(data.get("year_min")),
        year_max=_as_int(data.get("year_max")),
        min_popularity=_as_float(data.get("min_popularity")),
        cast=_as_str_list(data.get("cast")),
        similar_to=_as_str_list(data.get("similar_to")),
        unsupported=_as_str_list(data.get("unsupported")),
    )


def run(state: ConciergeState, db: Session, provider: LLMProvider) -> dict:
    state.taste = _liked_movies(db, state.user_id)

    # An LLMError here propagates -> the orchestrator falls back. A merely
    # unparseable response degrades softly to a plain semantic search.
    raw = provider.complete(SYSTEM_PROMPT, state.request)
    data = _parse_json_object(raw)
    state.intent = _build_intent(state.request, data)

    return {
        "liked_movies": len(state.taste),
        "parsed_ok": bool(data),
        "intent": state.intent.to_summary(),
    }
