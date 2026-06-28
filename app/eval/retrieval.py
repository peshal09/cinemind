"""Retrieval-quality + RAG-groundedness checks.

Two numbers for the README / interviews:

1. retrieval hit-rate@k — for a sample of movies, query with the movie's own
   keywords and check the movie itself is in the top-k. A proxy for "does thematic
   retrieval surface the right film?" (no LLM, deterministic).

2. groundedness rate — over a fixed set of in-domain questions, the fraction that
   yield a grounded, cited answer (vs. an "I don't know" / uncited answer). Uses the
   real /ask pipeline (LLM); ungrounded questions are logged.

    python -m app.eval.retrieval
"""

from __future__ import annotations

import time

from sqlalchemy import select

from app.db.database import SessionLocal
from app.embeddings.model import embed_texts
from app.db.models import Movie
from app.rag.ask import (
    SIMILARITY_THRESHOLD,
    SYSTEM_PROMPT,
    _parse_llm_json,
    _retrieve,
    build_context,
    resolve_citations,
)
from app.llm.factory import get_provider

# In-domain questions we expect the corpus to answer.
GROUNDEDNESS_QUESTIONS = [
    "a mind-bending movie about dreams",
    "movies about space battles",
    "a heist thriller",
    "an animated film about toys",
    "a movie about the mafia",
    "a film about boxing",
    "which movie stars Leonardo DiCaprio?",
    "a dystopian science fiction film",
]


def retrieval_hit_rate(sample_size: int = 200, k: int = 10) -> dict:
    with SessionLocal() as db:
        movies = db.execute(
            select(Movie).where(Movie.embedding.is_not(None)).order_by(Movie.id)
        ).scalars().all()
        # keep movies with usable keywords, sample evenly (deterministic)
        usable = [m for m in movies if m.keywords]
        step = max(1, len(usable) // sample_size)
        sample = usable[::step][:sample_size]

        queries = [", ".join(m.keywords) for m in sample]
        vectors = embed_texts(queries)

        hits = 0
        for movie, vec in zip(sample, vectors):
            distance = Movie.embedding.cosine_distance(vec.tolist())
            ids = db.execute(
                select(Movie.id)
                .where(Movie.embedding.is_not(None))
                .order_by(distance)
                .limit(k)
            ).scalars().all()
            if movie.id in ids:
                hits += 1

    return {"metric": f"retrieval hit-rate@{k}", "n": len(sample),
            "hits": hits, "rate": round(hits / len(sample), 4) if sample else 0.0}


def _complete_with_retry(provider, system: str, user: str, attempts: int = 3) -> str:
    """Tolerate transient LLM errors (e.g. 503) so one blip doesn't void the run."""
    for i in range(attempts):
        try:
            return provider.complete(system, user)
        except Exception:
            if i == attempts - 1:
                raise
            time.sleep(2 * (i + 1))
    return ""


def groundedness(k: int = 5) -> dict:
    grounded, ungrounded, errors = 0, [], []
    provider = get_provider()
    with SessionLocal() as db:
        for q in GROUNDEDNESS_QUESTIONS:
            retrieved = _retrieve(db, q, k)
            best = max((s for _, s in retrieved), default=0.0)
            if best < SIMILARITY_THRESHOLD:
                ungrounded.append(q)  # guard fired -> no grounded answer
                continue
            movies = [m for m, _ in retrieved]
            try:
                raw = _complete_with_retry(
                    provider, SYSTEM_PROMPT, f"{build_context(movies)}\n\nQuestion: {q}"
                )
            except Exception as exc:  # transient outage -> exclude from the rate
                errors.append((q, type(exc).__name__))
                continue
            answer, cited = _parse_llm_json(raw)
            if resolve_citations(answer, cited, movies):
                grounded += 1
            else:
                ungrounded.append(q)

    scored = len(GROUNDEDNESS_QUESTIONS) - len(errors)
    return {"metric": "groundedness rate", "n": scored, "grounded": grounded,
            "rate": round(grounded / scored, 4) if scored else 0.0,
            "ungrounded": ungrounded, "errors": errors}


if __name__ == "__main__":
    hr = retrieval_hit_rate()
    print(f"{hr['metric']}: {hr['rate']:.0%}  ({hr['hits']}/{hr['n']})")
    gr = groundedness()
    print(f"{gr['metric']}: {gr['rate']:.0%}  ({gr['grounded']}/{gr['n']} scored)")
    if gr["ungrounded"]:
        print("  ungrounded questions:", gr["ungrounded"])
    if gr["errors"]:
        print("  excluded (transient errors):", gr["errors"])
