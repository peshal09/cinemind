"""Popularity baseline for cold-start users.

A brand-new account has no ratings, so the personalized models can't rank for
it. The standard fallback is to recommend broadly popular, well-liked movies.
We rank by a count-weighted average rating (a movie needs enough ratings to be
trusted), which avoids obscure titles with a single 5-star rating topping the list.
"""

from __future__ import annotations

from functools import lru_cache

from app.data import loader
from app.recommenders.base import Recommendation


@lru_cache(maxsize=1)
def _ranked() -> list[Recommendation]:
    ratings = loader.load_ratings()
    movies = loader.load_movies()
    titles = dict(zip(movies["movieId"], movies["title"]))

    stats = ratings.groupby("movieId")["rating"].agg(["count", "mean"])
    # Bayesian-ish shrinkage: pull low-count means toward the global average.
    global_mean = ratings["rating"].mean()
    m = 50  # minimum-votes prior
    stats["score"] = (
        stats["count"] * stats["mean"] + m * global_mean
    ) / (stats["count"] + m)
    stats = stats.sort_values("score", ascending=False)

    return [
        Recommendation(int(mid), titles.get(int(mid), "?"), float(row.score))
        for mid, row in stats.iterrows()
    ]


def popular_movies(k: int = 10) -> list[Recommendation]:
    return _ranked()[:k]
