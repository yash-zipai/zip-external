"""
ZipAI — Market (MLS) Service Layer.

Orchestrates repository calls, applies TTL caching, and maps raw DB rows to
typed Pydantic response models. All business logic for the market-analysis
endpoints lives here.

Caches are defined locally to keep the market module self-contained; move them
to core/cache.py (as market_* instances) if you prefer to match the other
categories exactly.
"""

from __future__ import annotations

from typing import Any

from cachetools import TTLCache
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import (
    cached,
    market_median_sale_price_cache,
    market_median_price_yoy_cache,
    market_ppsf_month_cache,
    market_ppsf_city_cache,
    market_closed_sales_cache,
    market_new_listings_cache,
    market_inventory_cache,
    market_dom_cache,
    market_sale_to_list_cache,
    market_price_reductions_cache,
    market_segments_cache,
    market_summary_cache,
)

from core.categories.signal.market import repository as repo
from core.categories.signal.market.schemas import (
    ClosedSalesPoint, ClosedSalesResponse,
    DaysOnMarketResponse, DomPoint,
    InventoryPoint, InventoryResponse,
    MarketScopeEcho,
    MedianPriceYoYResponse,
    MedianSalePricePoint, MedianSalePriceResponse,
    NewListingsPoint, NewListingsResponse,
    PpsfByCityItem, PpsfByCityResponse,
    PpsfByMonthResponse, PpsfPoint,
    PriceReductionsPoint, PriceReductionsResponse,
    SaleToListPoint, SaleToListResponse,
    SegmentItem, SegmentsResponse,
    SummaryResponse, SummaryRow,
    YoyPoint,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v: Any) -> int:
    if v is None:
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _scope(area_level: str, area_code: str, property_type: str | None = None) -> MarketScopeEcho:
    return MarketScopeEcho(area_level=area_level, area_code=area_code, property_type=property_type)


class MarketService:
    """Business logic for the market-analysis endpoints."""

    # 1 ─────────────────────────────────────────────────────────────────────
    @staticmethod
    @cached(market_median_sale_price_cache)
    async def median_sale_price(session: AsyncSession, area_level, area_code, property_type) -> MedianSalePriceResponse:
        rows = await repo.median_sale_price(session, area_level, area_code, property_type)
        pts = [MedianSalePricePoint(month=r["month"], median_sale_price=_f(r["median_sale_price"]),
                                    closed_sales=_i(r["closed_sales"])) for r in rows]
        return MedianSalePriceResponse(scope=_scope(area_level, area_code, property_type), points=pts)

    # 2 ─────────────────────────────────────────────────────────────────────
    @staticmethod
    @cached(market_median_price_yoy_cache)
    async def median_price_yoy(session: AsyncSession, area_level, area_code) -> MedianPriceYoYResponse:
        rows = await repo.median_price_yoy(session, area_level, area_code)
        pts = [YoyPoint(month=r["month"], property_type=r["property_type"], yoy_pct=_f(r["yoy_pct"])) for r in rows]
        return MedianPriceYoYResponse(scope=_scope(area_level, area_code), points=pts)

    # 3 ─────────────────────────────────────────────────────────────────────
    @staticmethod
    @cached(market_ppsf_month_cache)
    async def ppsf_by_month(session: AsyncSession, area_level, area_code, property_type) -> PpsfByMonthResponse:
        rows = await repo.ppsf_by_month(session, area_level, area_code, property_type)
        pts = [PpsfPoint(month=r["month"], median_ppsf=_f(r["median_ppsf"])) for r in rows]
        return PpsfByMonthResponse(scope=_scope(area_level, area_code, property_type), points=pts)

    # 4 ─────────────────────────────────────────────────────────────────────
    @staticmethod
    @cached(market_ppsf_city_cache)
    async def ppsf_by_city(session: AsyncSession, area_level, area_code, property_type, trailing_12m: bool) -> PpsfByCityResponse:
        rows = await repo.ppsf_by_city(session, area_level, area_code, property_type, trailing_12m)
        items = [PpsfByCityItem(city=r["city"], median_ppsf=_f(r["median_ppsf"]),
                                median_sqft=_f(r["median_sqft"]), closed=_i(r["closed"])) for r in rows]
        return PpsfByCityResponse(scope=_scope(area_level, area_code, property_type),
                                  window="trailing_12m" if trailing_12m else "current_month", items=items)

    # 5 ─────────────────────────────────────────────────────────────────────
    @staticmethod
    @cached(market_closed_sales_cache)
    async def closed_sales(session: AsyncSession, area_level, area_code, property_type) -> ClosedSalesResponse:
        rows = await repo.closed_sales(session, area_level, area_code, property_type)
        pts = [ClosedSalesPoint(month=r["month"], closed_sales=_i(r["closed_sales"])) for r in rows]
        return ClosedSalesResponse(scope=_scope(area_level, area_code, property_type), points=pts)

    # 6 ─────────────────────────────────────────────────────────────────────
    @staticmethod
    @cached(market_new_listings_cache)
    async def new_listings(session: AsyncSession, area_level, area_code) -> NewListingsResponse:
        rows = await repo.new_listings(session, area_level, area_code)
        pts = [NewListingsPoint(month=r["month"], property_type=r["property_type"],
                                new_listings=_i(r["new_listings"])) for r in rows]
        return NewListingsResponse(scope=_scope(area_level, area_code), points=pts)

    # 7 ─────────────────────────────────────────────────────────────────────
    @staticmethod
    @cached(market_inventory_cache)
    async def inventory(session: AsyncSession, area_level, area_code, property_type) -> InventoryResponse:
        rows = await repo.inventory(session, area_level, area_code, property_type)
        pts = [InventoryPoint(month=r["month"], active_listings=_i(r["active_listings"]),
                              in_contract=_i(r["in_contract"])) for r in rows]
        return InventoryResponse(scope=_scope(area_level, area_code, property_type), points=pts)

    # 8 ─────────────────────────────────────────────────────────────────────
    @staticmethod
    @cached(market_dom_cache)
    async def days_on_market(session: AsyncSession, area_level, area_code) -> DaysOnMarketResponse:
        rows = await repo.days_on_market(session, area_level, area_code)
        pts = [DomPoint(month=r["month"], property_type=r["property_type"], median_dom=_f(r["median_dom"])) for r in rows]
        return DaysOnMarketResponse(scope=_scope(area_level, area_code), points=pts)

    # 9a ────────────────────────────────────────────────────────────────────
    @staticmethod
    @cached(market_sale_to_list_cache)
    async def sale_to_list(session: AsyncSession, area_level, area_code, property_type) -> SaleToListResponse:
        rows = await repo.sale_to_list(session, area_level, area_code, property_type)
        pts = [SaleToListPoint(month=r["month"], sale_to_list_pct=_f(r["sale_to_list_pct"])) for r in rows]
        return SaleToListResponse(scope=_scope(area_level, area_code, property_type), points=pts)

    # 9b ────────────────────────────────────────────────────────────────────
    @staticmethod
    @cached(market_price_reductions_cache)
    async def price_reductions(session: AsyncSession, area_level, area_code) -> PriceReductionsResponse:
        rows = await repo.price_reductions(session, area_level, area_code)
        pts = [PriceReductionsPoint(month=r["month"], price_reductions=_i(r["price_reductions"])) for r in rows]
        return PriceReductionsResponse(scope=_scope(area_level, area_code), points=pts)

    # 10 ────────────────────────────────────────────────────────────────────
    @staticmethod
    @cached(market_segments_cache)
    async def segments(session: AsyncSession, area_level, area_code, property_type, status: str) -> SegmentsResponse:
        rows = await repo.segments_by_city(session, area_level, area_code, property_type, status)
        items = [SegmentItem(city=r["city"], price_segment=r["price_segment"], count=_i(r["count"])) for r in rows]
        return SegmentsResponse(scope=_scope(area_level, area_code, property_type), status=status, items=items)

    # + ─────────────────────────────────────────────────────────────────────
    @staticmethod
    @cached(market_summary_cache)
    async def summary(session: AsyncSession, area_level, area_code, property_type) -> SummaryResponse:
        rows = await repo.summary(session, area_level, area_code, property_type)
        out = [SummaryRow(city=r["city"], sale_to_list_pct=_f(r["sale_to_list_pct"]),
                          absorption_pct=_f(r["absorption_pct"]), overbid_pct=_f(r["overbid_pct"]),
                          dom=_f(r["dom"]), appreciation_12mo_pct=_f(r["appreciation_12mo_pct"])) for r in rows]
        return SummaryResponse(scope=_scope(area_level, area_code, property_type), rows=out)