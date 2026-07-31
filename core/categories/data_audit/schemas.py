"""
Data Audit — Pydantic response models.

Mirrors the ai_admin module: one Response model per endpoint, each wrapping a
list of typed item rows (plus an echoed `days` where the endpoint is windowed).
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


# ── 1) Ingestion activity ─────────────────────────────────────────────────────
class IngestionDayCount(BaseModel):
    day: str
    category: str
    ingested: int


class IngestionActivityResponse(BaseModel):
    days: int
    items: List[IngestionDayCount]


# ── 2) Freshness ──────────────────────────────────────────────────────────────
class FreshnessRow(BaseModel):
    dataset: str
    last_ingested: Optional[str] = None
    latest_period: Optional[str] = None
    is_stale: bool


class FreshnessResponse(BaseModel):
    stale_after_days: int
    items: List[FreshnessRow]


# ── 3) Record counts ──────────────────────────────────────────────────────────
class RecordCountRow(BaseModel):
    category: str
    rows: int


class RecordCountsResponse(BaseModel):
    total_rows: int
    items: List[RecordCountRow]


# ── 4) Coverage ───────────────────────────────────────────────────────────────
class CoverageRow(BaseModel):
    category: str
    zipcodes_covered: int


class CoverageResponse(BaseModel):
    items: List[CoverageRow]


# ── 5) Coverage gaps (category-aware) ─────────────────────────────────────────
class CoverageGapRow(BaseModel):
    category: str
    zipcode: str
    searches: int
    users: int


class CoverageGapsResponse(BaseModel):
    days: int
    category: Optional[str] = None  # echoes the filter, null = all categories
    items: List[CoverageGapRow]


# ── 6) Data quality ───────────────────────────────────────────────────────────
class CompletenessRow(BaseModel):
    category: str
    field_checked: str   # which field we measured (rate / rating / zipcode)
    total: int
    missing: int
    missing_pct: float


class DataQualityResponse(BaseModel):
    items: List[CompletenessRow]


# ── 7) New property listings (MLS / IDX) ──────────────────────────────────────
class NewListingItem(BaseModel):
    listing_key_numeric: str
    listing_id: Optional[str] = None
    standard_status: Optional[str] = None
 
    # address / location (display uses the compliance-filtered address)
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
 
    # core facts
    list_price: Optional[float] = None
    bedrooms: Optional[float] = None
    bathrooms: Optional[float] = None
    living_area: Optional[float] = None
    property_class: Optional[str] = None
    is_lease_listing: bool = False
 
    # attribution
    listing_office_name: Optional[str] = None
    listing_member_name: Optional[str] = None
 
    # rich RESO fields pulled from source_payload JSONB
    property_type: Optional[str] = None
    year_built: Optional[str] = None
    lot_size_acres: Optional[str] = None
 
    # when it entered our system (the "new listing" signal)
    listed_at: Optional[str] = None
 
 
class NewListingsResponse(BaseModel):
    days: int
    returned: int          # rows in this page
    limit: int
    offset: int
    items: List[NewListingItem]
 
 
class StatusCount(BaseModel):
    standard_status: str
    listings: int
 
 
class CityCount(BaseModel):
    city: str
    listings: int
 
 
class NewListingsSummaryResponse(BaseModel):
    days: int
    total_new_listings: int
    for_sale: int
    for_lease: int
    zipcodes_covered: int
    by_status: List[StatusCount]
    top_cities: List[CityCount]