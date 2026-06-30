"""Critic agent — narrow, rank, and rerank.

Enforces the constraints we have data for (genre, year/decade, popularity, cast,
exclude-already-seen), pre-ranks by a normalized semantic+collaborative blend, then
asks the LLM to **rerank** the top candidates by true relevance to the request — so
the #1 pick reflects meaning, not superficial title-word overlap (e.g. a film merely
titled "Fun" isn't necessarily a fun movie). Constraints we can't enforce (runtime,
rating) are passed through to the trace as "noted, not enforced".
"""

from __future__ import annotations

import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.concierge.constraints import has_hard_constraint, year_bounds
from app.concierge.state import Candidate, ConciergeState
from app.db.models import Rating
from app.llm.base import LLMError, LLMProvider

NAME = "critic"

# The request is the primary intent, so semantic relevance leads; collaborative
# refines among relevant films. Both channels are min-max normalized over the
# candidate pool FIRST — they're on different scales (cosine ~0..1 vs the
# recommender's rating-scale ~0..5), so blending them raw lets generic popular
# movies dominate every query.
SEMANTIC_WEIGHT = 0.7
COLLAB_WEIGHT = 0.3
GENRE_MATCH_BOOST = 0.05      # per matched requested genre
RERANK_POOL = 12             # top-N (by blend) handed to the LLM reranker

RERANK_PROMPT = (
    "You rerank movie candidates by how well each matches the user's request. Judge by "
    "the request's actual MEANING — mood, theme, plot, tone — NOT superficial title-word "
    'overlap (a film merely titled "Fun" is not necessarily a fun movie; a film with '
    '"rain" in the title is not necessarily cozy). Drop poor fits. Respond with ONLY a '
    "JSON array of the candidate NUMBERS, best match first, at most {k} items. "
    "Example: [3, 1, 7]"
)


def _movie_genres(movie) -> set[str]:
    raw = movie.genres or ""
    if raw == "(no genres listed)":
        return set()
    return {g.strip().lower() for g in raw.split("|") if g.strip()}


def _movie_year(movie) -> int | None:
    rd = getattr(movie, "release_date", None)
    if rd and len(rd) >= 4 and rd[:4].isdigit():
        return int(rd[:4])
    return None


def _cast_names(movie) -> set[str]:
    return {c.get("name", "").lower() for c in (getattr(movie, "top_cast", None) or [])}


def _passes_filters(cand: Candidate, movie, intent, seen: set[int]) -> bool:
    if intent.exclude_seen and cand.movie_id in seen:
        return False
    if movie is None:
        return False

    if intent.genres:
        wanted = {g.lower() for g in intent.genres}
        if not (wanted & _movie_genres(movie)):
            return False

    year = _movie_year(movie)
    lo, hi = year_bounds(intent)
    if (lo or hi) and year is None:
        return False
    if lo and year is not None and year < lo:
        return False
    if hi and year is not None and year > hi:
        return False

    if intent.min_popularity is not None:
        pop = getattr(movie, "popularity", None) or 0.0
        if pop < intent.min_popularity:
            return False

    if intent.cast:
        wanted = {c.lower() for c in intent.cast}
        names = _cast_names(movie)
        if not any(any(w in n for n in names) for w in wanted):
            return False

    return True


def _minmax(value: float, lo: float, hi: float) -> float:
    """Scale value into [0, 1] given the pool's range; 0 when the range is empty."""
    return (value - lo) / (hi - lo) if hi > lo else 0.0


def _rank_pool(pool: list[Candidate], movies_by_id: dict, intent) -> None:
    """Set each candidate's blended .score in place. Normalizes the semantic and
    collaborative channels separately (different scales) before blending, so
    relevance — not raw popularity — drives the ranking."""
    if not pool:
        return
    sem = [c.semantic_score for c in pool]
    col = [c.collab_score for c in pool]
    s_lo, s_hi = min(sem), max(sem)
    c_lo, c_hi = min(col), max(col)
    wanted = {g.lower() for g in intent.genres}
    for c in pool:
        movie = movies_by_id.get(c.movie_id)
        boost = (
            GENRE_MATCH_BOOST * len(wanted & _movie_genres(movie))
            if wanted and movie is not None
            else 0.0
        )
        c.score = (
            SEMANTIC_WEIGHT * _minmax(c.semantic_score, s_lo, s_hi)
            + COLLAB_WEIGHT * _minmax(c.collab_score, c_lo, c_hi)
            + boost
        )


def _seen_movie_ids(db: Session, user_id: int) -> set[int]:
    rows = db.execute(select(Rating.movie_id).where(Rating.user_id == user_id)).scalars()
    return set(rows)


def _enforced(intent) -> dict:
    """The hard constraints actually applied — surfaced in the trace."""
    return {
        "genres": intent.genres,
        "year_range": [intent.year_min, intent.year_max]
        if (intent.year_min or intent.year_max) else intent.decade,
        "min_popularity": intent.min_popularity,
        "cast": intent.cast,
        "exclude_seen": intent.exclude_seen,
    }


def _parse_int_array(text: str) -> list[int]:
    """Pull a JSON array of ints from the model's text (tolerant of stray prose)."""
    m = re.search(r"\[[^\]]*\]", text, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except (json.JSONDecodeError, TypeError):
        return []
    out: list[int] = []
    for x in data if isinstance(data, list) else []:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return out


def _llm_rerank(
    state: ConciergeState, pool: list[Candidate], provider: LLMProvider
) -> tuple[list[Candidate], bool]:
    """Reorder `pool` by true relevance to the request via one LLM call and take the
    top `state.k`. Degrades to the existing (blended-score) order on any failure —
    a rerank hiccup never breaks the pipeline."""
    k = state.k
    if len(pool) <= 1:
        return pool[:k], False

    lines = []
    for i, c in enumerate(pool, start=1):
        movie = state.movies_by_id.get(c.movie_id)
        genres = (getattr(movie, "genres", "") or "").replace("|", ", ")
        overview = (getattr(movie, "overview", None) or "")[:160]
        lines.append(f"{i}. {c.title} — {genres} — {overview}")
    user_message = f"Request: {state.request}\n\nCandidates:\n" + "\n".join(lines)

    try:
        raw = provider.complete(RERANK_PROMPT.format(k=k), user_message)
    except LLMError:
        return pool[:k], False  # transient LLM issue -> keep blended order

    picked, used = [], set()
    for n in _parse_int_array(raw):
        idx = n - 1
        if 0 <= idx < len(pool) and idx not in used:
            used.add(idx)
            picked.append(pool[idx])
        if len(picked) >= k:
            break
    if not picked:
        return pool[:k], False  # unparseable -> blended order

    # Top up if the model returned fewer than k.
    for i, c in enumerate(pool):
        if len(picked) >= k:
            break
        if i not in used:
            picked.append(c)
    return picked, True


def run(state: ConciergeState, db: Session, provider: LLMProvider) -> dict:
    intent = state.intent
    seen = _seen_movie_ids(db, state.user_id) if intent.exclude_seen else set()

    kept = [
        c for c in state.candidates
        if _passes_filters(c, state.movies_by_id.get(c.movie_id), intent, seen)
    ]

    relaxed = False
    pool = kept
    if not pool:
        if has_hard_constraint(intent):
            # A hard constraint (year/genre/popularity) matched nothing in the catalog
            # (e.g. an out-of-range year). Be honest — don't relax into irrelevant films.
            state.shortlist = []
            return {
                "candidates_in": len(state.candidates),
                "after_filters": 0,
                "no_match": True,
                "reranked": False,
                "shortlist": [],
                "enforced": _enforced(intent),
                "noted_not_enforced": intent.unsupported,
            }
        # No hard constraint, but somehow empty (e.g. all already-seen) -> relax.
        relaxed = True
        pool = [c for c in state.candidates if c.movie_id not in seen]

    # Pre-rank by the normalized blend, take the top pool, then LLM-rerank by relevance.
    _rank_pool(pool, state.movies_by_id, intent)
    pre = sorted(pool, key=lambda c: c.score, reverse=True)[:RERANK_POOL]
    shortlist, reranked = _llm_rerank(state, pre, provider)

    state.shortlist = shortlist
    return {
        "candidates_in": len(state.candidates),
        "after_filters": len(kept),
        "relaxed": relaxed,
        "reranked": reranked,
        "shortlist": [c.title for c in shortlist],
        "enforced": _enforced(intent),
        "noted_not_enforced": intent.unsupported,
    }
