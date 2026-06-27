"""Cache tests: feed caching, rating-triggered invalidation, and helpers.

These need a running Redis; if it's unreachable the whole module is skipped so
the rest of the suite still runs.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.cache import redis_client
from app.main import app


def _redis_up() -> bool:
    try:
        return bool(redis_client.client.ping())
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _redis_up(), reason="Redis not available")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _new_user(client):
    """Register + login a fresh user; return (headers, user_id)."""
    u = "cachetest_" + uuid.uuid4().hex[:8]
    client.post("/auth/register", json={"username": u, "password": "secret123"})
    token = client.post(
        "/auth/login", json={"username": u, "password": "secret123"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    user_id = client.get("/auth/me", headers=headers).json()["id"]
    return headers, user_id


def test_feed_is_cached_on_second_call(client):
    headers, user_id = _new_user(client)
    redis_client.invalidate_user(user_id)  # start clean

    first = client.get("/recommend?k=3", headers=headers).json()
    assert first["cached"] is False

    second = client.get("/recommend?k=3", headers=headers).json()
    assert second["cached"] is True
    # Same payload content, just served from cache.
    assert second["recommendations"] == first["recommendations"]


def test_rating_invalidates_cache(client):
    headers, _ = _new_user(client)
    client.get("/recommend?k=3", headers=headers)  # warm cache
    assert client.get("/recommend?k=3", headers=headers).json()["cached"] is True

    resp = client.post(
        "/ratings", json={"movie_id": 1, "rating": 4.0}, headers=headers
    ).json()
    assert resp["cache_keys_invalidated"] >= 1

    # Next call recomputes (cache was cleared).
    assert client.get("/recommend?k=3", headers=headers).json()["cached"] is False


def test_cache_helpers_roundtrip(client):
    _, user_id = _new_user(client)
    redis_client.invalidate_user(user_id)

    assert redis_client.get_cached_feed(user_id, "hybrid", 5) is None
    payload = {"hello": "world"}
    redis_client.set_cached_feed(user_id, "hybrid", 5, payload)
    assert redis_client.get_cached_feed(user_id, "hybrid", 5) == payload

    removed = redis_client.invalidate_user(user_id)
    assert removed >= 1
    assert redis_client.get_cached_feed(user_id, "hybrid", 5) is None
