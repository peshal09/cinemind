"""SQLAlchemy ORM models: User, Movie, Rating.

`User` carries auth columns (username / hashed_password) that stay NULL for the
610 MovieLens "data" users seeded in Step 1; Step 2's registration fills them in
for real accounts. Keeping them here now avoids a migration later.
"""

from __future__ import annotations

from typing import List, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import expression

from app.db.database import Base
from app.embeddings.model import EMBEDDING_DIM


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # NULL for seeded MovieLens users; set when a real account registers (Step 2).
    username: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())

    ratings: Mapped[List["Rating"]] = relationship(back_populates="user")


class Movie(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # MovieLens movieId
    title: Mapped[str] = mapped_column(String, nullable=False)
    genres: Mapped[str] = mapped_column(String, nullable=False)  # '|'-separated
    # --- TMDB enrichment (populated by app.enrichment.tmdb) ---
    tmdb_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    overview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    poster_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    popularity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    release_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    keywords = mapped_column(JSONB, nullable=True)            # list[str]
    top_cast = mapped_column(JSONB, nullable=True)            # list[{name, character}]
    # Set once a movie has been processed (success or definitively no data) so the
    # backfill is resumable — NULL means "not yet enriched".
    enriched_at = mapped_column(DateTime(timezone=True), nullable=True)

    # Semantic embedding of title+genres+overview+keywords; NULL until backfilled.
    embedding = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

    ratings: Mapped[List["Rating"]] = relationship(back_populates="movie")


class Rating(Base):
    __tablename__ = "ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), nullable=False)
    rating: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    user: Mapped["User"] = relationship(back_populates="ratings")
    movie: Mapped["Movie"] = relationship(back_populates="ratings")


# Recommenders pull all ratings for a user constantly; index that lookup.
Index("ix_ratings_user_id", Rating.user_id)
Index("ix_ratings_movie_id", Rating.movie_id)
