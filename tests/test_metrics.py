"""Tests for the ranking metrics.

Each case uses small, hand-checkable inputs so the expected value is obvious.
"""

import math

import pytest

from app.eval.metrics import (
    dcg_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)

# Recommended ranking: items 1 and 3 are relevant, 2 and 4 are not.
RECS = [1, 2, 3, 4, 5]
RELEVANT = {1, 3, 9}  # 9 is relevant but never recommended


def test_precision_at_k():
    # Top-2 = [1, 2]; one hit (item 1) out of 2 -> 0.5
    assert precision_at_k(RECS, RELEVANT, k=2) == 0.5
    # Top-4 = [1,2,3,4]; two hits out of 4 -> 0.5
    assert precision_at_k(RECS, RELEVANT, k=4) == 0.5


def test_recall_at_k():
    # 3 relevant items total (1, 3, 9). Top-4 captures 1 and 3 -> 2/3.
    assert recall_at_k(RECS, RELEVANT, k=4) == pytest.approx(2 / 3)
    # Top-1 captures only item 1 -> 1/3.
    assert recall_at_k(RECS, RELEVANT, k=1) == pytest.approx(1 / 3)


def test_perfect_ranking_scores_one():
    recs = [1, 2, 3]
    relevant = {1, 2, 3}
    assert precision_at_k(recs, relevant, k=3) == 1.0
    assert recall_at_k(recs, relevant, k=3) == 1.0
    assert ndcg_at_k(recs, relevant, k=3) == pytest.approx(1.0)


def test_ndcg_rewards_higher_ranking():
    relevant = {1}
    # Hit at position 1 should score strictly higher than a hit at position 3.
    hit_first = ndcg_at_k([1, 2, 3], relevant, k=3)
    hit_third = ndcg_at_k([2, 3, 1], relevant, k=3)
    assert hit_first == pytest.approx(1.0)
    assert hit_first > hit_third > 0.0


def test_dcg_matches_formula():
    # Hit at rank 1 (idx 0) -> 1/log2(2)=1 ; hit at rank 3 (idx 2) -> 1/log2(4)=0.5
    assert dcg_at_k([1, 0, 1], {1}, k=3) == pytest.approx(1.0 + 0.5)


def test_empty_relevant_set_is_zero():
    assert recall_at_k(RECS, set(), k=3) == 0.0
    assert ndcg_at_k(RECS, set(), k=3) == 0.0


def test_no_hits_is_zero():
    assert precision_at_k([7, 8, 9], {1, 2}, k=3) == 0.0
    assert ndcg_at_k([7, 8, 9], {1, 2}, k=3) == 0.0


def test_invalid_k_raises():
    for fn in (precision_at_k, recall_at_k, ndcg_at_k):
        with pytest.raises(ValueError):
            fn(RECS, RELEVANT, k=0)
