"""FastAPI surface for CineMind.

Endpoints:
    POST /auth/register               -> create an account
    POST /auth/login                  -> get a JWT
    GET  /auth/me                     -> the current user
    GET  /recommend                   -> recommendations for the logged-in user
    GET  /movies/{movie_id}/similar   -> movies similar to a given movie

Recommendation endpoints accept:
    ?model=hybrid|collaborative|content   (default: hybrid)
    ?k=<int 1..100>                       (default: 10)

The three models are trained once at startup (in the lifespan handler) and held
in app state, so individual requests are just a lookup + ranking — no refitting.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.auth.dependencies import get_current_user
from app.auth.router import router as auth_router
from app.cache import redis_client
from app.db.models import User
from app.ratings import router as ratings_router
from app.rag.ask import router as ask_router
from app.rag.explain import router as explain_router
from app.recommenders import popularity
from app.search import router as search_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
from app.recommenders.base import Recommendation, Recommender
from app.recommenders.collaborative import CollaborativeRecommender
from app.recommenders.content_based import ContentBasedRecommender
from app.recommenders.hybrid import HybridRecommender

# Shared store for the fitted models, populated at startup.
MODELS: dict[str, Recommender] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fit once. Hybrid fits its own collaborative+content, but we expose all
    # three independently, so train dedicated instances for the standalone ones.
    MODELS["collaborative"] = CollaborativeRecommender().fit()
    MODELS["content"] = ContentBasedRecommender().fit()
    MODELS["hybrid"] = HybridRecommender().fit()
    yield
    MODELS.clear()


app = FastAPI(title="CineMind", version="0.1.0", lifespan=lifespan)

# CORS so the (separately served) index.html frontend can call this API.
# Comma-separated origins in CORS_ORIGINS; "*" (the dev default) allows any.
# Safe to allow "*" here because we authenticate via the Authorization header
# (bearer tokens), not cookies, so allow_credentials stays False.
_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(ratings_router)
app.include_router(search_router)
app.include_router(ask_router)
app.include_router(explain_router)


def get_model(
    model: str = Query("hybrid", pattern="^(hybrid|collaborative|content)$")
) -> Recommender:
    """Resolve the ?model= query param to a fitted recommender."""
    return MODELS[model]


def _serialize(recs: list[Recommendation]) -> list[dict]:
    return [
        {"movie_id": r.movie_id, "title": r.title, "score": round(r.score, 4)}
        for r in recs
    ]


@app.get("/")
def root() -> dict:
    return {
        "name": "CineMind",
        "version": "0.1.0",
        "models": sorted(MODELS.keys()),
        "endpoints": ["/auth/register", "/auth/login", "/recommend", "/movies/{movie_id}/similar"],
    }


@app.get("/recommend")
def recommend(
    k: int = Query(10, ge=1, le=100),
    model_name: str = Query("hybrid", alias="model", pattern="^(hybrid|collaborative|content)$"),
    recommender: Recommender = Depends(get_model),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Recommendations for the authenticated user.

    Served from the Redis cache when warm; otherwise computed, cached, returned.
    Falls back to a popularity baseline for accounts the batch-fitted model
    doesn't know yet (e.g. a just-registered user with no ratings).
    """
    cached = redis_client.get_cached_feed(current_user.id, model_name, k)
    if cached is not None:
        return {**cached, "cached": True}

    try:
        recs = recommender.recommend_for_user(current_user.id, k)
        cold_start = False
    except KeyError:
        recs = popularity.popular_movies(k)
        cold_start = True
    payload = {
        "user_id": current_user.id,
        "model": "popularity" if cold_start else model_name,
        "cold_start": cold_start,
        "count": len(recs),
        "recommendations": _serialize(recs),
    }
    redis_client.set_cached_feed(current_user.id, model_name, k, payload)
    return {**payload, "cached": False}


@app.get("/movies/{movie_id}/similar")
def similar(
    movie_id: int,
    k: int = Query(10, ge=1, le=100),
    model_name: str = Query("hybrid", alias="model", pattern="^(hybrid|collaborative|content)$"),
    recommender: Recommender = Depends(get_model),
) -> dict:
    try:
        recs = recommender.similar_to_movie(movie_id, k)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown movie_id: {movie_id}")
    return {"movie_id": movie_id, "model": model_name, "count": len(recs), "similar": _serialize(recs)}
