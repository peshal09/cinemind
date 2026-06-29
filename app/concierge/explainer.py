"""Explainer agent — justify the picks.

One LLM call explains the whole shortlist at once (cheaper than one call per pick),
grounded in the user's liked movies plus each pick's attributes. Results are mapped
back onto picks with the tolerant title matching from /ask, so loose title formats
still line up.
"""

from __future__ import annotations

import json
import re

from sqlalchemy.orm import Session

from app.concierge.state import ConciergeState, Pick
from app.llm.base import LLMProvider
from app.rag.ask import _canonical_title

NAME = "explainer"

SYSTEM_PROMPT = (
    "You explain, in 1-2 warm sentences each, why a user would enjoy specific movies. "
    "Use ONLY the provided data — the user's liked movies and each candidate's "
    "attributes. Reference the user's liked films by name when you can; never invent "
    "facts. Respond with ONLY a JSON array, no markdown:\n"
    '[{"title": "<exact candidate title>", "why": "<1-2 sentences>", '
    '"based_on": ["<liked title>", ...]}]'
)


def _parse_json_array(text: str) -> list:
    candidate = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", candidate, re.DOTALL)
    if fence:
        candidate = fence.group(1).strip()
    if not candidate.startswith("["):
        bracket = re.search(r"\[.*\]", candidate, re.DOTALL)
        if bracket:
            candidate = bracket.group(0)
    try:
        data = json.loads(candidate)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _movie_block(movie) -> str:
    genres = (movie.genres or "").replace("|", ", ")
    keywords = ", ".join(getattr(movie, "keywords", None) or [])
    cast = ", ".join(c.get("name", "") for c in (getattr(movie, "top_cast", None) or []))
    return (
        f"Title: {movie.title}\n"
        f"Genres: {genres}\n"
        f"Overview: {getattr(movie, 'overview', None) or 'N/A'}\n"
        f"Keywords: {keywords or 'N/A'}\n"
        f"Cast: {cast or 'N/A'}"
    )


def _build_user_message(state: ConciergeState) -> str:
    if state.taste:
        liked = "\n".join(
            f"- {m.title} ({(m.genres or '').replace('|', ', ')})" for m in state.taste
        )
    else:
        liked = "(no rating history yet — explain the fit to the request instead)"

    blocks = []
    for i, cand in enumerate(state.shortlist, start=1):
        movie = state.movies_by_id.get(cand.movie_id)
        if movie is not None:
            blocks.append(f"<candidate {i}>\n{_movie_block(movie)}\n</candidate>")

    return (
        f"User's request: {state.request}\n\n"
        f"User's liked movies:\n{liked}\n\n"
        f"Candidates to explain:\n" + "\n".join(blocks)
    )


def _pick_score(cand) -> float:
    """The blended [0,1] rank score from the critic; fall back to the raw channels
    if the critic didn't run (e.g. in isolated unit tests)."""
    return cand.score or max(cand.semantic_score, cand.collab_score)


def run(state: ConciergeState, db: Session, provider: LLMProvider) -> dict:
    if not state.shortlist:
        state.results = []
        return {"explained": 0}

    # An LLMError here propagates -> the orchestrator falls back.
    raw = provider.complete(SYSTEM_PROMPT, _build_user_message(state))
    parsed = _parse_json_array(raw)

    # Map explanations onto shortlist picks by tolerant title match.
    by_canon: dict[str, dict] = {}
    for item in parsed:
        if isinstance(item, dict) and item.get("title"):
            by_canon.setdefault(_canonical_title(str(item["title"])), item)

    results: list[Pick] = []
    explained = 0
    for cand in state.shortlist:
        movie = state.movies_by_id.get(cand.movie_id)
        item = by_canon.get(_canonical_title(cand.title))
        why = str(item.get("why", "")).strip() if item else ""
        based_on = [str(b) for b in item.get("based_on", [])] if item else []
        if why:
            explained += 1
        results.append(Pick(
            movie_id=cand.movie_id,
            title=cand.title,
            score=_pick_score(cand),
            why=why,
            based_on=based_on,
        ))

    state.results = results
    return {"picks": len(results), "explained": explained}
