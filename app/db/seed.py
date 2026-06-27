"""Create tables and load the MovieLens dataset into PostgreSQL.

Run once (or whenever you want a clean DB):

    python -m app.db.seed

It drops and recreates all tables, then bulk-loads movies, ratings, and one
`users` row per distinct MovieLens userId (auth columns left NULL for now).
"""

from __future__ import annotations

import sys

import pandas as pd
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text

from app.data import loader
from app.db import models  # noqa: F401  (import registers tables on Base)
from app.db.database import Base, engine


def is_seeded() -> bool:
    """True if the movies table exists and has rows."""
    if not sa_inspect(engine).has_table("movies"):
        return False
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM movies")).scalar()
    return bool(count)


def seed(force: bool = False) -> None:
    # Idempotent by default so the container entrypoint can call it on every
    # start without reloading data; `force=True` does a full reset.
    if not force and is_seeded():
        print("Database already seeded; skipping. (use --force to reload)")
        return

    print("Enabling pgvector extension...")
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    print("Dropping and recreating tables...")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    dataset = loader.ensure_dataset()
    movies = pd.read_csv(dataset / "movies.csv")   # movieId, title, genres
    ratings = pd.read_csv(dataset / "ratings.csv")  # userId, movieId, rating, timestamp

    users_df = pd.DataFrame({"id": sorted(ratings["userId"].unique())})
    movies_df = movies.rename(columns={"movieId": "id"})[["id", "title", "genres"]]
    ratings_df = ratings.rename(
        columns={"userId": "user_id", "movieId": "movie_id"}
    )[["user_id", "movie_id", "rating", "timestamp"]]

    with engine.begin() as conn:
        print(f"Loading {len(users_df)} users...")
        users_df.to_sql("users", conn, if_exists="append", index=False)
        print(f"Loading {len(movies_df)} movies...")
        movies_df.to_sql("movies", conn, if_exists="append", index=False)
        print(f"Loading {len(ratings_df)} ratings...")
        # chunksize keeps multi-row INSERTs under psycopg2's parameter limit
        # (4 cols * 5000 = 20000 < 32767).
        ratings_df.to_sql(
            "ratings", conn, if_exists="append", index=False,
            chunksize=5000, method="multi",
        )

        # We inserted explicit ids, so the auto-increment sequences are still at
        # their start. Advance them past MAX(id) or the next INSERT (e.g. a user
        # registering) would collide with an existing id.
        for table in ("users", "movies", "ratings"):
            conn.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                    f"(SELECT MAX(id) FROM {table}))"
                )
            )

    print("Done.")


if __name__ == "__main__":
    seed(force="--force" in sys.argv)
