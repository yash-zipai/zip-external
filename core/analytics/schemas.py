"""
ZipAI — Analytics (click/view tracking) Pydantic response schemas.
"""
from __future__ import annotations
from pydantic import BaseModel, Field


# ── Ingest (frontend -> API) ──────────────────────────────────────────────────
class TrackIn(BaseModel):
    """One click/view event coming from the frontend."""
    metric_key: str = Field(..., description="What was clicked, e.g. 'house:123', 'zip:94306', 'permits', 'mlo', 'index:lifestyle'.")
    user_id: str | None = Field(None, description="Logged-in user id, if any.")
    session_id: str | None = Field(None, description="Anonymous browser session id.")
    url: str | None = Field(None, description="Page URL where the event happened.")


class TrackAck(BaseModel):
    """Simple acknowledgement returned instantly to the frontend."""
    ok: bool = True


# ── Read (API -> frontend) ────────────────────────────────────────────────────
class ClickStatsResponse(BaseModel):
    """Aggregated counts for a single metric_key."""
    metric_key: str
    total_clicks: int = Field(0, description="Every click (one person clicking 5x = 5).")
    unique_people: int = Field(0, description="Distinct users/sessions of all time.")
    this_month_people: int = Field(0, description="Distinct users/sessions this calendar month.")
