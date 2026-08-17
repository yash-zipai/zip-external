"""
ZipAI — Market (MLS) Pydantic response schemas.

Defines the API contract for the market-analysis endpoints. Every chart is
scoped to an area (county | city | zip) and, where relevant, a property type
(SF | CONDO | ...). Series endpoints return one point per month; ranking and
summary endpoints return one item per city.

Source data: signal.listing_fact (+ public.zipdata_idxlistingpriceevent).
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


# ── Shared scope echo ─────────────────────────────────────────────────────────


class MarketScopeEcho(BaseModel):
    """The area/type the response was computed for (echoed back to the client)."""

    area_level: str = Field(..., description="Area granularity: county | city | zip.")
    area_code: str = Field(..., description="Area value, e.g. 'San Mateo' or '94103'.")
    property_type: str | None = Field(
        None, description="Property type filter applied, or null when the chart returns all types."
    )


# ── 1. Median sale price over time ────────────────────────────────────────────


class MedianSalePricePoint(BaseModel):
    month: date = Field(..., description="First day of the month.")
    median_sale_price: float | None = Field(None, description="Median closed sale price.")
    closed_sales: int = Field(0, description="Number of closed sales that month.")


class MedianSalePriceResponse(BaseModel):
    scope: MarketScopeEcho
    points: list[MedianSalePricePoint] = Field(default_factory=list)


# ── 2. Median price YoY % (SF vs Condo) ───────────────────────────────────────


class YoyPoint(BaseModel):
    month: date
    property_type: str = Field(..., description="SF or CONDO.")
    yoy_pct: float | None = Field(None, description="Year-over-year % change in median price.")


class MedianPriceYoYResponse(BaseModel):
    scope: MarketScopeEcho
    points: list[YoyPoint] = Field(default_factory=list)


# ── 3. Price per sq ft by month ───────────────────────────────────────────────


class PpsfPoint(BaseModel):
    month: date
    median_ppsf: float | None = Field(None, description="Median sale price per square foot.")


class PpsfByMonthResponse(BaseModel):
    scope: MarketScopeEcho
    points: list[PpsfPoint] = Field(default_factory=list)


# ── 4. Median price per sq ft by city (ranked) ────────────────────────────────


class PpsfByCityItem(BaseModel):
    city: str | None = None
    median_ppsf: float | None = Field(None, description="Median $/sqft for the city.")
    median_sqft: float | None = Field(None, description="Median living area (sq ft).")
    closed: int = Field(0, description="Closed sales in the window.")


class PpsfByCityResponse(BaseModel):
    scope: MarketScopeEcho
    window: str = Field(..., description="'current_month' or 'trailing_12m'.")
    items: list[PpsfByCityItem] = Field(default_factory=list)


# ── 5. Closed sales per month ─────────────────────────────────────────────────


class ClosedSalesPoint(BaseModel):
    month: date
    closed_sales: int = 0


class ClosedSalesResponse(BaseModel):
    scope: MarketScopeEcho
    points: list[ClosedSalesPoint] = Field(default_factory=list)


# ── 6. New listings per month (SF vs Condo) ───────────────────────────────────


class NewListingsPoint(BaseModel):
    month: date
    property_type: str
    new_listings: int = 0


class NewListingsResponse(BaseModel):
    scope: MarketScopeEcho
    points: list[NewListingsPoint] = Field(default_factory=list)


# ── 7. Active & in-contract inventory ─────────────────────────────────────────


class InventoryPoint(BaseModel):
    month: date
    active_listings: int = 0
    in_contract: int = 0


class InventoryResponse(BaseModel):
    scope: MarketScopeEcho
    points: list[InventoryPoint] = Field(default_factory=list)


# ── 8. Days on market ─────────────────────────────────────────────────────────


class DomPoint(BaseModel):
    month: date
    property_type: str
    median_dom: float | None = None


class DaysOnMarketResponse(BaseModel):
    scope: MarketScopeEcho
    points: list[DomPoint] = Field(default_factory=list)


# ── 9a. Sale-to-list ratio ────────────────────────────────────────────────────


class SaleToListPoint(BaseModel):
    month: date
    sale_to_list_pct: float | None = None


class SaleToListResponse(BaseModel):
    scope: MarketScopeEcho
    points: list[SaleToListPoint] = Field(default_factory=list)


# ── 9b. Price reductions per month ────────────────────────────────────────────


class PriceReductionsPoint(BaseModel):
    month: date
    price_reductions: int = 0


class PriceReductionsResponse(BaseModel):
    scope: MarketScopeEcho
    points: list[PriceReductionsPoint] = Field(default_factory=list)


# ── 10. Sales/listings by price segment (by city) ─────────────────────────────


class SegmentItem(BaseModel):
    city: str | None = None
    price_segment: str = Field(..., description="e.g. '$1M-$1.5M'.")
    count: int = 0


class SegmentsResponse(BaseModel):
    scope: MarketScopeEcho
    status: str = Field(..., description="Which set: closed | active | new.")
    items: list[SegmentItem] = Field(default_factory=list)


# ── + Local summary table ─────────────────────────────────────────────────────


class SummaryRow(BaseModel):
    city: str | None = None
    sale_to_list_pct: float | None = None
    absorption_pct: float | None = None
    overbid_pct: float | None = None
    dom: float | None = None
    appreciation_12mo_pct: float | None = None


class SummaryResponse(BaseModel):
    scope: MarketScopeEcho
    rows: list[SummaryRow] = Field(default_factory=list)