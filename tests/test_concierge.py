"""Multi-agent concierge tests.

Each agent is unit-tested in isolation (mocked LLM, real DB), plus an end-to-end
endpoint test and a fallback test. Uses TestClient so the recommender MODELS are
fitted by the app lifespan.
"""

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.concierge import critic, explainer, preference, retrieval
from app.concierge.state import Candidate, ConciergeState, Intent
from app.db.database import SessionLocal
from app.db.models import Movie
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # lifespan fits the recommender MODELS
        yield c


class FakeProvider:
    def __init__(self, responder):
        self.responder = responder
        self.calls = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.responder(system, user)


def _new_user(client):
    u = "concierge_" + uuid.uuid4().hex[:8]
    client.post("/auth/register", json={"username": u, "password": "secret123"})
    token = client.post(
        "/auth/login", json={"username": u, "password": "secret123"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    user_id = client.get("/auth/me", headers=headers).json()["id"]
    return headers, user_id


# ------------------------------ agent units -------------------------------
def test_preference_parses_intent_and_routes_unsupported(client):
    intent_json = json.dumps({
        "semantic_query": "mind-bending sci-fi about dreams",
        "genres": ["Sci-Fi"],
        "decade": "1990s",
        "similar_to": ["Inception"],
        "unsupported": ["max_runtime: 120"],
    })
    fake = FakeProvider(lambda s, u: intent_json)
    state = ConciergeState(request="a 90s sci-fi like Inception under 2 hours", user_id=999999)
    with SessionLocal() as db:
        out = preference.run(state, db, fake)

    assert out["parsed_ok"] is True
    assert state.intent.genres == ["Sci-Fi"]
    assert state.intent.decade == "1990s"
    assert "max_runtime: 120" in state.intent.unsupported


def test_retrieval_merges_semantic_and_collaborative(client):
    state = ConciergeState(request="a fun space adventure", user_id=1)  # user 1 is a seeded MovieLens user
    state.intent = Intent(semantic_query="a fun space adventure", raw_request="a fun space adventure")
    with SessionLocal() as db:
        out = retrieval.run(state, db, FakeProvider(lambda s, u: ""))

    assert out["candidates"] > 0
    assert len(state.candidates) == out["candidates"]
    # Every candidate has its Movie row available for the critic.
    assert all(c.movie_id in state.movies_by_id for c in state.candidates)


def test_retrieval_constrained_pulls_year_matching_films(client):
    # A year constraint must pull actual in-year films into the pool (not rely on the
    # semantic top-40 happening to contain them).
    state = ConciergeState(request="a thriller", user_id=1)
    state.intent = Intent(
        semantic_query="a thriller", raw_request="a thriller",
        year_min=1994, year_max=1994,
    )
    with SessionLocal() as db:
        out = retrieval.run(state, db, FakeProvider(lambda s, u: ""))

    assert out["constrained"] > 0
    years = [
        (getattr(state.movies_by_id.get(c.movie_id), "release_date", None) or "")[:4]
        for c in state.candidates
    ]
    assert "1994" in years  # an actual 1994 film made it into the pool


def test_critic_honest_empty_when_constraint_matches_nothing(client):
    # Out-of-catalog year -> the Critic must return an honest empty, not relax into junk.
    with SessionLocal() as db:
        movies = db.query(Movie).filter(Movie.release_date.like("199%")).limit(2).all()
        state = ConciergeState(request="x", user_id=999999, k=5)
        state.intent = Intent(
            semantic_query="x", raw_request="x", year_min=2099, year_max=2099,
        )
        state.movies_by_id = {m.id: m for m in movies}
        state.candidates = [Candidate(m.id, m.title, semantic_score=0.8) for m in movies]
        out = critic.run(state, db, FakeProvider(lambda s, u: ""))

    assert out["no_match"] is True
    assert state.shortlist == []


def test_critic_filters_by_genre_and_notes_unsupported(client):
    with SessionLocal() as db:
        comedy = db.query(Movie).filter(Movie.genres.like("%Comedy%")).first()
        drama_only = db.query(Movie).filter(Movie.genres == "Drama").first()
        state = ConciergeState(request="something funny", user_id=999999, k=5)
        state.intent = Intent(
            semantic_query="funny", raw_request="funny",
            genres=["Comedy"], unsupported=["max_runtime: 120"],
        )
        state.movies_by_id = {comedy.id: comedy, drama_only.id: drama_only}
        state.candidates = [
            Candidate(comedy.id, comedy.title, semantic_score=0.9, source="semantic"),
            Candidate(drama_only.id, drama_only.title, semantic_score=0.8, source="semantic"),
        ]
        out = critic.run(state, db, FakeProvider(lambda s, u: ""))

    titles = [c.title for c in state.shortlist]
    assert comedy.title in titles
    assert drama_only.title not in titles            # filtered out (not a Comedy)
    assert out["noted_not_enforced"] == ["max_runtime: 120"]


def test_critic_blends_normalized_scores(client):
    # A strongly-relevant semantic match must outrank a generic film with a high
    # collaborative/popularity score (different scales -> must be normalized first).
    with SessionLocal() as db:
        a = db.query(Movie).first()
        b = db.query(Movie).offset(1).first()
        state = ConciergeState(request="x", user_id=999999, k=5)
        state.intent = Intent(semantic_query="x", raw_request="x")
        state.movies_by_id = {a.id: a, b.id: b}
        state.candidates = [
            Candidate(a.id, a.title, semantic_score=0.85, collab_score=0.0, source="semantic"),
            Candidate(b.id, b.title, semantic_score=0.20, collab_score=4.30, source="popularity"),
        ]
        critic.run(state, db, FakeProvider(lambda s, u: ""))

    # Relevance leads: the semantic match (a) is ranked above the popular film (b).
    assert state.shortlist[0].movie_id == a.id
    assert all(0.0 <= c.score <= 1.5 for c in state.shortlist)  # normalized, not rating-scale


def test_critic_llm_reranks_pool(client):
    # Blended pre-rank would be a, b, c (descending semantic); the LLM reranker
    # returns [3, 1, 2], so the shortlist must come out c, a, b.
    with SessionLocal() as db:
        a, b, c = db.query(Movie).limit(3).all()
        state = ConciergeState(request="x", user_id=999999, k=3)
        state.intent = Intent(semantic_query="x", raw_request="x")
        state.movies_by_id = {a.id: a, b.id: b, c.id: c}
        state.candidates = [
            Candidate(a.id, a.title, semantic_score=0.9),
            Candidate(b.id, b.title, semantic_score=0.8),
            Candidate(c.id, c.title, semantic_score=0.7),
        ]
        out = critic.run(state, db, FakeProvider(lambda s, u: "[3, 1, 2]"))

    assert out["reranked"] is True
    assert [p.movie_id for p in state.shortlist] == [c.id, a.id, b.id]


def test_explainer_attaches_why_to_picks(client):
    with SessionLocal() as db:
        movie = db.query(Movie).filter(Movie.overview.isnot(None)).first()
        state = ConciergeState(request="something good", user_id=999999, k=5)
        state.shortlist = [Candidate(movie.id, movie.title, semantic_score=0.9)]
        state.movies_by_id = {movie.id: movie}
        resp = json.dumps([{"title": movie.title, "why": "You'll love it.", "based_on": []}])
        out = explainer.run(state, db, FakeProvider(lambda s, u: resp))

    assert out["explained"] == 1
    assert state.results[0].why == "You'll love it."


# --------------------------- endpoint / orchestration ----------------------
def _pipeline_responder(system, user):
    # One mock standing in for both LLM-using agents.
    if system.startswith("You convert"):                       # preference
        return json.dumps({"semantic_query": "a fun space adventure", "genres": []})
    return json.dumps([{"title": "t", "why": "Fits your vibe.", "based_on": []}])  # explainer


def test_concierge_endpoint_full_pipeline(client, monkeypatch):
    headers, _ = _new_user(client)
    fake = FakeProvider(_pipeline_responder)
    monkeypatch.setattr("app.concierge.orchestrator.get_provider", lambda: fake)

    r = client.post("/concierge", json={"request": "a fun space adventure", "k": 3}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["fallback"] is False
    assert [s["agent"] for s in body["trace"]] == ["preference", "retrieval", "critic", "explainer"]
    assert all(s["ok"] for s in body["trace"])
    assert body["picks"]                                       # non-empty shortlist


def test_concierge_falls_back_when_agent_fails(client, monkeypatch):
    headers, _ = _new_user(client)
    monkeypatch.setattr(
        "app.concierge.orchestrator.get_provider",
        lambda: FakeProvider(lambda s, u: json.dumps({"semantic_query": "x"})),
    )

    def boom(state, db, provider):
        raise RuntimeError("retrieval exploded")

    monkeypatch.setattr("app.concierge.retrieval.run", boom)

    r = client.post("/concierge", json={"request": "anything", "k": 3}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["fallback"] is True
    assert body["picks"]                                       # recommender still answered
    assert body["trace"][-1]["agent"] == "retrieval"
    assert body["trace"][-1]["ok"] is False


def test_concierge_requires_auth(client):
    assert client.post("/concierge", json={"request": "x"}).status_code == 401
