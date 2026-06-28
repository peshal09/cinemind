"""API tests: boot the real FastAPI app and hit the endpoints.

Using TestClient as a context manager runs the lifespan handler, so the models
are trained once before these tests run (a few seconds on first use).
Recommendations now require auth, so we register+login a throwaway user.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers(client):
    # Unique username: the DB persists between runs, so avoid 409 collisions.
    username = "apitest_" + uuid.uuid4().hex[:8]
    client.post("/auth/register", json={"username": username, "password": "secret123"})
    token = client.post(
        "/auth/login", json={"username": username, "password": "secret123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_api_info_lists_models(client):
    body = client.get("/api").json()
    assert set(body["models"]) == {"collaborative", "content", "hybrid"}


def test_recommend_requires_auth(client):
    assert client.get("/recommend").status_code == 401


def test_recommend_returns_k_items(client, auth_headers):
    resp = client.get("/recommend?k=5", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["recommendations"]) == 5
    # A brand-new account has no ratings -> popularity cold-start.
    assert body["cold_start"] is True
    first = body["recommendations"][0]
    assert {"movie_id", "title", "score"} <= first.keys()


def test_invalid_model_returns_422(client, auth_headers):
    assert client.get("/recommend?model=bogus", headers=auth_headers).status_code == 422


def test_similar_excludes_itself(client):
    resp = client.get("/movies/1/similar?k=5")  # public endpoint
    assert resp.status_code == 200
    ids = [r["movie_id"] for r in resp.json()["similar"]]
    assert 1 not in ids


def test_unknown_movie_returns_404(client):
    assert client.get("/movies/99999/similar").status_code == 404
