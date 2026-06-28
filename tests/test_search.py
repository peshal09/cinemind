"""Semantic search tests.

These boot the app (which lazy-loads the embedding model on first search) and hit
the real /search/semantic endpoint against the embedded movies in Postgres.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_exact_title_ranks_itself_first(client):
    # The keyword boost ensures an exact-title query lands on the movie itself.
    r = client.post("/search/semantic", json={"query": "Toy Story", "k": 5})
    assert r.status_code == 200
    results = r.json()["results"]
    assert results[0]["movie_id"] == 1
    assert results[0]["title"].startswith("Toy Story")
    assert results[0]["keyword_score"] == 1.0


def test_thematic_query_returns_sensible_movies(client):
    # A natural-language theme should return topically-coherent movies by MEANING,
    # not literal title words. With the gte-small embeddings, "a mind-bending
    # sci-fi about dreams" surfaces films like Inception, Paprika, Solaris and
    # Waking Life -- most of which don't contain "dream" in the title at all.
    r = client.post(
        "/search/semantic",
        json={"query": "a mind-bending sci-fi about dreams", "k": 10},
    )
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) == 10
    assert all(x["vector_score"] > 0.5 for x in results)  # real, strong similarity

    titles = [x["title"].lower() for x in results]
    # A spread of genuinely dream / mind-bending films we expect to surface.
    themed = ["inception", "paprika", "dreams", "solaris", "science of sleep",
              "waking life", "altered states", "dreamcatcher", "eternal sunshine"]
    assert sum(any(m in t for m in themed) for t in titles) >= 5  # topically on-point
    # Thematic, not lexical: at least one strong match has no "dream" in its title.
    assert any("dream" not in t for t in titles)
