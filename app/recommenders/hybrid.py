"""Hybrid recommender: a weighted blend of collaborative + content-based.

Idea: each base model has a blind spot. Collaborative filtering needs enough
ratings to learn a movie's latent factors (weak on niche/new films);
content-based only knows genres (ignores the "people who liked X also liked Y"
signal). We min-max normalize each model's scores onto [0, 1] so they're
comparable, then blend:

    final = alpha * collaborative + (1 - alpha) * content_based

If a user is unknown to the collaborative model (cold start) we fall back to
content-based alone.
"""

from __future__ import annotations

import numpy as np

from app.data import loader
from app.recommenders.base import Recommendation, Recommender, minmax_normalize
from app.recommenders.collaborative import CollaborativeRecommender
from app.recommenders.content_based import ContentBasedRecommender


class HybridRecommender(Recommender):
    def __init__(self, alpha: float = 0.5) -> None:
        if not 0.0 <= alpha <= 1.0:
            raise ValueError("alpha must be in [0, 1]")
        self.alpha = alpha
        self.collaborative = CollaborativeRecommender()
        self.content = ContentBasedRecommender()
        self._fitted = False

    def fit(self, ratings: pd.DataFrame | None = None) -> "HybridRecommender":
        ratings = loader.load_ratings() if ratings is None else ratings
        self.collaborative.fit(ratings)
        self.content.fit(ratings)
        movies = loader.load_movies()
        self._all_movie_ids = movies["movieId"].to_numpy()
        self._titles = dict(zip(movies["movieId"], movies["title"]))
        self._seen_by_user = (
            ratings.groupby("userId")["movieId"]
            .apply(lambda s: set(s.astype(int)))
            .to_dict()
        )
        self._fitted = True
        return self

    def _check_fitted(self) -> None:
        if not self._fitted:
            raise RuntimeError("Call fit() before using the recommender.")

    def _blended_scores(self, user_id: int, movie_ids: np.ndarray) -> np.ndarray:
        content = minmax_normalize(self.content.score(user_id, movie_ids))
        if not self.collaborative.has_user(user_id):
            return content  # cold start: content-only
        collab = minmax_normalize(self.collaborative.score(user_id, movie_ids))
        return self.alpha * collab + (1 - self.alpha) * content

    def recommend_for_user(self, user_id: int, k: int = 10) -> list[Recommendation]:
        self._check_fitted()
        if user_id not in self._seen_by_user:
            raise KeyError(f"Unknown user_id: {user_id}")
        movie_ids = self._all_movie_ids
        blended = self._blended_scores(user_id, movie_ids)

        seen = self._seen_by_user.get(user_id, set())
        order = np.argsort(blended)[::-1]
        out: list[Recommendation] = []
        for i in order:
            mid = int(movie_ids[i])
            if mid in seen:
                continue
            out.append(
                Recommendation(mid, self._titles.get(mid, "?"), float(blended[i]))
            )
            if len(out) == k:
                break
        return out

    def similar_to_movie(self, movie_id: int, k: int = 10) -> list[Recommendation]:
        """Blend the two models' similarity rankings for a movie."""
        self._check_fitted()
        # Pull a wide candidate list from each, then blend by normalized score.
        wide = max(k * 5, 50)
        collab = {r.movie_id: r.score for r in self.collaborative.similar_to_movie(movie_id, wide)}
        content = {r.movie_id: r.score for r in self.content.similar_to_movie(movie_id, wide)}

        candidates = np.array(sorted(set(collab) | set(content)))
        c_scores = minmax_normalize(np.array([collab.get(m, 0.0) for m in candidates]))
        k_scores = minmax_normalize(np.array([content.get(m, 0.0) for m in candidates]))
        blended = self.alpha * c_scores + (1 - self.alpha) * k_scores

        top = np.argsort(blended)[::-1][:k]
        return [
            Recommendation(
                int(candidates[i]),
                self._titles.get(int(candidates[i]), "?"),
                float(blended[i]),
            )
            for i in top
        ]

    def score(self, user_id: int, movie_ids: np.ndarray) -> np.ndarray:
        self._check_fitted()
        return self._blended_scores(user_id, movie_ids)
