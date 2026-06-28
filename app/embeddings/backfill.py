"""Backfill semantic embeddings for movies.

Idempotent: by default only embeds rows whose `embedding` is NULL, so it's safe
to re-run (e.g. after adding new movies). `--force` re-embeds everything.

    python -m app.embeddings.backfill          # fill missing
    python -m app.embeddings.backfill --force  # recompute all
"""

from __future__ import annotations

import sys

from sqlalchemy import select, text

from app.db.database import SessionLocal, engine
from app.db.models import Movie
from app.embeddings.model import MODEL_NAME, build_movie_text, embed_texts


def ensure_hnsw_index() -> None:
    """Create the approximate-NN index (HNSW, cosine) if it doesn't exist.

    This is what makes the similarity search ANN rather than a full scan.

    Also raise hnsw.ef_search (default 40 -> 200) as a database-level default so
    every connection gets it: at 40 the ANN search misses some true neighbors
    (hit-rate@10 ~72% vs ~77% exact); 200 closes that gap with negligible latency
    at this corpus size.
    """
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS movies_embedding_hnsw "
                "ON movies USING hnsw (embedding vector_cosine_ops)"
            )
        )
        db_name = conn.execute(text("SELECT current_database()")).scalar()
        conn.execute(text(f'ALTER DATABASE "{db_name}" SET hnsw.ef_search = 200'))


def backfill(force: bool = False) -> int:
    with SessionLocal() as session:
        query = select(Movie).order_by(Movie.id)
        if not force:
            query = query.where(Movie.embedding.is_(None))
        movies = session.scalars(query).all()

        if movies:
            print(f"Embedding {len(movies)} movies with {MODEL_NAME}...")
            texts = [
                build_movie_text(
                    m.title, m.genres, m.overview, m.keywords,
                    [c.get("name") for c in (m.top_cast or []) if c.get("name")],
                )
                for m in movies
            ]
            vectors = embed_texts(texts)
            for movie, vector in zip(movies, vectors):
                movie.embedding = vector.tolist()
            session.commit()
            print(f"Stored {len(movies)} embeddings.")
        else:
            print("All movies already embedded; nothing to do.")

    # Always ensure the ANN index exists (idempotent).
    ensure_hnsw_index()
    print("HNSW index ready.")

    # Retrieval just changed, so any cached /ask answers may now be stale.
    if movies:
        from app.cache import redis_client

        removed = redis_client.invalidate_ask()
        print(f"Invalidated {removed} cached /ask answer(s).")

    return len(movies)


if __name__ == "__main__":
    backfill(force="--force" in sys.argv)
