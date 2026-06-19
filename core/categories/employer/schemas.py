"""
ZipAI — Jobs (Employer) Pydantic response schemas.

Defines the API contract for the jobs endpoints (``/v1/jobs``):
  - Breakdown   (top-5 per-industry employer stats for a zipcode)
  - Index score (aggregated jobs index score for a zipcode)
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Breakdown ─────────────────────────────────────────────────────────────────


class JobsIndustryItem(BaseModel):
    """One industry sector's employer stats within a zipcode."""

    rank: int | None = Field(None, description="Sector rank within the zipcode.")
    sector: str | None = Field(None, description="Industry sector name.")
    naics_code: str | None = Field(None, description="NAICS industry code.")
    establishments_zip: int | None = Field(None, description="Establishments in this zip.")
    share_pct: float | None = Field(None, description="Sector share of the zip (%).")
    employment_county: int | None = Field(
        None, description="County-level employment (total jobs, Census)."
    )
    annual_payroll_k_county: int | None = Field(
        None, description="County-level annual payroll in $1,000s (Census)."
    )
    establishments_county: int | None = Field(None, description="County-level establishments.")


class JobsBreakdownResponse(BaseModel):
    """Response for GET /v1/jobs/zipcode/{zip}/breakdown."""

    zipcode: str = Field(..., description="Queried zipcode.")
    city: str | None = Field(None, description="City name for the zipcode.")
    county_fips: str | None = Field(None, description="County FIPS code (e.g. '06-037').")
    snapshot_year: int | None = Field(None, description="Snapshot reference year.")
    top_5_industries: list[JobsIndustryItem] = Field(
        default_factory=list,
        description="Top 5 industry sectors, ordered by rank ascending.",
    )


# ── Index score ───────────────────────────────────────────────────────────────


class JobsIndexScoreResponse(BaseModel):
    """Response for GET /v1/jobs/zipcode/{zip}/index-scores (zip aggregate)."""

    zipcode: str = Field(..., description="Queried zipcode.")
    city: str | None = Field(None, description="City name for the zipcode.")
    jobs_index_score: int | None = Field(
        None,
        ge=0,
        le=100,
        description="Jobs index score 0–100 (employer diversity / top-sector concentration).",
    )
    top_sector: str | None = Field(None, description="Highest-ranked industry sector name.")
    establishment_count: int = Field(0, description="Total establishments in the zip.")
    snapshot_year: int | None = Field(None, description="Snapshot reference year.")