"""Rating endpoint: a user rates a movie, which invalidates their cached feed.

Writing a rating changes what we *should* recommend, so the user's cached feeds
are stale the moment they rate. We delete them here; the next /recommend recomputes.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.cache import redis_client
from app.db.database import get_db
from app.db.models import Movie, Rating, User

router = APIRouter(tags=["ratings"])


class RatingRequest(BaseModel):
    movie_id: int
    rating: float = Field(ge=0.5, le=5.0)


class RatingResponse(BaseModel):
    user_id: int
    movie_id: int
    rating: float
    cache_keys_invalidated: int


@router.post("/ratings", response_model=RatingResponse)
def rate_movie(
    body: RatingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RatingResponse:
    if db.get(Movie, body.movie_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown movie_id: {body.movie_id}")

    # Upsert: update the user's existing rating for this movie, or insert one.
    existing = db.scalar(
        select(Rating).where(
            Rating.user_id == current_user.id, Rating.movie_id == body.movie_id
        )
    )
    if existing is not None:
        existing.rating = body.rating
        existing.timestamp = int(time.time())
    else:
        db.add(
            Rating(
                user_id=current_user.id,
                movie_id=body.movie_id,
                rating=body.rating,
                timestamp=int(time.time()),
            )
        )
    db.commit()

    removed = redis_client.invalidate_user(current_user.id)
    return RatingResponse(
        user_id=current_user.id,
        movie_id=body.movie_id,
        rating=body.rating,
        cache_keys_invalidated=removed,
    )
