"""
Market (MLS) — API routes — SLIM build.

Only the 5 dashboard graphs + the two drill-down feeds. Scope each call with
exactly one of county | city | zip, plus ptype where single-type.

    from core.signal.market.routes import router as market_router
    app.include_router(market_router, prefix="/v1")
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date  # noqa: F401

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.schema_manager import get_schema_session
from .schemas import (
    HomePriceTrendResponse, ValuePerSqftResponse,
    PriceDropPressureResponse, PriceCutsResponse,
    FreshSupplyResponse, HomesSoldResponse,
    InventoryResponse, SpeedToSellResponse,
    ListingsResponse,
)
from .service import MarketService

router = APIRouter(tags=["Market"])
_db = get_schema_session("signal")

ALLOWED_PTYPES = {"SF", "CONDO", "TOWNHOUSE", "MULTI_FAMILY", "LAND", "COMMERCIAL"}
ALLOWED_STATUS = {"active", "pending", "sold", "new"}

# Public-display defaults (change here if policy differs):
ONLY_PUBLIC_DEFAULT = True     # honour IDX internet_list = TRUE on drill-downs


@dataclass(frozen=True)
class MarketScope:
    area_level: str
    area_code: str


def market_scope(
    county: str | None = Query(None, description="County name, e.g. 'San Mateo'."),
    city: str | None = Query(None, description="City name, e.g. 'Los Altos Hills'."),
    zip: str | None = Query(None, description="ZIP code, e.g. '94022'."),
) -> MarketScope:
    chosen = [(lvl, val) for lvl, val in (("county", county), ("city", city), ("zip", zip)) if val]
    if len(chosen) != 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Provide exactly one of: county, city, or zip.")
    lvl, val = chosen[0]
    return MarketScope(area_level=lvl, area_code=val)


def ptype_param(ptype: str = Query("SF", description="SF | CONDO | ...")) -> str:
    p = ptype.upper()
    if p not in ALLOWED_PTYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"ptype must be one of {sorted(ALLOWED_PTYPES)}.")
    return p


# ═════════════════════════════ GRAPH 1 · PRICES ══════════════════════════════
@router.get("/market/home-price-trend/", response_model=HomePriceTrendResponse, summary="Home Price Trend")
async def home_price_trend(scope: MarketScope = Depends(market_scope),
                           ptype: str = Depends(ptype_param),
                           db: AsyncSession = Depends(_db)) -> HomePriceTrendResponse:
    return await MarketService.home_price_trend(db, scope.area_level, scope.area_code, ptype)


@router.get("/market/value-per-sqft/", response_model=ValuePerSqftResponse, summary="Value per Sq Ft")
async def value_per_sqft(scope: MarketScope = Depends(market_scope),
                         ptype: str = Depends(ptype_param),
                         db: AsyncSession = Depends(_db)) -> ValuePerSqftResponse:
    return await MarketService.value_per_sqft(db, scope.area_level, scope.area_code, ptype)


# ═══════════════════════ GRAPH 2 · NEGOTIATING ROOM ══════════════════════════
@router.get("/market/price-drop-pressure/", response_model=PriceDropPressureResponse, summary="Negotiating Room")
async def price_drop_pressure(scope: MarketScope = Depends(market_scope),
                              ptype: str = Depends(ptype_param),
                              db: AsyncSession = Depends(_db)) -> PriceDropPressureResponse:
    return await MarketService.price_drop_pressure(db, scope.area_level, scope.area_code, ptype)

@router.get("/market/price-cuts/", response_model=PriceCutsResponse, summary="Negotiating Room — cut details (drill-down)")
async def price_cuts(scope: MarketScope = Depends(market_scope),
                     ptype: str = Depends(ptype_param),
                     year: int | None = Query(None, ge=2000, le=2100, description="Filter by year, e.g. 2026."),
                     month: int | None = Query(None, ge=1, le=12, description="Filter by month number 1-12."),
                     db: AsyncSession = Depends(_db)) -> PriceCutsResponse:
    try:
        return await MarketService.price_cuts(db, scope.area_level, scope.area_code, ptype, year, month, ONLY_PUBLIC_DEFAULT)
    except Exception:
        import traceback
        raise HTTPException(status_code=500, detail=traceback.format_exc())
    
# ═══════════════════════ GRAPH 3 · SUPPLY & DEMAND ═══════════════════════════
@router.get("/market/fresh-supply/", response_model=FreshSupplyResponse, summary="Fresh Supply")
async def fresh_supply(scope: MarketScope = Depends(market_scope),
                       db: AsyncSession = Depends(_db)) -> FreshSupplyResponse:
    return await MarketService.fresh_supply(db, scope.area_level, scope.area_code)


@router.get("/market/homes-sold/", response_model=HomesSoldResponse, summary="Homes Sold")
async def homes_sold(scope: MarketScope = Depends(market_scope),
                     ptype: str = Depends(ptype_param),
                     db: AsyncSession = Depends(_db)) -> HomesSoldResponse:
    return await MarketService.homes_sold(db, scope.area_level, scope.area_code, ptype)


# ═══════════════════════ GRAPH 4 · WHAT IS AVAILABLE ═════════════════════════
@router.get("/market/available-inventory/", response_model=InventoryResponse, summary="What is Available")
async def available_inventory(scope: MarketScope = Depends(market_scope),
                              ptype: str = Depends(ptype_param),
                              db: AsyncSession = Depends(_db)) -> InventoryResponse:
    return await MarketService.available_inventory(db, scope.area_level, scope.area_code, ptype)


# ═══════════════════════ GRAPH 5 · HOW FAST HOMES SELL ═══════════════════════
@router.get("/market/speed-to-sell/", response_model=SpeedToSellResponse, summary="How Fast Homes Sell")
async def speed_to_sell(scope: MarketScope = Depends(market_scope),
                        db: AsyncSession = Depends(_db)) -> SpeedToSellResponse:
    return await MarketService.speed_to_sell(db, scope.area_level, scope.area_code)


# ═══════════ SHARED DRILL-DOWN · "See listings ->" (any card) ════════════════
@router.get("/market/listings/", response_model=ListingsResponse, summary="Listings drill-down (active|pending|sold|new)")
async def listings(scope: MarketScope = Depends(market_scope),
                   ptype: str = Depends(ptype_param),
                   status_: str = Query("active", alias="status", description="active | pending | sold | new"),
                   year: int | None = Query(None, ge=2000, le=2100, description="For sold/new: filter by year."),
                   month: int | None = Query(None, ge=1, le=12, description="For sold/new: filter by month 1-12."),
                   limit: int = Query(100, ge=1, le=500),
                   db: AsyncSession = Depends(_db)) -> ListingsResponse:
    s = status_.lower()
    if s not in ALLOWED_STATUS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"status must be one of {sorted(ALLOWED_STATUS)}.")
    return await MarketService.listings(db, scope.area_level, scope.area_code, ptype, s, year, month, ONLY_PUBLIC_DEFAULT, limit)