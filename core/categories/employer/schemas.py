"""
ZipAI — Jobs (Employer) Pydantic response schemas.

Defines the API contract for the jobs endpoints:
  - Breakdown (per-industry employer stats for a zipcode)
  - Score     (aggregated job-market score for a zipcode)
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Breakdown ─────────────────────────────────────────────────────────────────


class JobsIndustryItem(BaseModel):
    """One industry sector's employer stats within a zipcode."""

    rank: int | None = Field(None, description="Sector rank within the zipcode.")
    naics_code: str | None = Field(None, description="NAICS industry code.")
    sector_name: str | None = Field(None, description="Industry sector name.")
    establishments_zip: int | None = Field(None, description="Establishments in this zip.")
    share_pct: float | None = Field(None, description="Sector share of the zip (%).")
    employment_zip_suppressed: int | None = Field(
        None, description="Zip-level employment (may be suppressed → null)."
    )
    payroll_k_zip_suppressed: int | None = Field(
        None, description="Zip-level payroll in $1,000s (may be suppressed → null)."
    )
    employment_county: int | None = Field(None, description="County-level employment.")
    payroll_k_county: int | None = Field(None, description="County-level payroll in $1,000s.")
    establishments_county: int | None = Field(None, description="County-level establishments.")


class JobsBreakdownResponse(BaseModel):
    """Response for GET /api/zipcode/{zip}/location-indices/jobs/breakdown/."""

    zipcode: str = Field(..., description="Queried zipcode.")
    city: str | None = Field(None, description="City name for the zipcode.")
    latitude: float | None = Field(None, description="Zip snapshot latitude.")
    longitude: float | None = Field(None, description="Zip snapshot longitude.")
    items: list[JobsIndustryItem] = Field(
        default_factory=list,
        description="Per-industry breakdown, ordered by rank ascending.",
    )


# ── Score ─────────────────────────────────────────────────────────────────────


class JobsScoreResponse(BaseModel):
    """Response for GET /api/zipcode/{zip}/location-indices/jobs/ (aggregate score)."""

    zipcode: str = Field(..., description="Queried zipcode.")
    city: str | None = Field(None, description="City name for the zipcode.")
    job_market_score: float | None = Field(
        None, description="Job-market score (sum of sector share %)."
    )
    sector_count: int = Field(0, description="Number of industry sectors.")
    total_establishments: int = Field(0, description="Total establishments across sectors.")