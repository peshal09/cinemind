"""Retrieval agent — find candidates (no LLM).

Three sources, merged: semantic (embedding ANN over the request), collaborative (the
hybrid recommender), and — when the request carries a hard constraint (year/decade,
genre, popularity) — a **constrained DB query** that guarantees constraint-matching
films enter the pool. Without that last source, a year/genre constraint applied only
as a post-filter in the Critic can empty the pool (the right films were never
retrieved). Also records every candidate's Movie row in state.movies_by_id.
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.concierge.constraints import has_hard_constraint, year_bounds
from app.concierge.state import Candidate, ConciergeState
from app.db.models import Movie
from app.embeddings.model import embed_texts
from app.llm.base import LLMProvider

NAME = "retrieval"

SEMANTIC_K = 40
COLLAB_K = 20
CONSTRAINED_K = 30


def _constraint_conditions(intent) -> list:
    """SQLAlchemy WHERE conditions for the hard constraints (year/genre/popularity).
    release_date is an ISO string, so lexical comparison gives correct year bounds."""
    conds = []
    lo, hi = year_bounds(intent)
    if lo or hi:
        lo, hi = lo or 1900, hi or 2100
        conds.append(Movie.release_date.is_not(None))
        conds.append(Movie.release_date >= f"{lo:04d}-01-01")
        conds.append(Movie.release_date <= f"{hi:04d}-12-31")
    if intent.genres:
        conds.append(or_(*[Movie.genres.ilike(f"%{g}%") for g in intent.genres]))
    if intent.min_popularity is not None:
        conds.append(Movie.popularity >= intent.min_popularity)
    return conds


def run(state: ConciergeState, db: Session, provider: LLMProvider) -> dict:
    intent = state.intent
    query = (intent.semantic_query if intent else None) or state.request

    query_vec = embed_texts([query])[0].tolist()
    distance = Movie.embedding.cosine_distance(query_vec)
    by_id: dict[int, Candidate] = {}

    def add_semantic(movie: Movie, dist: float, source: str) -> None:
        state.movies_by_id[movie.id] = movie
        score = 1.0 - float(dist)
        existing = by_id.get(movie.id)
        if existing is not None:
            existing.semantic_score = max(existing.semantic_score, score)
            if source not in existing.source:
                existing.source = f"{existing.source}+{source}"
        else:
            by_id[movie.id] = Candidate(
                movie_id=movie.id, title=movie.title,
                semantic_score=score, source=source,
            )

    # --- semantic ANN over the whole catalog ---
    rows = db.execute(
        select(Movie, distance.label("dist"))
        .where(Movie.embedding.is_not(None))
        .order_by(distance)
        .limit(SEMANTIC_K)
    ).all()
    for movie, dist in rows:
        add_semantic(movie, dist, "semantic")

    # --- constrained retrieval: pull constraint-matching films INTO the pool,
    #     ranked by relevance within the constraint (so the Critic can keep them) ---
    n_constrained = 0
    if intent is not None and has_hard_constraint(intent):
        crows = db.execute(
            select(Movie, distance.label("dist"))
            .where(Movie.embedding.is_not(None), *_constraint_conditions(intent))
            .order_by(distance)
            .limit(CONSTRAINED_K)
        ).all()
        for movie, dist in crows:
            add_semantic(movie, dist, "constraint")
        n_constrained = len(crows)

    # --- collaborative (late import of MODELS avoids a circular import) ---
    n_collab = 0
    collab_source = "collaborative"
    try:
        from app.main import MODELS

        recs = MODELS["hybrid"].recommend_for_user(state.user_id, COLLAB_K)
    except KeyError:
        from app.recommenders.popularity import popular_movies

        recs = popular_movies(COLLAB_K)
        collab_source = "popularity"

    for rec in recs:
        n_collab += 1
        existing = by_id.get(rec.movie_id)
        if existing is not None:
            existing.collab_score = float(rec.score)
            if collab_source not in existing.source:
                existing.source = f"{existing.source}+{collab_source}"
        else:
            by_id[rec.movie_id] = Candidate(
                movie_id=rec.movie_id, title=rec.title,
                collab_score=float(rec.score), source=collab_source,
            )

    # Fetch Movie rows for any collaborative-only ids (others are already cached).
    missing = [mid for mid in by_id if mid not in state.movies_by_id]
    if missing:
        for movie in db.execute(select(Movie).where(Movie.id.in_(missing))).scalars():
            state.movies_by_id[movie.id] = movie

    state.candidates = list(by_id.values())
    return {
        "candidates": len(state.candidates),
        "semantic": sum(1 for c in state.candidates if "semantic" in c.source),
        "constrained": n_constrained,
        "collaborative": n_collab,
        "collab_source": collab_source,
    }
