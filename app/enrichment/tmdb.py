"""Enrich movies with TMDB metadata.

For each movie we map movieId -> tmdbId (from links.csv) and fetch overview,
keywords, top cast, poster_path, popularity, and release_date in a single TMDB
call (append_to_response=keywords,credits).

Idempotent & resumable: only movies with enriched_at IS NULL are processed, and
each batch is committed before the next, so an interrupted run continues where it
left off. Transient failures (network, 429, 5xx) are retried and, if still
failing, left unmarked for a later run. Requests run concurrently with a
semaphore; HTTP 429 is honored via Retry-After.

    python -m app.enrichment.tmdb            # fill missing
    python -m app.enrichment.tmdb --force    # re-enrich everything

Data provided by TMDB (themoviedb.org); attribution belongs in the README.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone

import httpx
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import select

from app.data import loader
from app.db.database import SessionLocal
from app.db.models import Movie

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"
CONCURRENCY = 32
BATCH_SIZE = 200
TOP_CAST = 10
MAX_RETRIES = 5


def _links_map() -> dict[int, int]:
    """movieId -> tmdbId from links.csv (rows without a tmdbId are dropped)."""
    links = pd.read_csv(loader.ensure_dataset() / "links.csv")
    links = links.dropna(subset=["tmdbId"])
    return {int(r.movieId): int(r.tmdbId) for r in links.itertuples()}


def _parse(data: dict) -> dict:
    keywords = [k["name"] for k in data.get("keywords", {}).get("keywords", [])]
    cast = [
        {"name": c.get("name"), "character": c.get("character", "")}
        for c in data.get("credits", {}).get("cast", [])[:TOP_CAST]
    ]
    return {
        "overview": data.get("overview") or None,
        "poster_path": data.get("poster_path"),
        "popularity": data.get("popularity"),
        "release_date": data.get("release_date") or None,
        "keywords": keywords,
        "top_cast": cast,
    }


async def _fetch(client, sem, tmdb_id):
    """Return (status, payload). status: ok|notfound|error|fail."""
    url = f"{BASE_URL}/movie/{tmdb_id}"
    params = {"api_key": TMDB_API_KEY, "append_to_response": "keywords,credits"}
    async with sem:
        for attempt in range(MAX_RETRIES):
            try:
                r = await client.get(url, params=params, timeout=30)
            except httpx.HTTPError:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            if r.status_code == 200:
                return ("ok", r.json())
            if r.status_code == 404:
                return ("notfound", None)
            if r.status_code == 401:
                return ("error", 401)  # bad API key -> abort upstream
            if r.status_code == 429:
                await asyncio.sleep(float(r.headers.get("Retry-After", "1")) + 0.5)
                continue
            if r.status_code >= 500:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            return ("error", r.status_code)
        return ("fail", None)


async def _fetch_many(pairs):
    sem = asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*[_fetch(client, sem, tid) for _, tid in pairs])
    return {mid: res for (mid, _), res in zip(pairs, results)}


def enrich(force: bool = False) -> int:
    if not TMDB_API_KEY:
        raise SystemExit("TMDB_API_KEY is not set (.env).")

    links = _links_map()
    with SessionLocal() as session:
        query = select(Movie.id).order_by(Movie.id)
        if not force:
            query = query.where(Movie.enriched_at.is_(None))
        todo = [mid for (mid,) in session.execute(query).all()]

    total = len(todo)
    if total == 0:
        print("Nothing to enrich.")
        return 0

    print(f"Enriching {total} movies from TMDB (concurrency={CONCURRENCY})...")
    fetched = nomap = notfound = retry_later = 0

    for start in range(0, total, BATCH_SIZE):
        chunk = todo[start : start + BATCH_SIZE]
        to_fetch = [(mid, links[mid]) for mid in chunk if mid in links]
        results = asyncio.run(_fetch_many(to_fetch)) if to_fetch else {}
        now = datetime.now(timezone.utc)

        with SessionLocal() as session:
            for mid in chunk:
                movie = session.get(Movie, mid)
                if mid not in links:
                    movie.keywords, movie.top_cast = [], []
                    movie.enriched_at = now
                    nomap += 1
                    continue
                status, payload = results.get(mid, ("fail", None))
                if status == "ok":
                    for field, value in _parse(payload).items():
                        setattr(movie, field, value)
                    movie.tmdb_id = links[mid]
                    movie.enriched_at = now
                    fetched += 1
                elif status == "notfound":
                    movie.keywords, movie.top_cast = [], []
                    movie.enriched_at = now
                    notfound += 1
                elif status == "error":
                    raise SystemExit(
                        f"TMDB returned HTTP {payload}; aborting (check TMDB_API_KEY)."
                    )
                else:
                    retry_later += 1  # leave enriched_at NULL for a future run
            session.commit()

        done = min(start + BATCH_SIZE, total)
        print(
            f"[enrich] {done}/{total}  fetched={fetched} no_tmdb={nomap} "
            f"notfound={notfound} retry_later={retry_later}",
            flush=True,
        )

    print("Done.")
    return fetched


if __name__ == "__main__":
    enrich(force="--force" in sys.argv)
