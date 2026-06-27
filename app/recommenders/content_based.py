"""Content-based recommender using movie genres.

Idea: describe every movie by its genres as a TF-IDF vector (TF-IDF down-weights
common genres like "Drama" and rewards rarer, more distinctive ones). Two movies
are "similar" if their genre vectors point the same way (high cosine similarity).

For a user, we build a taste profile by summing the genre vectors of the movies
they rated, weighted by how much they liked each one relative to their own
average. We then recommend unseen movies whose genre vector best matches that
profile. This needs no other users' data, so it works for niche movies that
collaborative filtering has too few ratings to handle.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.data import loader
from app.recommenders.base import Recommendation, Recommender


class ContentBasedRecommender(Recommender):
    def __init__(self) -> None:
        self._fitted = False

    def fit(self, ratings: pd.DataFrame | None = None) -> "ContentBasedRecommender":
        movies = loader.load_movies()
        self._movie_ids = movies["movieId"].to_numpy()
        self._movie_pos = {m: i for i, m in enumerate(self._movie_ids)}
        self._titles = dict(zip(movies["movieId"], movies["title"]))

        # Treat the '|'-separated genre string as a document; each genre a token.
        genre_docs = movies["genres"].str.replace("|", " ", regex=False)
        self._vectorizer = TfidfVectorizer(token_pattern=r"[^ ]+")
        self._genre_matrix = self._vectorizer.fit_transform(genre_docs)  # sparse

        self._ratings = loader.load_ratings() if ratings is None else ratings
        self._user_means = self._ratings.groupby("userId")["rating"].mean()

        self._fitted = True
        return self

    def _check_fitted(self) -> None:
        if not self._fitted:
            raise RuntimeError("Call fit() before using the recommender.")

    def _user_profile(self, user_id: int) -> np.ndarray:
        """Genre-space vector for a user, weighted by liking vs. their mean."""
        user_rows = self._ratings[self._ratings["userId"] == user_id]
        if user_rows.empty:
            raise KeyError(f"Unknown user_id: {user_id}")
        mean = self._user_means[user_id]

        profile = np.zeros(self._genre_matrix.shape[1], dtype=float)
        for movie_id, rating in zip(user_rows["movieId"], user_rows["rating"]):
            pos = self._movie_pos.get(int(movie_id))
            if pos is None:
                continue
            profile += (rating - mean) * self._genre_matrix[pos].toarray().ravel()
        return profile

    def _seen_movies(self, user_id: int) -> set[int]:
        rows = self._ratings[self._ratings["userId"] == user_id]
        return set(rows["movieId"].astype(int))

    def recommend_for_user(self, user_id: int, k: int = 10) -> list[Recommendation]:
        self._check_fitted()
        profile = self._user_profile(user_id).reshape(1, -1)
        sims = cosine_similarity(profile, self._genre_matrix).ravel()

        seen = self._seen_movies(user_id)
        order = np.argsort(sims)[::-1]
        out: list[Recommendation] = []
        for i in order:
            mid = int(self._movie_ids[i])
            if mid in seen:
                continue
            out.append(
                Recommendation(mid, self._titles.get(mid, "?"), float(sims[i]))
            )
            if len(out) == k:
                break
        return out

    def similar_to_movie(self, movie_id: int, k: int = 10) -> list[Recommendation]:
        self._check_fitted()
        if movie_id not in self._movie_pos:
            raise KeyError(f"Unknown movie_id: {movie_id}")
        m = self._movie_pos[movie_id]
        sims = cosine_similarity(self._genre_matrix[m], self._genre_matrix).ravel()
        sims[m] = -np.inf  # exclude the movie itself
        top = np.argsort(sims)[::-1][:k]
        return [
            Recommendation(
                int(self._movie_ids[i]),
                self._titles.get(int(self._movie_ids[i]), "?"),
                float(sims[i]),
            )
            for i in top
        ]

    def score(self, user_id: int, movie_ids: np.ndarray) -> np.ndarray:
        self._check_fitted()
        profile = self._user_profile(user_id).reshape(1, -1)
        sims_all = cosine_similarity(profile, self._genre_matrix).ravel()
        out = np.zeros(len(movie_ids), dtype=float)
        for j, mid in enumerate(movie_ids):
            pos = self._movie_pos.get(int(mid))
            if pos is not None:
                out[j] = sims_all[pos]
        return out

    def has_user(self, user_id: int) -> bool:
        self._check_fitted()
        return user_id in set(self._ratings["userId"].astype(int))
