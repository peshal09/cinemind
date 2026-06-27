"""Load the MovieLens ml-latest-small dataset.

This module is the single source of truth for reading the dataset. Every
recommender consumes data through these functions, so if the data source ever
changes (a database in Week 2, say) we only touch this file.

The CSV schemas (ml-latest-small):
    movies.csv   : movieId, title, genres        (genres are '|'-separated)
    ratings.csv  : userId, movieId, rating, timestamp
    links.csv    : movieId, imdbId, tmdbId
    tags.csv     : userId, movieId, tag, timestamp
"""

from __future__ import annotations

import io
import zipfile
from functools import lru_cache
from pathlib import Path
from urllib.request import urlopen

import pandas as pd

# data/ lives at the project root, next to app/.
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DATASET_DIR = DATA_DIR / "ml-latest-small"
DATASET_URL = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"


def ensure_dataset() -> Path:
    """Return the dataset directory, downloading it once if it's missing.

    Makes the data layer reproducible: a fresh clone can produce the data
    without any manual curl step.
    """
    if (DATASET_DIR / "ratings.csv").exists():
        return DATASET_DIR

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with urlopen(DATASET_URL) as resp:  # noqa: S310 (trusted, pinned URL)
        payload = resp.read()
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        zf.extractall(DATA_DIR)
    return DATASET_DIR


@lru_cache(maxsize=1)
def load_movies() -> pd.DataFrame:
    """movieId, title, genres(str), genres_list(list[str]) — from the database.

    Aliased back to the MovieLens column names so every recommender keeps working
    unchanged regardless of whether the source is CSV or Postgres.
    """
    from app.db.database import engine

    movies = pd.read_sql(
        "SELECT id AS \"movieId\", title, genres FROM movies ORDER BY id", engine
    )
    # "(no genres listed)" is the dataset's sentinel for "no genres".
    movies["genres_list"] = movies["genres"].apply(
        lambda g: [] if g == "(no genres listed)" else g.split("|")
    )
    return movies


@lru_cache(maxsize=1)
def load_ratings() -> pd.DataFrame:
    """userId, movieId, rating, timestamp — from the database."""
    from app.db.database import engine

    return pd.read_sql(
        'SELECT user_id AS "userId", movie_id AS "movieId", rating, timestamp '
        "FROM ratings",
        engine,
    )


@lru_cache(maxsize=1)
def load_links() -> pd.DataFrame:
    """movieId, imdbId, tmdbId."""
    path = ensure_dataset() / "links.csv"
    return pd.read_csv(path)


@lru_cache(maxsize=1)
def load_tags() -> pd.DataFrame:
    """userId, movieId, tag, timestamp."""
    path = ensure_dataset() / "tags.csv"
    return pd.read_csv(path)


def movie_title(movie_id: int) -> str | None:
    """Convenience lookup used when returning human-readable results."""
    movies = load_movies()
    row = movies.loc[movies["movieId"] == movie_id, "title"]
    return None if row.empty else row.iloc[0]


if __name__ == "__main__":
    # Quick smoke check: `python -m app.data.loader`
    movies = load_movies()
    ratings = load_ratings()
    print(f"movies : {len(movies):>6} rows  | columns: {list(movies.columns)}")
    print(f"ratings: {len(ratings):>6} rows  | columns: {list(ratings.columns)}")
    print(f"users  : {ratings['userId'].nunique():>6} unique")
    print(f"genres : sample -> {movies.loc[0, 'title']} {movies.loc[0, 'genres_list']}")
