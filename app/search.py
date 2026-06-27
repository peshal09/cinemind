"""Semantic search endpoint.

Flow: embed the query with the same all-MiniLM model, pull a candidate pool via
pgvector ANN (cosine, HNSW index), then re-rank by blending the vector score with
a keyword/title-match score so exact-title queries still land on the nose:

    final = (1 - KEYWORD_WEIGHT) * vector_score + KEYWORD_WEIGHT * keyword_score

Tune KEYWORD_WEIGHT toward 0 for "more semantic", toward 1 for "more literal".
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Movie
from app.embeddings.model import embed_texts

router = APIRouter(tags=["search"])

# --- tunable knobs --------------------------------------------------------
KEYWORD_WEIGHT = 0.3          # blend weight for the title keyword match [0, 1]
CANDIDATE_MULTIPLIER = 5      # vector candidates to pull = max(k * this, MIN_POOL)
MIN_CANDIDATE_POOL = 50
# --------------------------------------------------------------------------

# Common words ignored in the title match so they don't inflate the keyword score
# (e.g. "a sci-fi about dreams" shouldn't reward every title containing "a"/"about").
_STOPWORDS = {
    "a", "an", "the", "of", "about", "in", "on", "for", "to", "and", "or",
    "with", "is", "it", "this", "that", "movie", "film",
}


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    k: int = Field(default=10, ge=1, le=100)


def _content_words(text: str) -> set[str]:
    """Meaningful lowercased words: drop stopwords and 4-digit years."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and not re.fullmatch(r"\d{4}", w)}


def _keyword_score(query: str, title: str) -> float:
    """Title-match score in [0, 1], averaging two coverages so an exact title
    (e.g. "Toy Story") beats a superset title (e.g. "Toy Story 3"):

      - query coverage: how many query words appear in the title
      - title coverage: how many (year-stripped) title words are in the query
    """
    q_words = _content_words(query)
    t_words = _content_words(title)
    if not q_words or not t_words:
        return 0.0
    title_lower = title.lower()
    query_cov = sum(1 for w in q_words if w in title_lower) / len(q_words)
    title_cov = sum(1 for w in t_words if w in q_words) / len(t_words)
    return (query_cov + title_cov) / 2


@router.post("/search/semantic")
def semantic_search(body: SearchRequest, db: Session = Depends(get_db)) -> dict:
    query_vec = embed_texts([body.query])[0].tolist()
    pool = max(body.k * CANDIDATE_MULTIPLIER, MIN_CANDIDATE_POOL)

    # ANN candidate retrieval: nearest by cosine distance (uses the HNSW index).
    distance = Movie.embedding.cosine_distance(query_vec)
    rows = db.execute(
        select(Movie.id, Movie.title, distance.label("dist"))
        .where(Movie.embedding.is_not(None))
        .order_by(distance)
        .limit(pool)
    ).all()

    ranked = []
    for movie_id, title, dist in rows:
        vector_score = 1.0 - float(dist)  # cosine distance -> cosine similarity
        keyword_score = _keyword_score(body.query, title)
        score = (1 - KEYWORD_WEIGHT) * vector_score + KEYWORD_WEIGHT * keyword_score
        ranked.append(
            {
                "movie_id": movie_id,
                "title": title,
                "score": round(score, 4),
                "vector_score": round(vector_score, 4),
                "keyword_score": round(keyword_score, 4),
            }
        )

    ranked.sort(key=lambda r: r["score"], reverse=True)
    return {"query": body.query, "k": body.k, "results": ranked[: body.k]}
