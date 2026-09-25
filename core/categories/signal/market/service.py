"""
ZipAI — Market (MLS) Service Layer — SLIM build.

Maps repository rows to typed Pydantic models and applies the low-confidence
guard (sample_size < 5) on the price / PPSF / DOM / leverage / reduction charts.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import (
    cached,
    market_home_price_trend_cache,
    market_value_per_sqft_cache,
    market_price_drop_pressure_cache,
    market_price_cuts_cache,
    market_buyer_leverage_cache,
    market_price_reductions_cache,
    market_fresh_supply_cache,
    market_homes_sold_cache,
    market_inventory_cache,
    market_speed_to_sell_cache,
    market_listings_cache,
    market_price_distribution_cache,
    market_dom_breakdown_cache,
    market_closed_monthly_cache,
)
from . import repository as repo
from .schemas import (
    MarketScopeEcho,
    HomePriceTrendPoint, HomePriceTrendResponse,
    ValuePerSqftPoint, ValuePerSqftResponse,
    PriceDropPressurePoint, PriceDropPressureResponse,
    PriceCutRow, PriceCutsResponse,
    BuyerLeveragePoint, BuyerLeverageResponse,
    PriceReductionsPoint, PriceReductionsResponse,
    FreshSupplyPoint, FreshSupplyResponse,
    HomesSoldPoint, HomesSoldResponse,
    InventoryPoint, InventoryResponse,
    SpeedToSellPoint, SpeedToSellResponse,
    ListingRow, ListingsResponse,
    PriceBand, PriceDistributionResponse,
    DomBucket, DomBreakdownResponse,
)

LOW_CONFIDENCE_MIN = 5   # months with fewer closed sales than this are flagged


import datetime as _dt
from decimal import Decimal as _Decimal


def _i(v):
    """Coerce to int, tolerating timedelta, Decimal, float, str, None."""
    if v is None:
        return 0
    if isinstance(v, _dt.timedelta):
        return int(v.days)
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _f(v):
    """Coerce to float | None, tolerating Decimal, timedelta, str."""
    if v is None:
        return None
    if isinstance(v, _dt.timedelta):
        return float(v.days)
    if isinstance(v, _Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _scope(area_level, area_code, ptype=None) -> MarketScopeEcho:
    return MarketScopeEcho(area_level=area_level, area_code=area_code, property_type=ptype)


@cached(market_closed_monthly_cache)
async def _closed_monthly(session: AsyncSession, area_level, area_code, ptype, months):
    """Shared closed-sales rows behind home-price-trend, value-per-sqft and homes-sold.

    Cached (and in-flight coalesced) on its own, so the three charts requested
    together for one area/ptype cost a single scan.
    """
    return await repo.closed_monthly(session, area_level, area_code, ptype, months)


class MarketService:

    # Graph 1 · Prices ────────────────────────────────────────────────────────
    @staticmethod
    @cached(market_home_price_trend_cache)
    async def home_price_trend(session: AsyncSession, area_level, area_code, ptype, months) -> HomePriceTrendResponse:
        rows = await _closed_monthly(session, area_level, area_code, ptype, months)
        pts = []
        for r in rows:
            n = _i(r["sample_size"])
            pts.append(HomePriceTrendPoint(month=r["month"], median_sale_price=_f(r["median_sale_price"]),
                                           sample_size=n, low_confidence=n < LOW_CONFIDENCE_MIN))
        return HomePriceTrendResponse(scope=_scope(area_level, area_code, ptype), points=pts)

    @staticmethod
    @cached(market_value_per_sqft_cache)
    async def value_per_sqft(session: AsyncSession, area_level, area_code, ptype, months) -> ValuePerSqftResponse:
        rows = await _closed_monthly(session, area_level, area_code, ptype, months)
        pts = []
        for r in rows:
            n = _i(r["ppsf_sample_size"])
            if n == 0:
                continue  # no sale with living_sqft > 0 this month — the chart never had this point
            pts.append(ValuePerSqftPoint(month=r["month"], median_ppsf=_f(r["median_ppsf"]),
                                         sample_size=n, low_confidence=n < LOW_CONFIDENCE_MIN))
        return ValuePerSqftResponse(scope=_scope(area_level, area_code, ptype), points=pts)

    # Graph 2 · Negotiating room ───────────────────────────────────────────────
    @staticmethod
    @cached(market_price_drop_pressure_cache)
    async def price_drop_pressure(session: AsyncSession, area_level, area_code, ptype, months) -> PriceDropPressureResponse:
        rows = await repo.price_drop_pressure(session, area_level, area_code, ptype, months)
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

    @staticmethod
    @cached(market_buyer_leverage_cache)
    async def buyer_leverage(session: AsyncSession, area_level, area_code, months) -> BuyerLeverageResponse:
        # Same shared rows as home-price-trend for SF and CONDO, which are usually
        # requested for the same area in the same page load, so these are cache hits.
        by_month: dict = {}
        for key, ptype in (("sf", "SF"), ("condo", "CONDO")):
            for r in await _closed_monthly(session, area_level, area_code, ptype, months):
                n = _i(r["stl_sample_size"])
                if n == 0:
                    continue
                p = by_month.setdefault(r["month"], {"sf": None, "condo": None, "sf_n": 0, "condo_n": 0})
                p[f"{key}_n"] = n
                if n >= LOW_CONFIDENCE_MIN:   # a thin series is null, not flagged (see schema)
                    p[key] = _f(r["median_sale_to_list"])
        pts = []
        for month in sorted(by_month):
            p = by_month[month]
            n = (p["sf_n"] if p["sf"] is not None else 0) + (p["condo_n"] if p["condo"] is not None else 0)
            pts.append(BuyerLeveragePoint(month=month, sf=p["sf"], condo=p["condo"],
                                          sf_sample_size=p["sf_n"], condo_sample_size=p["condo_n"],
                                          sample_size=n, low_confidence=n == 0))
        return BuyerLeverageResponse(scope=_scope(area_level, area_code), points=pts)

    @staticmethod
    @cached(market_price_reductions_cache)
    async def price_reductions(session: AsyncSession, area_level, area_code, ptype, months) -> PriceReductionsResponse:
        rows = await _closed_monthly(session, area_level, area_code, ptype, months)
        pts = []
        for r in rows:
            n = _i(r["cut_sample_size"])
            if n == 0:
                continue  # no sale with a known original list price this month
            cut = _i(r["sold_after_cut"])
            pts.append(PriceReductionsPoint(month=r["month"], sold_after_cut=cut,
                                            pct_reduced=round(100 * cut / n, 1),
                                            median_cut_pct=_f(r["median_cut_pct"]),
                                            sample_size=n, low_confidence=n < LOW_CONFIDENCE_MIN))
        return PriceReductionsResponse(scope=_scope(area_level, area_code, ptype), points=pts)

    # Graph 3 · Supply & demand ────────────────────────────────────────────────
    @staticmethod
    @cached(market_fresh_supply_cache)
    async def fresh_supply(session: AsyncSession, area_level, area_code, months) -> FreshSupplyResponse:
        rows = await repo.fresh_supply(session, area_level, area_code, months)
        pts = [FreshSupplyPoint(month=r["month"], property_type=r["property_type"],
                                new_listings=_i(r["new_listings"])) for r in rows]
        return FreshSupplyResponse(scope=_scope(area_level, area_code), points=pts)

    @staticmethod
    @cached(market_homes_sold_cache)
    async def homes_sold(session: AsyncSession, area_level, area_code, ptype, months) -> HomesSoldResponse:
        rows = await _closed_monthly(session, area_level, area_code, ptype, months)
        pts = [HomesSoldPoint(month=r["month"], closed_sales=_i(r["sample_size"])) for r in rows]
        return HomesSoldResponse(scope=_scope(area_level, area_code, ptype), points=pts)

    # Graph 4 · What is available ──────────────────────────────────────────────
    @staticmethod
    @cached(market_inventory_cache)
    async def available_inventory(session: AsyncSession, area_level, area_code, ptype, months) -> InventoryResponse:
        rows = await repo.available_inventory(session, area_level, area_code, ptype, months)
        pts = [InventoryPoint(month=r["month"], active_listings=_i(r["active_listings"]),
                              in_contract=_i(r["in_contract"])) for r in rows]
        return InventoryResponse(scope=_scope(area_level, area_code, ptype), points=pts)

    # Graph 4 drill-down · price distribution ──────────────────────────────────
    @staticmethod
    @cached(market_price_distribution_cache)
    async def price_distribution(session: AsyncSession, area_level, area_code, ptype) -> PriceDistributionResponse:
        rows = await repo.price_distribution(session, area_level, area_code, ptype)
        bands = [PriceBand(band=r["band"], min_price=_f(r["min_price"]),
                           max_price=_f(r["max_price"]), homes=_i(r["homes"])) for r in rows]
        return PriceDistributionResponse(scope=_scope(area_level, area_code, ptype), bands=bands)


    # Graph 5 · How fast homes sell ────────────────────────────────────────────
    @staticmethod
    @cached(market_speed_to_sell_cache)
    async def speed_to_sell(session: AsyncSession, area_level, area_code, months) -> SpeedToSellResponse:
        rows = await repo.speed_to_sell(session, area_level, area_code, months)
        pts = []
        for r in rows:
            n = _i(r["sample_size"])
            pts.append(SpeedToSellPoint(month=r["month"], property_type=r["property_type"],
                                        median_dom=_f(r["median_dom"]),
                                        sample_size=n, low_confidence=n < LOW_CONFIDENCE_MIN))
        return SpeedToSellResponse(scope=_scope(area_level, area_code), points=pts)

    # Graph 5 drill-down · DOM breakdown ───────────────────────────────────────
    @staticmethod
    @cached(market_dom_breakdown_cache)
    async def dom_breakdown(session: AsyncSession, area_level, area_code, ptype, year, month) -> DomBreakdownResponse:
        rows = await repo.dom_breakdown(session, area_level, area_code, ptype, year, month)
        buckets = [DomBucket(bucket=r["bucket"],
                             dom_min=(_i(r["dom_min"]) if r["dom_min"] is not None else None),
                             dom_max=(_i(r["dom_max"]) if r["dom_max"] is not None else None),
                             homes=_i(r["homes"])) for r in rows]
        return DomBreakdownResponse(scope=_scope(area_level, area_code, ptype), buckets=buckets)

    # Shared drill-down · listings ─────────────────────────────────────────────
    @staticmethod
    @cached(market_listings_cache)
    async def listings(session: AsyncSession, area_level, area_code, ptype, status_key, year, month,
                       price_min, price_max, dom_min, dom_max, only_public, limit) -> ListingsResponse:
        rows = await repo.listings(session, area_level, area_code, ptype, status_key, year, month,
                                   price_min, price_max, dom_min, dom_max, only_public, limit)
        out = [ListingRow(listing_key_numeric=r["listing_key_numeric"], address=r.get("address"),
                          city=r.get("city"), zip_code=r.get("zip_code"),
                          list_price=_f(r["list_price"]), sale_price=_f(r["sale_price"]),
                          beds=_f(r["beds"]), baths=_f(r["baths"]), sqft=_f(r["sqft"]),
                          status=r.get("status"), dom=(_i(r["dom"]) if r["dom"] is not None else None),
                          list_date=r["list_date"], close_date=r["close_date"]) for r in rows]
        return ListingsResponse(scope=_scope(area_level, area_code, ptype), status=status_key,
                                count=len(out), rows=out)

