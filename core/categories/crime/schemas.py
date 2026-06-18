"""
ZipAI — Crime Pydantic response schemas.

Defines the API contract for the crime endpoints:
  - Crime summary  (per-year totals + violent/property split for a zipcode)
  - Crime breakdown (per crime-type detail for the most recent year)
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────


class CrimeClass(str, Enum):
    """Broad classification of a crime type (the classes the summary splits on)."""

    VIOLENT = "violent"
    PROPERTY = "property"


# ── Crime Summary ─────────────────────────────────────────────────────────────


class CrimeSummaryYear(BaseModel):
    """Aggregated crime figures for a single year in a zipcode."""

    year: int = Field(..., description="Calendar year of the figures.")
    city: str | None = Field(None, description="City name for the zipcode.")
    total_crimes: int = Field(0, description="Total incidents across all classes.")
    crime_rate_index: float | None = Field(
        None, description="Sum of per-type rates across all classes."
    )
    violent_count: int = Field(0, description="Total violent-crime incidents.")
    violent_rate: float | None = Field(None, description="Sum of violent-crime rates.")
    property_count: int = Field(0, description="Total property-crime incidents.")
    property_rate: float | None = Field(None, description="Sum of property-crime rates.")


class CrimeSummaryResponse(BaseModel):
    """Response for GET /v1/zipinsights/{zip} (crime summary)."""

    zipcode: str = Field(..., description="Queried zipcode.")
    years: list[CrimeSummaryYear] = Field(
        default_factory=list,
        description="Per-year crime summary, ordered by year ascending.",
    )


# ── Crime Breakdown ───────────────────────────────────────────────────────────


class CrimeBreakdownItem(BaseModel):
    """A single crime type's figures for the most recent year."""

    crime_type: str = Field(..., description="Specific crime type.")
    crime_class: str | None = Field(
        None, description="Broad class (e.g. violent, property)."
    )
    actual_count: int = Field(0, description="Number of incidents.")
    rate: float | None = Field(None, description="Incident rate for this crime type.")


class CrimeBreakdownResponse(BaseModel):
    """Response for GET /v1/zipcode/{zip}/location-indices/crime/breakdown."""

    zipcode: str = Field(..., description="Queried zipcode.")
    year: int | None = Field(
        None, description="Year the breakdown covers (most recent available)."
    )
    items: list[CrimeBreakdownItem] = Field(
        default_factory=list,
        description="Per crime-type breakdown, ordered by rate descending.",
    )