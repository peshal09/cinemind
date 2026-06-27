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
from app.embeddings.model import build_movie_text, embed_texts


def ensure_hnsw_index() -> None:
    """Create the approximate-NN index (HNSW, cosine) if it doesn't exist.

    This is what makes the similarity search ANN rather than a full scan.
    """
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS movies_embedding_hnsw "
                "ON movies USING hnsw (embedding vector_cosine_ops)"
            )
        )


def backfill(force: bool = False) -> int:
    with SessionLocal() as session:
        query = select(Movie).order_by(Movie.id)
        if not force:
            query = query.where(Movie.embedding.is_(None))
        movies = session.scalars(query).all()

        if movies:
            print(f"Embedding {len(movies)} movies with all-MiniLM-L6-v2...")
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
    return len(movies)


if __name__ == "__main__":
    backfill(force="--force" in sys.argv)
