"""POST /concierge — the multi-agent film concierge endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.concierge.orchestrator import run_concierge
from app.db.database import get_db
from app.db.models import User

router = APIRouter(tags=["concierge"])


class ConciergeRequest(BaseModel):
    request: str = Field(min_length=1)
    k: int = Field(default=5, ge=1, le=20)


@router.post("/concierge")
def concierge(
    body: ConciergeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Turn a natural-language request into a ranked, explained shortlist via the
    4-agent pipeline. Returns the picks plus a per-agent trace; falls back to the
    Phase-3 recommender if any agent fails."""
    return run_concierge(body.request, current_user.id, db, k=body.k)
