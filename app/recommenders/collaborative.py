"""Collaborative filtering via matrix factorization (TruncatedSVD).

Idea: factor the (sparse) user-item ratings matrix R into low-rank user and
item factor matrices. Each user and movie becomes a vector in the same
`n_factors`-dimensional "taste space"; their dot product predicts a rating.
Recommendations for a user are the unseen movies with the highest predicted
rating.

We mean-center each user's ratings before factorizing so that "no rating"
(filled with 0) means "average for this user" rather than "hated it" — a
standard, important trick for SVD on explicit-rating data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics.pairwise import cosine_similarity

from app.data import loader
from app.recommenders.base import Recommendation, Recommender


class CollaborativeRecommender(Recommender):
    def __init__(self, n_factors: int = 50, random_state: int = 42) -> None:
        self.n_factors = n_factors
        self.random_state = random_state
        self._fitted = False

    def fit(self, ratings: pd.DataFrame | None = None) -> "CollaborativeRecommender":
        # Default to the full dataset; an explicit subset enables holdout eval.
        ratings = loader.load_ratings() if ratings is None else ratings
        movies = loader.load_movies()
        self._titles = dict(zip(movies["movieId"], movies["title"]))

        # Dense user x item matrix. NaN = unrated.
        pivot = ratings.pivot(index="userId", columns="movieId", values="rating")
        self._user_ids = pivot.index.to_numpy()
        self._movie_ids = pivot.columns.to_numpy()
        self._user_pos = {u: i for i, u in enumerate(self._user_ids)}
        self._movie_pos = {m: i for i, m in enumerate(self._movie_ids)}

        # Mean-center per user, then fill unrated with 0 (= the user's mean).
        self._user_means = pivot.mean(axis=1).to_numpy()
        centered = pivot.sub(pivot.mean(axis=1), axis=0).fillna(0.0).to_numpy()

        # Track which (user, movie) pairs were actually rated, to exclude later.
        self._rated_mask = ~pivot.isna().to_numpy()

        # Factorize. n_factors is capped by the matrix's smaller dimension.
        n_comp = min(self.n_factors, min(centered.shape) - 1)
        self._svd = TruncatedSVD(n_components=n_comp, random_state=self.random_state)
        self._user_factors = self._svd.fit_transform(centered)   # (n_users, k)
        self._item_factors = self._svd.components_.T             # (n_items, k)

        # Reconstructed, de-centered predicted ratings for everyone.
        self._pred = self._user_factors @ self._svd.components_
        self._pred += self._user_means[:, None]

        self._fitted = True
        return self

    def _check_fitted(self) -> None:
        if not self._fitted:
            raise RuntimeError("Call fit() before using the recommender.")

    def recommend_for_user(self, user_id: int, k: int = 10) -> list[Recommendation]:
        self._check_fitted()
        if user_id not in self._user_pos:
            raise KeyError(f"Unknown user_id: {user_id}")
        u = self._user_pos[user_id]

        preds = self._pred[u].copy()
        preds[self._rated_mask[u]] = -np.inf  # don't recommend already-rated movies
        top = np.argsort(preds)[::-1][:k]
        return [
            Recommendation(
                movie_id=int(self._movie_ids[i]),
                title=self._titles.get(int(self._movie_ids[i]), "?"),
                score=float(preds[i]),
            )
            for i in top
        ]

    def similar_to_movie(self, movie_id: int, k: int = 10) -> list[Recommendation]:
        self._check_fitted()
        if movie_id not in self._movie_pos:
            raise KeyError(f"Unknown movie_id: {movie_id}")
        m = self._movie_pos[movie_id]

        sims = cosine_similarity(
            self._item_factors[m].reshape(1, -1), self._item_factors
        ).ravel()
        sims[m] = -np.inf  # exclude the movie itself
        top = np.argsort(sims)[::-1][:k]
        return [
            Recommendation(
                movie_id=int(self._movie_ids[i]),
                title=self._titles.get(int(self._movie_ids[i]), "?"),
                score=float(sims[i]),
            )
            for i in top
        ]

    def score(self, user_id: int, movie_ids: np.ndarray) -> np.ndarray:
        self._check_fitted()
        if user_id not in self._user_pos:
            raise KeyError(f"Unknown user_id: {user_id}")
        u = self._user_pos[user_id]
        # For movies not in the training matrix, fall back to the user's mean.
        out = np.full(len(movie_ids), self._user_means[u], dtype=float)
        for j, mid in enumerate(movie_ids):
            pos = self._movie_pos.get(int(mid))
            if pos is not None:
                out[j] = self._pred[u, pos]
        return out

    @property
    def movie_ids(self) -> np.ndarray:
        self._check_fitted()
        return self._movie_ids

    def has_user(self, user_id: int) -> bool:
        self._check_fitted()
        return user_id in self._user_pos
