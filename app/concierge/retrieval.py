"""Retrieval agent — find candidates (no LLM).

Pulls candidates two ways and merges them: semantic (embedding ANN over the request)
and collaborative (the hybrid recommender for this user). Reuses the existing tools;
no new retrieval logic. Also records every candidate's Movie row in
state.movies_by_id so the Critic has metadata to filter on.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.concierge.state import Candidate, ConciergeState
from app.db.models import Movie
from app.llm.base import LLMProvider
from app.rag.ask import _retrieve

NAME = "retrieval"

SEMANTIC_K = 40
COLLAB_K = 20


def run(state: ConciergeState, db: Session, provider: LLMProvider) -> dict:
    intent = state.intent
    query = (intent.semantic_query if intent else None) or state.request

    by_id: dict[int, Candidate] = {}

    # --- semantic candidates (Movie objects + cosine score) ---
    for movie, score in _retrieve(db, query, SEMANTIC_K):
        state.movies_by_id[movie.id] = movie
        by_id[movie.id] = Candidate(
            movie_id=movie.id, title=movie.title,
            semantic_score=float(score), source="semantic",
        )

    # --- collaborative candidates (late import of MODELS avoids a circular import) ---
    n_collab = 0
    collab_source = "collaborative"
    try:
        from app.main import MODELS

        recs = MODELS["hybrid"].recommend_for_user(state.user_id, COLLAB_K)
    except KeyError:
        # Cold-start user the model doesn't know -> popularity as a stand-in.
        from app.recommenders.popularity import popular_movies

        recs = popular_movies(COLLAB_K)
        collab_source = "popularity"

    for rec in recs:
        n_collab += 1
        existing = by_id.get(rec.movie_id)
        if existing is not None:
            existing.collab_score = float(rec.score)
            existing.source = f"semantic+{collab_source}"
        else:
            by_id[rec.movie_id] = Candidate(
                movie_id=rec.movie_id, title=rec.title,
                collab_score=float(rec.score), source=collab_source,
            )

    # Fetch Movie rows for any collaborative-only ids (semantic ones are already cached).
    missing = [mid for mid in by_id if mid not in state.movies_by_id]
    if missing:
        for movie in db.execute(select(Movie).where(Movie.id.in_(missing))).scalars():
            state.movies_by_id[movie.id] = movie

    state.candidates = list(by_id.values())
    return {
        "candidates": len(state.candidates),
        "semantic": sum(1 for c in state.candidates if "semantic" in c.source),
        "collaborative": n_collab,
        "collab_source": collab_source,
    }
