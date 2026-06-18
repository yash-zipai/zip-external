"""
ZipAI — Healthcare Pydantic response schemas.

Defines the API contract for all healthcare endpoints:
  - Top places (providers by zipcode)
  - Breakdown (bucketed category scores)
  - Healthcare index (per-zipcode composite score)
  - Map pins (minimal provider pins for maps)
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from core.pagination import PaginationMeta


# ── Enums ─────────────────────────────────────────────────────────────────────


class HealthcareCategory(str, Enum):
    """Valid provider categories in the healthcare schema."""

    HOSPITALS = "hospitals"
    URGENT_CARE = "urgent_care"
    PEDIATRICS = "pediatrics"
    DENTISTS = "dentists"
    CLINICS = "clinics"
    PHARMACIES = "pharmacies"
    MENTAL_HEALTH = "mental_health"


# ── Top Places ────────────────────────────────────────────────────────────────


class ProviderDetail(BaseModel):
    """A single healthcare provider with aggregated review data."""

    provider_id: int = Field(..., description="Unique provider identifier.")
    provider_name: str | None = Field(None, description="Business name.")
    category: str | None = Field(None, description="Provider category (e.g. hospitals, dentists).")
    address: str | None = Field(None, description="Street address.")
    phone: str | None = Field(None, description="Contact phone number.")
    website: str | None = Field(None, description="Website URL.")
    google_maps: str | None = Field(None, description="Google Maps listing URL.")
    rank: int | None = Field(None, description="Rank within category for this zipcode.")
    avg_rating: float | None = Field(None, description="Average review rating (1.00–5.00).")
    review_count: int = Field(0, description="Total number of scraped reviews.")
    thumbnail_url: str | None = Field(None, description="First image URL (thumbnail).")


class TopPlacesResponse(BaseModel):
    """Response for GET /v1/healthcare/zipcode/{zip}/top-places."""

    zipcode: str = Field(..., description="Queried zipcode.")
    category_filter: str | None = Field(
        None,
        description="Category filter applied, or null if all categories returned.",
    )
    providers: list[ProviderDetail] = Field(
        default_factory=list, description="List of matching providers."
    )
    pagination: PaginationMeta = Field(..., description="Pagination metadata.")


# ── Breakdown ─────────────────────────────────────────────────────────────────


class BreakdownBucket(BaseModel):
    """
    One aggregated bucket in the healthcare breakdown.

    Buckets map raw categories to broader groups:
      hospitals + urgent_care  → hospital_urgent
      dentists                 → dental
      pediatrics               → pediatrics
      clinics + pharmacies     → primary_care
    """

    bucket: str = Field(..., description="Aggregated bucket name.")
    provider_count: int = Field(0, description="Distinct providers in this bucket.")
    avg_rating: float | None = Field(None, description="Average review rating.")
    total_reviews: int = Field(0, description="Total reviews across providers.")
    score: float | None = Field(
        None,
        description="Composite score: avg_rating × ln(review_count).",
    )


class BreakdownResponse(BaseModel):
    """Response for GET /v1/healthcare/zipcode/{zip}/breakdown."""

    zipcode: str = Field(..., description="Queried zipcode.")
    buckets: list[BreakdownBucket] = Field(
        default_factory=list, description="Breakdown by healthcare bucket."
    )


# ── Healthcare Index ──────────────────────────────────────────────────────────


class HealthcareIndexEntry(BaseModel):
    """One zipcode's composite healthcare index score."""

    zipcode: str = Field(..., description="US zipcode.")
    city: str | None = Field(None, description="City name.")
    total_providers: int = Field(0, description="Distinct providers in this zip.")
    overall_avg_rating: float | None = Field(None, description="Average rating across all providers.")
    total_reviews: int = Field(0, description="Total reviews across all providers.")
    healthcare_index_score: float | None = Field(
        None,
        description="Composite index: avg_rating × ln(total_reviews).",
    )


class HealthcareIndexResponse(BaseModel):
    """Response for GET /v1/healthcare/index-scores."""

    zipcode_filter: str | None = Field(
        None,
        description="Zipcode filter applied, or null if all zipcodes returned.",
    )
    entries: list[HealthcareIndexEntry] = Field(
        default_factory=list, description="Index score entries."
    )
    pagination: PaginationMeta = Field(..., description="Pagination metadata.")


# ── Map Pins ──────────────────────────────────────────────────────────────────


class MapPin(BaseModel):
    """Minimal healthcare provider pin for map display."""

    name: str | None = Field(None, description="Provider business name.")
    latitude: float = Field(..., description="Latitude (always present).")
    longitude: float = Field(..., description="Longitude (always present).")
    avg_rating: float | None = Field(None, description="Average rating (1.00–5.00).")
    thumbnail_url: str | None = Field(
        None,
        description=(
            "Thumbnail image URL. Currently always null — the "
            "healthcare_provider table has no image/thumbnail column yet."
        ),
    )


class MapPinsResponse(BaseModel):
    """Response for GET /v1/healthcare/places/pins/."""

    pins: list[MapPin] = Field(
        default_factory=list,
        description="Provider pins that have valid coordinates.",
    )