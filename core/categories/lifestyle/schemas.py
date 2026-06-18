"""
ZipAI — Lifestyle Pydantic response schemas.

Defines the API contract for the lifestyle endpoints:
  - Top places (places by zipcode, optional category filter)
  - Breakdown (per-category averages for a zipcode)
  - Map pins (minimal place pins for maps)
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.pagination import PaginationMeta


# ── Top Places ────────────────────────────────────────────────────────────────


class PlaceDetail(BaseModel):
    """A single lifestyle place with aggregated review data."""

    place_id: int = Field(..., description="Unique place identifier.")
    place_name: str | None = Field(None, description="Business name.")
    category: str | None = Field(None, description="Place category (e.g. entertainment).")
    address: str | None = Field(None, description="Street address.")
    phone: str | None = Field(None, description="Contact phone number.")
    website: str | None = Field(None, description="Website URL.")
    google_maps: str | None = Field(None, description="Google Maps listing URL.")
    rank: int | None = Field(None, description="Rank within category for this zipcode.")
    avg_rating: float | None = Field(None, description="Average review rating (1.00–5.00).")
    review_count: int = Field(0, description="Total number of scraped reviews.")
    latitude: float | None = Field(None, description="Latitude.")
    longitude: float | None = Field(None, description="Longitude.")
    thumbnail_url: str | None = Field(None, description="First image URL (thumbnail).")


class TopPlacesResponse(BaseModel):
    """Response for GET /api/zipcode/{zip}/top-places/."""

    zipcode: str = Field(..., description="Queried zipcode.")
    category_filter: str | None = Field(
        None,
        description="Category filter applied, or null if all categories returned.",
    )
    places: list[PlaceDetail] = Field(
        default_factory=list, description="List of matching places."
    )
    pagination: PaginationMeta = Field(..., description="Pagination metadata.")


# ── Breakdown ─────────────────────────────────────────────────────────────────


class LifestyleBreakdownItem(BaseModel):
    """One category's aggregated lifestyle figures for a zipcode."""

    category: str | None = Field(None, description="Place category.")
    avg_rating: float | None = Field(None, description="Average stored rating.")
    total_places: int = Field(0, description="Distinct places in this category.")
    total_reviews: int = Field(0, description="Total reviews across places.")


class LifestyleBreakdownResponse(BaseModel):
    """Response for GET /api/zipcode/{zip}/location-indices/lifestyle/breakdown/."""

    zipcode: str = Field(..., description="Queried zipcode.")
    city: str | None = Field(None, description="City name for the zipcode.")
    items: list[LifestyleBreakdownItem] = Field(
        default_factory=list,
        description="Per-category breakdown, ordered by average rating desc.",
    )


# ── Map Pins ──────────────────────────────────────────────────────────────────


class MapPin(BaseModel):
    """Minimal lifestyle place pin for map display."""

    place_id: int | None = Field(None, description="Unique place identifier.")
    name: str | None = Field(None, description="Place business name.")
    category: str | None = Field(None, description="Place category (for layer styling).")
    latitude: float = Field(..., description="Latitude (always present).")
    longitude: float = Field(..., description="Longitude (always present).")


class MapPinsResponse(BaseModel):
    """Response for GET /api/map/v1/places/pins/."""

    pins: list[MapPin] = Field(
        default_factory=list,
        description="Place pins that have valid coordinates.",
    )