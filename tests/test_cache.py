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


def test_ask_key_normalizes_question():
    # Case / surrounding-whitespace differences map to the same cache entry...
    assert redis_client.ask_key("A Heist Thriller", 5) == redis_client.ask_key(
        "  a heist   thriller ", 5
    )
    # ...but k is part of the key.
    assert redis_client.ask_key("a heist thriller", 5) != redis_client.ask_key(
        "a heist thriller", 10
    )


def test_generic_cache_roundtrip_and_invalidate_ask():
    key = redis_client.ask_key("totally unique probe question xyz", 5)
    redis_client.invalidate_ask()
    assert redis_client.get_cached(key) is None        # miss

    redis_client.set_cached(key, {"answer": "hi", "citations": []})
    assert redis_client.get_cached(key) == {"answer": "hi", "citations": []}  # hit

    assert redis_client.invalidate_ask() >= 1
    assert redis_client.get_cached(key) is None         # cleared


def test_why_is_cached_and_invalidated_by_rating(client, monkeypatch):
    headers, user_id = _new_user(client)
    # Rate a film so the user has taste (not the cold-start path).
    client.post("/ratings", json={"movie_id": 1, "rating": 5.0}, headers=headers)

    calls = {"n": 0}

    class _FakeProvider:
        def complete(self, system, user):
            calls["n"] += 1
            return "Because you loved similar films."

    monkeypatch.setattr("app.rag.explain.get_provider", lambda: _FakeProvider())
    redis_client.invalidate_user(user_id)  # start clean

    first = client.get("/recommendations/2/why", headers=headers).json()
    assert first["cached"] is False and calls["n"] == 1

    second = client.get("/recommendations/2/why", headers=headers).json()
    assert second["cached"] is True and calls["n"] == 1   # served from cache

    # Re-rating invalidates this user's /why cache -> next call recomputes.
    client.post("/ratings", json={"movie_id": 3, "rating": 4.0}, headers=headers)
    third = client.get("/recommendations/2/why", headers=headers).json()
    assert third["cached"] is False and calls["n"] == 2
