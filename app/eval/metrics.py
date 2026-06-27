"""Offline ranking metrics for evaluating recommenders.

These answer "of the items we recommended, how many were actually relevant, and
were the good ones ranked near the top?" Given a ranked list of recommended
movie ids and the set the user actually liked (the "relevant" set), we score the
ranking. All metrics return a float in [0, 1]; higher is better.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
import math


def precision_at_k(recommended: Sequence[int], relevant: Iterable[int], k: int) -> float:
    """Fraction of the top-k recommendations that are relevant.

    "Of what we showed, how much was good?"
    """
    if k <= 0:
        raise ValueError("k must be positive")
    relevant = set(relevant)
    top_k = recommended[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for item in top_k if item in relevant)
    return hits / k


def recall_at_k(recommended: Sequence[int], relevant: Iterable[int], k: int) -> float:
    """Fraction of all relevant items that appear in the top-k.

    "Of everything good, how much did we surface?"
    """
    if k <= 0:
        raise ValueError("k must be positive")
    relevant = set(relevant)
    if not relevant:
        return 0.0
    top_k = recommended[:k]
    hits = sum(1 for item in top_k if item in relevant)
    return hits / len(relevant)


def dcg_at_k(recommended: Sequence[int], relevant: Iterable[int], k: int) -> float:
    """Discounted cumulative gain with binary relevance.

    A relevant item at rank i contributes 1 / log2(i + 1), so hits ranked higher
    are worth more than hits ranked lower.
    """
    relevant = set(relevant)
    return sum(
        1.0 / math.log2(rank + 2)  # rank is 0-based -> position 1 uses log2(2)
        for rank, item in enumerate(recommended[:k])
        if item in relevant
    )


def ndcg_at_k(recommended: Sequence[int], relevant: Iterable[int], k: int) -> float:
    """Normalized DCG: DCG divided by the best achievable DCG (ideal ordering).

    Rewards putting relevant items as high as possible. 1.0 = perfect ranking.
    """
    if k <= 0:
        raise ValueError("k must be positive")
    relevant = set(relevant)
    if not relevant:
        return 0.0
    actual = dcg_at_k(recommended, relevant, k)
    # Ideal: every top slot (up to #relevant or k) is a hit.
    ideal_hits = min(len(relevant), k)
    ideal = sum(1.0 / math.log2(rank + 2) for rank in range(ideal_hits))
    return actual / ideal if ideal > 0 else 0.0
