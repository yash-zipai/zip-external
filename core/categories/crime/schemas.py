"""
ZipAI — Crime Pydantic response schemas.

Defines the API contract for the crime endpoints (new scheme):
  - Index scores (ZIP aggregate + 0–100 crime index, safety %, level)
  - Breakdown   (summary + top 5 offenses + year-over-year trend)
  - Insights    (monthly crime-rate series for the listing chart)

Save as: core/categories/crime/schemas.py
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────


class CrimeLevel(str, Enum):
    """Safety band derived from the safety percentage."""

    VERY_LOW = "Very Low"   # >= 80
    LOW = "Low"             # 60–79
    MODERATE = "Moderate"   # 40–59
    HIGH = "High"           # < 40


class TrendDirection(str, Enum):
    """Direction of the year-over-year change."""

    INCREASE = "increase"
    DECREASE = "decrease"
    FLAT = "flat"


# ── Index Scores ──────────────────────────────────────────────────────────────


class CrimeIndexScoresResponse(BaseModel):
    """Response for GET /v1/crime/zipcode/{zip}/index-scores."""

    zipcode: str = Field(..., description="Queried zipcode.")
    city: str | None = Field(None, description="City name for the zipcode.")
    crime_index: float | None = Field(
        None, description="Crime index, 0–100 (lower = more crime / worse safety)."
    )
    level: CrimeLevel | None = Field(
        None, description="Safety band: Very Low | Low | Moderate | High."
    )
    violent_total: int = Field(0, description="Violent incidents (latest year).")
    property_total: int = Field(0, description="Property incidents (latest year).")
    safety_pct: float | None = Field(None, description="Safety percentage (0–100).")
    as_of: date | None = Field(None, description="Data reference date.")


# ── Breakdown ─────────────────────────────────────────────────────────────────


class CrimeTopOffense(BaseModel):
    """A single top offense within a zipcode."""

    crime_type: str = Field(..., description="Offense type (e.g. larceny).")
    total_count: int = Field(0, description="Total incidents of this type.")
    crime_rank: int | None = Field(None, description="Rank by count (1 = highest).")
    avg_rate: float | None = Field(None, description="Average rate for this offense.")


class CrimeTrend(BaseModel):
    """Year-over-year trend block."""

    latest_year: int | None = Field(None, description="Most recent year present.")
    latest_total: int = Field(0, description="Total incidents in the latest year.")
    prev_year: int | None = Field(None, description="Previous year present.")
    prev_total: int = Field(0, description="Total incidents in the previous year.")
    yoy_pct: float | None = Field(
        None, description="Year-over-year percentage change (signed)."
    )
    trend_direction: TrendDirection | None = Field(
        None, description="increase | decrease | flat."
    )


class CrimeBreakdownResponse(BaseModel):
    """Response for GET /v1/crime/zipcode/{zip}/breakdown."""

    zipcode: str = Field(..., description="Queried zipcode.")
    crime_index: float | None = Field(None, description="Crime index for the latest year.")
    violent_total: int = Field(0, description="Violent incidents (latest year).")
    property_total: int = Field(0, description="Property incidents (latest year).")
    top_offenses: list[CrimeTopOffense] = Field(
        default_factory=list, description="Top 5 offenses by count."
    )
    trend: CrimeTrend | None = Field(None, description="Year-over-year trend.")


# ── Insights ──────────────────────────────────────────────────────────────────


class CrimeMonthPoint(BaseModel):
    """One point in the monthly crime-rate series."""

    month: str = Field(..., description="Month label, 'YYYY-MM'.")
    value: int = Field(0, description="Crime count/value for the month.")


class CrimeRateSeries(BaseModel):
    """Monthly series wrapper for the listing chart."""

    monthly_series: list[CrimeMonthPoint] = Field(
        default_factory=list, description="Last N months, oldest first."
    )
    as_of: date | None = Field(None, description="Data reference date.")


class CrimeInsightsResponse(BaseModel):
    """Response for GET /v1/crime/zipcode/{zip}/insights."""

    zipcode: str = Field(..., description="Queried zipcode.")
    crime_rate: CrimeRateSeries = Field(..., description="Monthly crime-rate series.")
    mock: bool = Field(False, description="True if the series is mock/placeholder data.")