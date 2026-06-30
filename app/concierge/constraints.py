"""Shared helpers for the hard constraints the concierge can actually enforce
(year/decade, genre, popularity) — used by both the Retrieval and Critic agents so
the two never drift on what counts as a constraint."""

from __future__ import annotations

from app.concierge.state import Intent


def year_bounds(intent: Intent) -> tuple[int | None, int | None]:
    """Resolve (year_min, year_max) from explicit years or a decade like '1990s'."""
    lo, hi = intent.year_min, intent.year_max
    if intent.decade and not (lo or hi):
        d = intent.decade.strip().rstrip("s")
        if len(d) >= 4 and d[:4].isdigit():
            lo = int(d[:4])
            hi = lo + 9
    return lo, hi


def has_hard_constraint(intent: Intent) -> bool:
    """True if the request carries a constraint we can filter the catalog on."""
    lo, hi = year_bounds(intent)
    return bool(lo or hi or intent.genres or intent.min_popularity is not None)
