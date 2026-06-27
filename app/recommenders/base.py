"""Shared types and interface for all recommenders.

Every recommender implements the same small contract so the API layer and the
hybrid can treat them interchangeably:

    fit()                          -> self      (train / build internal state)
    recommend_for_user(uid, k)     -> [Recommendation]
    similar_to_movie(mid, k)       -> [Recommendation]
    score(uid, movie_ids)          -> np.ndarray (per-movie affinity, for hybrid)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Recommendation:
    """One scored recommendation, ready to serialize in an API response."""

    movie_id: int
    title: str
    score: float


class Recommender(ABC):
    """Common interface. See module docstring for the contract."""

    @abstractmethod
    def fit(self) -> "Recommender":
        ...

    @abstractmethod
    def recommend_for_user(self, user_id: int, k: int = 10) -> list[Recommendation]:
        ...

    @abstractmethod
    def similar_to_movie(self, movie_id: int, k: int = 10) -> list[Recommendation]:
        ...

    @abstractmethod
    def score(self, user_id: int, movie_ids: np.ndarray) -> np.ndarray:
        """Per-movie affinity for `user_id`, aligned to `movie_ids`.

        Used by the hybrid to blend models. Higher = better.
        """
        ...


def minmax_normalize(scores: np.ndarray) -> np.ndarray:
    """Scale scores to [0, 1]. Lets us blend models on different scales.

    Returns all-0.5 if every score is identical (avoids divide-by-zero).
    """
    if scores.size == 0:
        return scores
    lo, hi = float(np.min(scores)), float(np.max(scores))
    if hi - lo < 1e-12:
        return np.full_like(scores, 0.5, dtype=float)
    return (scores - lo) / (hi - lo)
