"""Personalized recommendation rationale: GET /recommendations/{movie_id}/why.

Explains, in a couple of natural sentences, why the logged-in user might enjoy a
given movie — grounded in their actual rating history plus the movie's attributes
(genres, overview, keywords, cast). The LLM is told to reference the user's real
liked movies and not invent anything.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import Movie, Rating, User
from app.llm.base import LLMError
from app.llm.factory import get_provider

router = APIRouter(tags=["recommendations"])

LIKE_THRESHOLD = 4.0
HISTORY_LIMIT = 8

SYSTEM_PROMPT = (
    "You write a short, natural explanation (2-3 sentences) of why a user would "
    "enjoy a movie. Use ONLY the user's liked-movies list and the candidate movie's "
    "attributes provided. Reference specific movies the user liked by name. Be warm "
    "and concise; never invent facts not in the provided data."
)


def _liked_movies(db: Session, user_id: int) -> list[Movie]:
    """The user's highest-rated movies (their taste signal)."""
    rows = db.execute(
        select(Movie)
        .join(Rating, Rating.movie_id == Movie.id)
        .where(Rating.user_id == user_id, Rating.rating >= LIKE_THRESHOLD)
        .order_by(Rating.rating.desc())
        .limit(HISTORY_LIMIT)
    ).scalars().all()
    return rows


@router.get("/recommendations/{movie_id}/why")
def why(
    movie_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail=f"Unknown movie_id: {movie_id}")

    liked = _liked_movies(db, current_user.id)
    if not liked:
        return {
            "movie_id": movie.id,
            "title": movie.title,
            "why": "You haven't rated any movies yet, so I can't personalize this. "
                   "Rate a few films you love and I'll explain your matches.",
            "based_on": [],
        }

    liked_lines = "\n".join(f"- {m.title} ({m.genres.replace('|', ', ')})" for m in liked)
    cast = ", ".join(c.get("name", "") for c in (movie.top_cast or []))
    keywords = ", ".join(movie.keywords or [])
    user_message = (
        f"User's liked movies:\n{liked_lines}\n\n"
        f"Candidate movie:\n"
        f"Title: {movie.title}\n"
        f"Genres: {movie.genres.replace('|', ', ')}\n"
        f"Overview: {movie.overview or 'N/A'}\n"
        f"Keywords: {keywords or 'N/A'}\n"
        f"Cast: {cast or 'N/A'}\n\n"
        f"In 2-3 sentences, explain why this user would enjoy this movie, "
        f"referencing the specific movies they liked."
    )

    try:
        rationale = get_provider().complete(SYSTEM_PROMPT, user_message).strip()
    except LLMError as exc:
        raise HTTPException(
            status_code=503,
            detail="The explanation service is temporarily unavailable. Please try again shortly.",
        ) from exc
    return {
        "movie_id": movie.id,
        "title": movie.title,
        "why": rationale,
        "based_on": [m.title for m in liked],
    }
