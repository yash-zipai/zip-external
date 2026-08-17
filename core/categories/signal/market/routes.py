"""
Market (MLS) category — API routes.

An APIRouter holding the market-analysis endpoints (the 10 Compass-style charts
plus the local summary table). Every endpoint is scoped to an area via query
params — provide exactly one of ``county``, ``city`` or ``zip`` — and, where the
chart is single-type, a ``ptype`` (SF | CONDO | ...).

Include it under whatever prefix your app uses, e.g.:

    app.include_router(market_router, prefix="/api")
    # -> /api/market/median-sale-price/?county=San Mateo&ptype=SF
    # -> /api/market/summary/?county=San Mateo&ptype=SF

Data comes from the ``signal`` schema, so the session dependency binds there
(search_path = signal,public), which also reaches public.zipdata_idxlistingpriceevent.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.schema_manager import get_schema_session
from core.categories.signal.market.schemas import (
    ClosedSalesResponse, DaysOnMarketResponse, InventoryResponse,
    MedianPriceYoYResponse, MedianSalePriceResponse, NewListingsResponse,
    PpsfByCityResponse, PpsfByMonthResponse, PriceReductionsResponse,
    SaleToListResponse, SegmentsResponse, SummaryResponse,
)
from .service import MarketService

router = APIRouter(tags=["Market"])

# market tables live in the `signal` schema
_db = get_schema_session("signal")

ALLOWED_PTYPES = {"SF", "CONDO", "TOWNHOUSE", "MULTI_FAMILY", "LAND", "COMMERCIAL"}


# ── Shared dependencies ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class MarketScope:
    area_level: str   # county | city | zip
    area_code: str


def market_scope(
    county: str | None = Query(None, description="County name, e.g. 'San Mateo'."),
    city: str | None = Query(None, description="City name, e.g. 'Redwood City'."),
    zip: str | None = Query(None, description="ZIP code, e.g. '94103'."),
) -> MarketScope:
    """Resolve the area from exactly one of county / city / zip."""
    chosen = [(lvl, val) for lvl, val in (("county", county), ("city", city), ("zip", zip)) if val]
    if len(chosen) != 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide exactly one of: county, city, or zip.",
        )
    lvl, val = chosen[0]
    return MarketScope(area_level=lvl, area_code=val)


def ptype_param(
    ptype: str = Query("SF", description="Property type: SF | CONDO | TOWNHOUSE | MULTI_FAMILY | LAND | COMMERCIAL."),
) -> str:
    p = ptype.upper()
    if p not in ALLOWED_PTYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"ptype must be one of {sorted(ALLOWED_PTYPES)}.",
        )
    return p


# ── 1. Median sale price over time ────────────────────────────────────────────


@router.get("/market/median-sale-price/", response_model=MedianSalePriceResponse,
            summary="Median sale price over time")
async def median_sale_price(
    scope: MarketScope = Depends(market_scope),
    ptype: str = Depends(ptype_param),
    db: AsyncSession = Depends(_db),
) -> MedianSalePriceResponse:
    return await MarketService.median_sale_price(db, scope.area_level, scope.area_code, ptype)


# ── 2. Median price YoY % (SF vs Condo) ───────────────────────────────────────


@router.get("/market/median-price-yoy/", response_model=MedianPriceYoYResponse,
            summary="Median price year-over-year % (SF vs Condo)")
async def median_price_yoy(
    scope: MarketScope = Depends(market_scope),
    db: AsyncSession = Depends(_db),
) -> MedianPriceYoYResponse:
    return await MarketService.median_price_yoy(db, scope.area_level, scope.area_code)


# ── 3. Price per sq ft by month ───────────────────────────────────────────────


@router.get("/market/price-per-sqft/", response_model=PpsfByMonthResponse,
            summary="Median price per square foot by month")
async def ppsf_by_month(
    scope: MarketScope = Depends(market_scope),
    ptype: str = Depends(ptype_param),
    db: AsyncSession = Depends(_db),
) -> PpsfByMonthResponse:
    return await MarketService.ppsf_by_month(db, scope.area_level, scope.area_code, ptype)


# ── 4. Median price per sq ft by city ─────────────────────────────────────────


@router.get("/market/price-per-sqft-by-city/", response_model=PpsfByCityResponse,
            summary="Median price per sq ft ranked by city")
async def ppsf_by_city(
    scope: MarketScope = Depends(market_scope),
    ptype: str = Depends(ptype_param),
    trailing_12m: bool = Query(False, description="True = trailing 12 months; False = current month only."),
    db: AsyncSession = Depends(_db),
) -> PpsfByCityResponse:
    return await MarketService.ppsf_by_city(db, scope.area_level, scope.area_code, ptype, trailing_12m)


# ── 5. Closed sales per month ─────────────────────────────────────────────────


@router.get("/market/closed-sales/", response_model=ClosedSalesResponse,
            summary="Closed sales per month")
async def closed_sales(
    scope: MarketScope = Depends(market_scope),
    ptype: str = Depends(ptype_param),
    db: AsyncSession = Depends(_db),
) -> ClosedSalesResponse:
    return await MarketService.closed_sales(db, scope.area_level, scope.area_code, ptype)


# ── 6. New listings per month (SF vs Condo) ───────────────────────────────────


@router.get("/market/new-listings/", response_model=NewListingsResponse,
            summary="New listings per month (SF vs Condo)")
async def new_listings(
    scope: MarketScope = Depends(market_scope),
    db: AsyncSession = Depends(_db),
) -> NewListingsResponse:
    return await MarketService.new_listings(db, scope.area_level, scope.area_code)


# ── 7. Active & in-contract inventory ─────────────────────────────────────────


@router.get("/market/inventory/", response_model=InventoryResponse,
            summary="Active & in-contract listings over time")
async def inventory(
    scope: MarketScope = Depends(market_scope),
    ptype: str = Depends(ptype_param),
    db: AsyncSession = Depends(_db),
) -> InventoryResponse:
    return await MarketService.inventory(db, scope.area_level, scope.area_code, ptype)


# ── 8. Days on market (SF vs Condo) ───────────────────────────────────────────


@router.get("/market/days-on-market/", response_model=DaysOnMarketResponse,
            summary="Median days on market (SF vs Condo)")
async def days_on_market(
    scope: MarketScope = Depends(market_scope),
    db: AsyncSession = Depends(_db),
) -> DaysOnMarketResponse:
    return await MarketService.days_on_market(db, scope.area_level, scope.area_code)


# ── 9a. Sale-to-list ratio ────────────────────────────────────────────────────


@router.get("/market/sale-to-list/", response_model=SaleToListResponse,
            summary="Sale-to-list price ratio by month")
async def sale_to_list(
    scope: MarketScope = Depends(market_scope),
    ptype: str = Depends(ptype_param),
    db: AsyncSession = Depends(_db),
) -> SaleToListResponse:
    return await MarketService.sale_to_list(db, scope.area_level, scope.area_code, ptype)


# ── 9b. Price reductions per month ────────────────────────────────────────────


@router.get("/market/price-reductions/", response_model=PriceReductionsResponse,
            summary="Price reductions per month")
async def price_reductions(
    scope: MarketScope = Depends(market_scope),
    db: AsyncSession = Depends(_db),
) -> PriceReductionsResponse:
    return await MarketService.price_reductions(db, scope.area_level, scope.area_code)


# ── 10. Sales / listings by price segment ─────────────────────────────────────


@router.get("/market/segments/", response_model=SegmentsResponse,
            summary="Sales/listings by price segment, by city")
async def segments(
    scope: MarketScope = Depends(market_scope),
    ptype: str = Depends(ptype_param),
    status_set: str = Query("closed", alias="status", description="closed | active | new."),
    db: AsyncSession = Depends(_db),
) -> SegmentsResponse:
    s = status_set.lower()
    if s not in {"closed", "active", "new"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="status must be one of: closed, active, new.",
        )
    return await MarketService.segments(db, scope.area_level, scope.area_code, ptype, s)


# ── + Local summary table ─────────────────────────────────────────────────────


@router.get("/market/summary/", response_model=SummaryResponse,
            summary="Local summary table (per city)")
async def summary(
    scope: MarketScope = Depends(market_scope),
    ptype: str = Depends(ptype_param),
    db: AsyncSession = Depends(_db),
) -> SummaryResponse:
    return await MarketService.summary(db, scope.area_level, scope.area_code, ptype)