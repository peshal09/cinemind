"""Offline evaluation with a temporal holdout.

Why a holdout: `recommend_for_user` deliberately excludes movies a user has
already rated, so we can't score recommendations against ratings the model was
trained on — they'd all be filtered out. Instead we hide each user's most recent
ratings, fit the model on the rest, then check whether those held-out movies the
user *liked* show up in the recommendations.

For each user we sort ratings by time, move the last ~`test_frac` into a test
set, and treat held-out movies rated >= `like_threshold` as the answer key.
The split is temporal (no RNG) so results are deterministic.
"""

from __future__ import annotations

from statistics import mean

import pandas as pd

from app.data import loader
from app.eval.metrics import ndcg_at_k, precision_at_k, recall_at_k


def temporal_holdout(ratings: pd.DataFrame, test_frac: float = 0.2, min_ratings: int = 5):
    """Split into (train_df, {user_id: liked_test_movie_ids})."""
    train_parts, test_liked = [], {}
    for uid, grp in ratings.groupby("userId"):
        if len(grp) < min_ratings:
            train_parts.append(grp)
            continue
        grp = grp.sort_values("timestamp")
        n_test = max(1, int(len(grp) * test_frac))
        train_parts.append(grp.iloc[:-n_test])
        test = grp.iloc[-n_test:]
        liked = set(test.loc[test["rating"] >= 4.0, "movieId"].astype(int))
        if liked:
            test_liked[uid] = liked
    return pd.concat(train_parts), test_liked


def evaluate(recommender_factory, k: int = 10, n_users: int = 30) -> dict:
    """Fit a fresh recommender on the training split and score it @k.

    `recommender_factory` is a zero-arg callable returning an unfit recommender
    (e.g. `HybridRecommender`). Returns averaged precision/recall/ndcg @k.
    """
    train_df, test_liked = temporal_holdout(loader.load_ratings())
    model = recommender_factory()
    model.fit(train_df)

    p, r, n = [], [], []
    for uid in list(test_liked)[:n_users]:
        liked = test_liked[uid]
        recs = [rec.movie_id for rec in model.recommend_for_user(uid, k)]
        p.append(precision_at_k(recs, liked, k))
        r.append(recall_at_k(recs, liked, k))
        n.append(ndcg_at_k(recs, liked, k))

    return {
        "k": k,
        "users_evaluated": len(p),
        "precision@k": round(mean(p), 4) if p else 0.0,
        "recall@k": round(mean(r), 4) if r else 0.0,
        "ndcg@k": round(mean(n), 4) if n else 0.0,
    }
