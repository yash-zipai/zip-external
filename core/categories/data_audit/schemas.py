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
class CompletenessStat(BaseModel):
    total: int
    missing: int
    missing_pct: float


class DuplicateRow(BaseModel):
    zipcode: str
    provider_name: str
    dupes: int


class DataQualityResponse(BaseModel):
    crime_missing_rate: CompletenessStat
    healthcare_missing_rating: CompletenessStat
    healthcare_duplicates: List[DuplicateRow]