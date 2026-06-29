"""Explicit shared state threaded through the concierge agents.

Keeping the flow in one plain object (not hidden globals) is what makes the
pipeline debuggable and explainable — every agent reads from and writes to it, and
the trace is just a list of what each agent did.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Intent:
    """Structured form of the user's request (produced by the Preference agent)."""

    semantic_query: str        # distilled vibe/theme text used for embedding search
    raw_request: str
    genres: list[str] = field(default_factory=list)
    moods: list[str] = field(default_factory=list)
    decade: Optional[str] = None          # e.g. "1990s"
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    min_popularity: Optional[float] = None
    cast: list[str] = field(default_factory=list)
    similar_to: list[str] = field(default_factory=list)
    exclude_seen: bool = True
    # Constraints we understood but can't enforce (no data), e.g. "max_runtime: 120".
    unsupported: list[str] = field(default_factory=list)

    def to_summary(self) -> dict:
        return {
            "semantic_query": self.semantic_query,
            "genres": self.genres,
            "moods": self.moods,
            "decade": self.decade,
            "year_min": self.year_min,
            "year_max": self.year_max,
            "min_popularity": self.min_popularity,
            "cast": self.cast,
            "similar_to": self.similar_to,
            "exclude_seen": self.exclude_seen,
            "unsupported": self.unsupported,
        }


@dataclass
class Candidate:
    movie_id: int
    title: str
    semantic_score: float = 0.0   # cosine similarity to the query [0, 1]
    collab_score: float = 0.0     # recommender score (rating-scale, NOT 0..1)
    source: str = ""              # "semantic" | "collaborative" | "semantic+collaborative" | "popularity"
    score: float = 0.0            # final blended rank score [0, 1] (set by the critic)


@dataclass
class Pick:
    movie_id: int
    title: str
    score: float
    why: str = ""
    based_on: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "movie_id": self.movie_id,
            "title": self.title,
            "score": round(self.score, 4),
            "why": self.why,
            "based_on": self.based_on,
        }


@dataclass
class AgentStep:
    """One entry in the trace: what an agent did, how long it took, and whether it
    succeeded. This is the "show your work" record returned to the caller."""

    name: str
    detail: dict
    ms: float
    ok: bool = True
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "agent": self.name,
            "ms": round(self.ms, 1),
            "ok": self.ok,
            "error": self.error,
            "detail": self.detail,
        }


@dataclass
class ConciergeState:
    request: str
    user_id: int
    k: int = 5
    intent: Optional[Intent] = None
    taste: list[Any] = field(default_factory=list)            # list[Movie] (liked films)
    movies_by_id: dict[int, Any] = field(default_factory=dict)  # id -> Movie (candidate metadata)
    candidates: list[Candidate] = field(default_factory=list)
    shortlist: list[Candidate] = field(default_factory=list)
    results: list[Pick] = field(default_factory=list)
    trace: list[AgentStep] = field(default_factory=list)
