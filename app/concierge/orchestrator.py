"""Concierge orchestrator.

Runs the four agents in sequence over one explicit ConciergeState, timing each and
recording a trace step. If any agent raises, it records the failure and degrades to
the Phase-3 recommender so the user always gets something.
"""

from __future__ import annotations

import logging
from time import perf_counter

from sqlalchemy.orm import Session

from app.concierge import critic, explainer, preference, retrieval
from app.concierge.state import AgentStep, ConciergeState
from app.llm.factory import get_provider

logger = logging.getLogger("cinemind.concierge")

# The fixed pipeline, in order. Each module exposes NAME and run(state, db, provider).
AGENTS = [preference, retrieval, critic, explainer]


def _fallback(state: ConciergeState, db: Session, exc: Exception) -> dict:
    """Phase-3 recommender fallback (mirrors app.main.recommend): hybrid for known
    users, popularity for cold-start. Always returns non-empty picks if possible."""
    from app.recommenders.popularity import popular_movies

    try:
        from app.main import MODELS

        recs = MODELS["hybrid"].recommend_for_user(state.user_id, state.k)
        model = "hybrid"
    except KeyError:
        recs = popular_movies(state.k)
        model = "popularity"
    except Exception:  # noqa: BLE001 — last-resort safety net
        recs = popular_movies(state.k)
        model = "popularity"

    # Fetch poster paths for the fallback picks in one query.
    from sqlalchemy import select

    from app.db.models import Movie

    posters = dict(
        db.execute(
            select(Movie.id, Movie.poster_path).where(
                Movie.id.in_([r.movie_id for r in recs])
            )
        ).all()
    )
    picks = [
        {"movie_id": r.movie_id, "title": r.title, "score": round(r.score, 4),
         "why": "", "based_on": [], "poster_path": posters.get(r.movie_id)}
        for r in recs
    ]
    logger.warning("concierge fallback (%s) after %s: %s", model, type(exc).__name__, exc)
    return {
        "request": state.request,
        "intent": state.intent.to_summary() if state.intent else None,
        "picks": picks,
        "trace": [s.to_dict() for s in state.trace],
        "fallback": True,
        "fallback_reason": f"{type(exc).__name__}: {exc}",
        "fallback_model": model,
    }


def run_concierge(request: str, user_id: int, db: Session, k: int = 5) -> dict:
    state = ConciergeState(request=request, user_id=user_id, k=k)
    provider = get_provider()

    for agent in AGENTS:
        t0 = perf_counter()
        try:
            detail = agent.run(state, db, provider)
            ms = (perf_counter() - t0) * 1000
            state.trace.append(AgentStep(agent.NAME, detail, ms, ok=True))
        except Exception as exc:  # noqa: BLE001 — any agent failure -> graceful fallback
            ms = (perf_counter() - t0) * 1000
            state.trace.append(
                AgentStep(agent.NAME, {}, ms, ok=False, error=f"{type(exc).__name__}: {exc}")
            )
            return _fallback(state, db, exc)

    return {
        "request": state.request,
        "intent": state.intent.to_summary() if state.intent else None,
        "picks": [p.to_dict() for p in state.results],
        "trace": [s.to_dict() for s in state.trace],
        "fallback": False,
    }
