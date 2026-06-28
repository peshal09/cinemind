"""RAG /ask tests with a mocked LLM provider (deterministic, no key/network).

The fake provider is installed by monkeypatching `app.rag.ask.get_provider`, so we
exercise the real retrieval, guard, context-building, and citation-validation logic
while controlling the model's output.
"""

import json
import re

import pytest
from fastapi.testclient import TestClient

import app.rag.ask as ask_module
from app.llm.base import LLMUnavailableError
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class FakeProvider:
    def __init__(self, responder):
        self.responder = responder
        self.calls = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.responder(system, user)


@pytest.fixture
def patch_provider(monkeypatch):
    def _install(responder):
        fake = FakeProvider(responder)
        monkeypatch.setattr(ask_module, "get_provider", lambda: fake)
        return fake
    return _install


def _first_context_title(user_message: str):
    """The first movie title in the built context block."""
    m = re.search(r"Title: (.+)", user_message)
    return m.group(1).strip() if m else None


def test_grounded_answer_validates_citations(client, patch_provider):
    # Model cites one real retrieved title + one invented title; validation must
    # keep the real one and drop the invented one.
    def responder(system, user):
        real = _first_context_title(user)
        return json.dumps(
            {"answer": "A fitting movie about dreams.",
             "citations": [real, "Totally Made Up Film (1899)"]}
        )

    fake = patch_provider(responder)
    r = client.post("/ask", json={"question": "a mind-bending movie about dreams", "k": 5})
    assert r.status_code == 200
    body = r.json()

    assert body["answer"]                                   # non-empty answer
    assert len(fake.calls) == 1                             # LLM was called (grounded)
    cited = [c["title"] for c in body["citations"]]
    assert cited                                            # at least one citation
    assert "Totally Made Up Film (1899)" not in cited      # invented citation dropped
    assert set(cited).issubset(set(body["used_context"]))  # only retrieved movies


def test_cast_question_uses_top_cast(client, patch_provider):
    # The cast question should retrieve a DiCaprio film, so the built context must
    # contain his name (proving top_cast data is fed to the model).
    def responder(system, user):
        return json.dumps(
            {"answer": "It stars Leonardo DiCaprio.",
             "citations": [_first_context_title(user)]}
        )

    fake = patch_provider(responder)
    r = client.post("/ask", json={"question": "which of these stars Leonardo DiCaprio?", "k": 5})
    assert r.status_code == 200

    assert len(fake.calls) == 1
    context = fake.calls[0][1]
    assert "Leonardo DiCaprio" in context                  # top_cast is in the context
    assert r.json()["citations"]                           # valid citation returned


def _strip_year(title: str) -> str:
    return re.sub(r"\s*\(\d{4}\)\s*$", "", title).strip()


def test_citation_matching_is_format_tolerant(client, patch_provider):
    # The model cites the right film but loosely: no year, article moved to the
    # front ("Boxer, The (1997)" -> "The Boxer"). Robust matching must still keep it.
    def responder(system, user):
        loose = _strip_year(_first_context_title(user))
        m = re.match(r"^(.*),\s*(The|A|An)$", loose)
        if m:
            loose = f"{m.group(2)} {m.group(1)}"
        return json.dumps({"answer": "A great pick.", "citations": [loose]})

    patch_provider(responder)
    r = client.post("/ask", json={"question": "a film about boxing", "k": 5})
    assert r.status_code == 200
    assert r.json()["citations"]  # the loosely-formatted citation still validated


def test_prose_answer_recovers_citations_from_text(client, patch_provider):
    # The model ignores the JSON format and just names a film in prose; the fallback
    # should recover the citation by scanning the answer text.
    def responder(system, user):
        base = _strip_year(_first_context_title(user))
        return f'The standout here is "{base}", a great film.'

    patch_provider(responder)
    r = client.post("/ask", json={"question": "a film about boxing", "k": 5})
    assert r.status_code == 200
    assert r.json()["citations"]  # recovered from prose, no JSON returned


def test_llm_outage_degrades_to_503_not_500(client, patch_provider):
    # When the provider exhausts all models, /ask must return a clean 503 with a
    # clear message -- never a raw 500.
    def responder(system, user):
        raise LLMUnavailableError("all models unavailable")

    patch_provider(responder)
    r = client.post("/ask", json={"question": "a film about boxing", "k": 5})
    assert r.status_code == 503
    assert "temporarily unavailable" in r.json()["detail"].lower()


def test_offtopic_hits_guard_without_calling_llm(client, patch_provider):
    # Genuinely out-of-corpus question -> groundedness guard short-circuits.
    def responder(system, user):
        raise AssertionError("LLM must not be called when the guard fires")

    fake = patch_provider(responder)
    r = client.post("/ask", json={"question": "how do I bake sourdough bread?", "k": 5})
    assert r.status_code == 200
    body = r.json()

    assert body["answer"] == ask_module.IDK_ANSWER
    assert body["citations"] == []
    assert body["used_context"] == []
    assert fake.calls == []                                # provider never invoked
