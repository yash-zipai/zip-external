"""
ZipAI — Rate (mortgage) Pydantic response schemas.

Two charts, both from signal.mortgage_rate (Freddie Mac PMMS via FRED):
  - 30-year fixed rate over time  (line)
  - 15-year fixed rate over time  (line)
Plus a "current" stat for the Today's Numbers card (latest value + weekly change).
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


# ── Current (Today's Numbers card) ────────────────────────────────────────────


class RateCurrentResponse(BaseModel):
    """Latest weekly rate plus the week-over-week change (for the stat card)."""

    rate_date: date | None = Field(None, description="Survey date of the latest reading (Thursday).")
    rate_30yr: float | None = Field(None, description="Latest 30-year fixed rate (%).")
    rate_15yr: float | None = Field(None, description="Latest 15-year fixed rate (%).")
    change_30yr_wow: float | None = Field(None, description="30-yr change vs the previous week (percentage points).")
    change_15yr_wow: float | None = Field(None, description="15-yr change vs the previous week (percentage points).")
    source: str = Field("FREDDIE_MAC", description="Data source.")


# ── History (feeds both line charts) ──────────────────────────────────────────


class RateHistoryPoint(BaseModel):
    rate_date: date = Field(..., description="Weekly survey date.")
    rate_30yr: float | None = Field(None, description="30-year fixed rate (%).")
    rate_15yr: float | None = Field(None, description="15-year fixed rate (%).")


class RateHistoryResponse(BaseModel):
    """Weekly series. The frontend draws two charts: one from rate_30yr, one from rate_15yr."""

    source: str = Field("FREDDIE_MAC", description="Data source.")
    points: list[RateHistoryPoint] = Field(default_factory=list, description="Weekly points, oldest first.")