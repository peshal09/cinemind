"""Critic agent — narrow and order (no LLM).

Enforces the constraints we have data for (genre, year/decade, popularity, cast,
exclude-already-seen), applies light genre diversity, and re-ranks to the final
top-k. Constraints we can't enforce (runtime, rating) are passed through to the
trace as "noted, not enforced" rather than silently ignored.
"""

from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.concierge.state import Candidate, ConciergeState
from app.db.models import Rating
from app.llm.base import LLMProvider

NAME = "critic"

# The request is the primary intent, so semantic relevance leads; collaborative
# refines among relevant films. Both channels are min-max normalized over the
# candidate pool FIRST — they're on different scales (cosine ~0..1 vs the
# recommender's rating-scale ~0..5), so blending them raw lets generic popular
# movies dominate every query.
SEMANTIC_WEIGHT = 0.7
COLLAB_WEIGHT = 0.3
GENRE_MATCH_BOOST = 0.05      # per matched requested genre


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
    lo, hi = intent.year_min, intent.year_max
    if intent.decade and not (lo or hi):
        d = intent.decade.strip().rstrip("s")
        if d[:4].isdigit():
            lo, hi = int(d[:4]), int(d[:4]) + 9
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


def run(state: ConciergeState, db: Session, provider: LLMProvider) -> dict:
    intent = state.intent
    seen = _seen_movie_ids(db, state.user_id) if intent.exclude_seen else set()

    kept = [
        c for c in state.candidates
        if _passes_filters(c, state.movies_by_id.get(c.movie_id), intent, seen)
    ]

    # Don't return nothing: if hard filters eliminated everyone, relax them and just
    # drop already-seen, so the user still gets a sensible (if looser) shortlist.
    relaxed = False
    pool = kept
    if not pool:
        relaxed = True
        pool = [c for c in state.candidates if c.movie_id not in seen]

    _rank_pool(pool, state.movies_by_id, intent)
    ranked = sorted(pool, key=lambda c: c.score, reverse=True)

    # Light diversity: avoid a shortlist dominated by one genre.
    cap = max(2, math.ceil(state.k / 2))
    genre_counts: dict[str, int] = {}
    shortlist: list[Candidate] = []
    for cand in ranked:
        movie = state.movies_by_id.get(cand.movie_id)
        primary = next(iter(_movie_genres(movie)), None) if movie else None
        if primary and genre_counts.get(primary, 0) >= cap:
            continue
        shortlist.append(cand)
        if primary:
            genre_counts[primary] = genre_counts.get(primary, 0) + 1
        if len(shortlist) >= state.k:
            break

    # If diversity capping under-filled, top up from the ranked remainder.
    if len(shortlist) < state.k:
        for cand in ranked:
            if cand not in shortlist:
                shortlist.append(cand)
            if len(shortlist) >= state.k:
                break

    state.shortlist = shortlist
    return {
        "candidates_in": len(state.candidates),
        "after_filters": len(kept),
        "relaxed": relaxed,
        "shortlist": [c.title for c in shortlist],
        "enforced": {
            "genres": intent.genres,
            "year_range": [intent.year_min, intent.year_max] if (intent.year_min or intent.year_max) else intent.decade,
            "min_popularity": intent.min_popularity,
            "cast": intent.cast,
            "exclude_seen": intent.exclude_seen,
        },
        "noted_not_enforced": intent.unsupported,
    }
