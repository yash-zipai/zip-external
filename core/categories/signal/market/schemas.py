"""
ZipAI — Market (MLS) response schemas — SLIM build.

Only the models for the 5 dashboard graphs + the two drill-down feeds
(price-cuts, listings) + the low-confidence accuracy flag.
"""
from __future__ import annotations

from datetime import date
from pydantic import BaseModel, Field


class MarketScopeEcho(BaseModel):
    area_level: str
    area_code: str
    property_type: str | None = None


# ── Graph 1 · Prices ──────────────────────────────────────────────────────────
class HomePriceTrendPoint(BaseModel):
    month: date
    median_sale_price: float | None = None
    sample_size: int = 0
    low_confidence: bool = False          # True when sample_size < 5


class HomePriceTrendResponse(BaseModel):
    scope: MarketScopeEcho
    points: list[HomePriceTrendPoint] = Field(default_factory=list)


class ValuePerSqftPoint(BaseModel):
    month: date
    median_ppsf: float | None = None
    sample_size: int = 0
    low_confidence: bool = False


class ValuePerSqftResponse(BaseModel):
    scope: MarketScopeEcho
    points: list[ValuePerSqftPoint] = Field(default_factory=list)


# ── Graph 2 · Negotiating room ────────────────────────────────────────────────
class PriceDropPressurePoint(BaseModel):
    month: date
    price_drops: int = 0
    new_listings: int = 0
    drops_per_100_new: float | None = None


class PriceDropPressureResponse(BaseModel):
    scope: MarketScopeEcho
    points: list[PriceDropPressurePoint] = Field(default_factory=list)


# drill-down: the individual cuts
class PriceCutRow(BaseModel):
    event_date: date
    listing_key_numeric: str
    address: str | None = None
    city: str | None = None
    zip_code: str | None = None
    prior_price: float | None = None
    price: float | None = None
    cut_amount: float | None = None
    cut_pct: float | None = None


class PriceCutsResponse(BaseModel):
    scope: MarketScopeEcho
    on_date: date | None = None
    year: int | None = None
    month: int | None = None
    count: int = 0
    rows: list[PriceCutRow] = Field(default_factory=list)


# ── Graph 3 · Supply & demand ─────────────────────────────────────────────────
class FreshSupplyPoint(BaseModel):
    month: date
    property_type: str
    new_listings: int = 0


class FreshSupplyResponse(BaseModel):
    scope: MarketScopeEcho
    points: list[FreshSupplyPoint] = Field(default_factory=list)


class HomesSoldPoint(BaseModel):
    month: date
    closed_sales: int = 0


class HomesSoldResponse(BaseModel):
    scope: MarketScopeEcho
    points: list[HomesSoldPoint] = Field(default_factory=list)


# ── Graph 4 · What is available ───────────────────────────────────────────────
class InventoryPoint(BaseModel):
    month: date
    active_listings: int = 0
    in_contract: int = 0


class InventoryResponse(BaseModel):
    scope: MarketScopeEcho
    points: list[InventoryPoint] = Field(default_factory=list)


# ── Graph 5 · How fast homes sell ─────────────────────────────────────────────
class SpeedToSellPoint(BaseModel):
    month: date
    property_type: str
    median_dom: float | None = None
    sample_size: int = 0
    low_confidence: bool = False


class SpeedToSellResponse(BaseModel):
    scope: MarketScopeEcho
    points: list[SpeedToSellPoint] = Field(default_factory=list)


# ── Shared drill-down: individual listings (any card's "See listings ->") ──────
class ListingRow(BaseModel):
    listing_key_numeric: str
    address: str | None = None
    city: str | None = None
    zip_code: str | None = None
    list_price: float | None = None
    sale_price: float | None = None
    beds: float | None = None
    baths: float | None = None
    sqft: float | None = None
    status: str | None = None
    dom: int | None = None
    list_date: date | None = None
    close_date: date | None = None


class ListingsResponse(BaseModel):
    scope: MarketScopeEcho
    status: str
    count: int = 0
    rows: list[ListingRow] = Field(default_factory=list)