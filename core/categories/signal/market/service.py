"""
ZipAI — Market (MLS) Service Layer — SLIM build.

Maps repository rows to typed Pydantic models and applies the low-confidence
guard (sample_size < 5) on the price / PPSF / DOM charts.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import (
    cached,
    market_home_price_trend_cache,
    market_value_per_sqft_cache,
    market_price_drop_pressure_cache,
    market_price_cuts_cache,
    market_fresh_supply_cache,
    market_homes_sold_cache,
    market_inventory_cache,
    market_speed_to_sell_cache,
    market_listings_cache,
)
from . import repository as repo
from .schemas import (
    MarketScopeEcho,
    HomePriceTrendPoint, HomePriceTrendResponse,
    ValuePerSqftPoint, ValuePerSqftResponse,
    PriceDropPressurePoint, PriceDropPressureResponse,
    PriceCutRow, PriceCutsResponse,
    FreshSupplyPoint, FreshSupplyResponse,
    HomesSoldPoint, HomesSoldResponse,
    InventoryPoint, InventoryResponse,
    SpeedToSellPoint, SpeedToSellResponse,
    ListingRow, ListingsResponse,
)

LOW_CONFIDENCE_MIN = 5   # months with fewer closed sales than this are flagged


def _i(v) -> int:
    return int(v) if v is not None else 0


def _f(v) -> float | None:
    return float(v) if v is not None else None


def _scope(area_level, area_code, ptype=None) -> MarketScopeEcho:
    return MarketScopeEcho(area_level=area_level, area_code=area_code, property_type=ptype)


class MarketService:

    # Graph 1 · Prices ────────────────────────────────────────────────────────
    @staticmethod
    @cached(market_home_price_trend_cache)
    async def home_price_trend(session: AsyncSession, area_level, area_code, ptype) -> HomePriceTrendResponse:
        rows = await repo.home_price_trend(session, area_level, area_code, ptype)
        pts = []
        for r in rows:
            n = _i(r["sample_size"])
            pts.append(HomePriceTrendPoint(month=r["month"], median_sale_price=_f(r["median_sale_price"]),
                                           sample_size=n, low_confidence=n < LOW_CONFIDENCE_MIN))
        return HomePriceTrendResponse(scope=_scope(area_level, area_code, ptype), points=pts)

    @staticmethod
    @cached(market_value_per_sqft_cache)
    async def value_per_sqft(session: AsyncSession, area_level, area_code, ptype) -> ValuePerSqftResponse:
        rows = await repo.value_per_sqft(session, area_level, area_code, ptype)
        pts = []
        for r in rows:
            n = _i(r["sample_size"])
            pts.append(ValuePerSqftPoint(month=r["month"], median_ppsf=_f(r["median_ppsf"]),
                                         sample_size=n, low_confidence=n < LOW_CONFIDENCE_MIN))
        return ValuePerSqftResponse(scope=_scope(area_level, area_code, ptype), points=pts)

    # Graph 2 · Negotiating room ───────────────────────────────────────────────
    @staticmethod
    @cached(market_price_drop_pressure_cache)
    async def price_drop_pressure(session: AsyncSession, area_level, area_code, ptype) -> PriceDropPressureResponse:
        rows = await repo.price_drop_pressure(session, area_level, area_code, ptype)
        pts = [PriceDropPressurePoint(month=r["month"], price_drops=_i(r["price_drops"]),
                                      new_listings=_i(r["new_listings"]),
                                      drops_per_100_new=_f(r["drops_per_100_new"])) for r in rows]
        return PriceDropPressureResponse(scope=_scope(area_level, area_code, ptype), points=pts)

    @staticmethod
    @cached(market_price_cuts_cache)
    async def price_cuts(session: AsyncSession, area_level, area_code, ptype, year, month, only_public) -> PriceCutsResponse:
        rows = await repo.price_cuts(session, area_level, area_code, ptype, year, month, only_public)
        out = [PriceCutRow(event_date=r["event_date"], listing_key_numeric=r["listing_key_numeric"],
                           address=r.get("address"), city=r.get("city"), zip_code=r.get("zip_code"),
                           prior_price=_f(r["prior_price"]), price=_f(r["price"]),
                           cut_amount=_f(r["cut_amount"]), cut_pct=_f(r["cut_pct"])) for r in rows]
        return PriceCutsResponse(scope=_scope(area_level, area_code, ptype), year=year, month=month,
                                 count=len(out), rows=out)

    # Graph 3 · Supply & demand ────────────────────────────────────────────────
    @staticmethod
    @cached(market_fresh_supply_cache)
    async def fresh_supply(session: AsyncSession, area_level, area_code) -> FreshSupplyResponse:
        rows = await repo.fresh_supply(session, area_level, area_code)
        pts = [FreshSupplyPoint(month=r["month"], property_type=r["property_type"],
                                new_listings=_i(r["new_listings"])) for r in rows]
        return FreshSupplyResponse(scope=_scope(area_level, area_code), points=pts)

    @staticmethod
    @cached(market_homes_sold_cache)
    async def homes_sold(session: AsyncSession, area_level, area_code, ptype) -> HomesSoldResponse:
        rows = await repo.homes_sold(session, area_level, area_code, ptype)
        pts = [HomesSoldPoint(month=r["month"], closed_sales=_i(r["closed_sales"])) for r in rows]
        return HomesSoldResponse(scope=_scope(area_level, area_code, ptype), points=pts)

    # Graph 4 · What is available ──────────────────────────────────────────────
    @staticmethod
    @cached(market_inventory_cache)
    async def available_inventory(session: AsyncSession, area_level, area_code, ptype) -> InventoryResponse:
        rows = await repo.available_inventory(session, area_level, area_code, ptype)
        pts = [InventoryPoint(month=r["month"], active_listings=_i(r["active_listings"]),
                              in_contract=_i(r["in_contract"])) for r in rows]
        return InventoryResponse(scope=_scope(area_level, area_code, ptype), points=pts)

    # Graph 5 · How fast homes sell ────────────────────────────────────────────
    @staticmethod
    @cached(market_speed_to_sell_cache)
    async def speed_to_sell(session: AsyncSession, area_level, area_code) -> SpeedToSellResponse:
        rows = await repo.speed_to_sell(session, area_level, area_code)
        pts = []
        for r in rows:
            n = _i(r["sample_size"])
            pts.append(SpeedToSellPoint(month=r["month"], property_type=r["property_type"],
                                        median_dom=_f(r["median_dom"]),
                                        sample_size=n, low_confidence=n < LOW_CONFIDENCE_MIN))
        return SpeedToSellResponse(scope=_scope(area_level, area_code), points=pts)

    # Shared drill-down · listings ─────────────────────────────────────────────
    @staticmethod
    @cached(market_listings_cache)
    async def listings(session: AsyncSession, area_level, area_code, ptype, status_key, year, month, only_public, limit) -> ListingsResponse:
        rows = await repo.listings(session, area_level, area_code, ptype, status_key, year, month, only_public, limit)
        out = [ListingRow(listing_key_numeric=r["listing_key_numeric"], address=r.get("address"),
                          city=r.get("city"), zip_code=r.get("zip_code"),
                          list_price=_f(r["list_price"]), sale_price=_f(r["sale_price"]),
                          beds=_f(r["beds"]), baths=_f(r["baths"]), sqft=_f(r["sqft"]),
                          status=r.get("status"), dom=(_i(r["dom"]) if r["dom"] is not None else None),
                          list_date=r["list_date"], close_date=r["close_date"]) for r in rows]
        return ListingsResponse(scope=_scope(area_level, area_code, ptype), status=status_key,
                                count=len(out), rows=out)