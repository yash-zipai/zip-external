"""
ZipAI — Market (MLS) Data Repository (DAL) — SLIM build.

Raw SQL for the 5 dashboard graphs + two drill-down feeds. Values are bound
parameters; the only interpolated token is the area column name, resolved from
a fixed whitelist (injection-safe). Queries match the frontend SQL 1:1
(city/ptype are parameterized).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_AREA_COLUMNS = {"county": "county", "city": "city", "zip": "zip_code"}


def _area_col(area_level: str) -> str:
    try:
        return _AREA_COLUMNS[area_level]
    except KeyError:
        raise ValueError(f"Unsupported area_level '{area_level}'. Use county | city | zip.")


async def _rows(session: AsyncSession, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    result = await session.execute(text(sql), params)
    return [dict(r._mapping) for r in result.fetchall()]


# ── Graph 1 · HOME PRICE TREND (median sale price) ────────────────────────────
async def home_price_trend(session, area_level, area_code, property_type):
    col = _area_col(area_level)
    sql = f"""
        SELECT date_trunc('month', close_date)::date AS month,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY sale_price) AS median_sale_price,
               count(*) AS sample_size
        FROM   signal.listing_fact
        WHERE  standard_status = 'Closed' AND property_type = :ptype AND {col} = :area
        GROUP  BY 1 ORDER BY 1
    """
    return await _rows(session, sql, {"ptype": property_type, "area": area_code})


# ── Graph 1 · VALUE PER SQ FT (median $/sqft) ─────────────────────────────────
async def value_per_sqft(session, area_level, area_code, property_type):
    col = _area_col(area_level)
    sql = f"""
        SELECT date_trunc('month', close_date)::date AS month,
               round(percentile_cont(0.5) WITHIN GROUP (ORDER BY sale_price/NULLIF(living_sqft,0))::numeric,0) AS median_ppsf,
               count(*) AS sample_size
        FROM   signal.listing_fact
        WHERE  standard_status = 'Closed' AND property_type = :ptype AND {col} = :area AND living_sqft > 0
        GROUP  BY 1 ORDER BY 1
    """
    return await _rows(session, sql, {"ptype": property_type, "area": area_code})


# ── Graph 2 · PRICE DROP PRESSURE (Negotiating room) ──────────────────────────
async def price_drop_pressure(session, area_level, area_code, property_type):
    col = _area_col(area_level)
    sql = f"""
        SELECT month,
               count(*) FILTER (WHERE kind='price_drop')  AS price_drops,
               count(*) FILTER (WHERE kind='new_listing') AS new_listings,
               round(100.0*count(*) FILTER (WHERE kind='price_drop')/NULLIF(count(*) FILTER (WHERE kind='new_listing'),0),1) AS drops_per_100_new
        FROM   signal.market_event
        WHERE  {col} = :area AND property_type = :ptype
        GROUP  BY month ORDER BY month
    """
    return await _rows(session, sql, {"area": area_code, "ptype": property_type})


# ── Graph 2 drill-down · PRICE CUTS (individual cut events) ────────────────────
async def price_cuts(session, area_level, area_code, property_type, year, month, only_public):
    col = _area_col(area_level)
    sql = f"""
        SELECT me.event_date,
               me.listing_key_numeric,
               NULL::text AS address,
               me.city, me.zip_code,
               me.prior_price, me.price,
               (me.prior_price - me.price)                             AS cut_amount,
               round(((1 - me.price/NULLIF(me.prior_price,0))*100)::numeric, 1) AS cut_pct
        FROM   signal.market_event me
        WHERE  me.kind = 'price_drop' AND me.{col} = :area AND me.property_type = :ptype
          AND  (CAST(:year  AS int) IS NULL OR EXTRACT(YEAR  FROM me.event_date) = :year)
          AND  (CAST(:month AS int) IS NULL OR EXTRACT(MONTH FROM me.event_date) = :month)
        ORDER  BY me.event_date DESC, cut_amount DESC
    """
    return await _rows(session, sql, {"area": area_code, "ptype": property_type,
                                      "year": year, "month": month})


# ── Graph 3 · FRESH SUPPLY (new listings, SF vs Condo) ────────────────────────
async def fresh_supply(session, area_level, area_code):
    col = _area_col(area_level)
    sql = f"""
        SELECT date_trunc('month', list_date)::date AS month, property_type, count(*) AS new_listings
        FROM   signal.listing_fact
        WHERE  list_date IS NOT NULL AND property_type IN ('SF','CONDO') AND {col} = :area
        GROUP  BY 1,2 ORDER BY 1,2
    """
    return await _rows(session, sql, {"area": area_code})


# ── Graph 3 · HOMES SOLD (closed sales per month) ─────────────────────────────
async def homes_sold(session, area_level, area_code, property_type):
    col = _area_col(area_level)
    sql = f"""
        SELECT date_trunc('month', close_date)::date AS month, count(*) AS closed_sales
        FROM   signal.listing_fact
        WHERE  standard_status = 'Closed' AND property_type = :ptype AND {col} = :area
        GROUP  BY 1 ORDER BY 1
    """
    return await _rows(session, sql, {"ptype": property_type, "area": area_code})


# ── Graph 4 · AVAILABLE INVENTORY (active & in-contract) ──────────────────────
async def available_inventory(session, area_level, area_code, property_type):
    col = _area_col(area_level)
    sql = f"""
        WITH months AS (
            SELECT generate_series(date '2020-01-01', date_trunc('month', now()), interval '1 month')::date AS m
        )
        SELECT mo.m AS month,
               count(*) FILTER (
                   WHERE f.list_date <= (mo.m + interval '1 month - 1 day')
                     AND COALESCE(f.pending_date,f.close_date,date '2999-01-01') > (mo.m + interval '1 month - 1 day')
               ) AS active_listings,
               count(*) FILTER (
                   WHERE f.pending_date <= (mo.m + interval '1 month - 1 day')
                     AND COALESCE(f.close_date,date '2999-01-01') > (mo.m + interval '1 month - 1 day')
               ) AS in_contract
        FROM   months mo
        JOIN   signal.listing_fact f ON f.{col} = :area AND f.property_type = :ptype
        GROUP  BY mo.m ORDER BY mo.m
    """
    return await _rows(session, sql, {"area": area_code, "ptype": property_type})

# ── Graph 4 drill-down · PRICE DISTRIBUTION (available inventory by price band) ─
#  Active listings grouped into price bands. Click a band -> listings(status=active,
#  price_min/price_max) returns the homes in that band.
async def price_distribution(session, area_level, area_code, property_type):
    col = _area_col(area_level)
    sql = f"""
        SELECT band, band_order, min_price, max_price, count(*) AS homes
        FROM (
            SELECT
              CASE
                WHEN list_price < 2000000 THEN 'Under $2M'
                WHEN list_price < 4000000 THEN '$2M-$4M'
                WHEN list_price < 6000000 THEN '$4M-$6M'
                ELSE 'Over $6M'
              END AS band,
              CASE
                WHEN list_price < 2000000 THEN 1
                WHEN list_price < 4000000 THEN 2
                WHEN list_price < 6000000 THEN 3
                ELSE 4
              END AS band_order,
              CASE
                WHEN list_price < 2000000 THEN 0
                WHEN list_price < 4000000 THEN 2000000
                WHEN list_price < 6000000 THEN 4000000
                ELSE 6000000
              END AS min_price,
              CASE
                WHEN list_price < 2000000 THEN 2000000
                WHEN list_price < 4000000 THEN 4000000
                WHEN list_price < 6000000 THEN 6000000
                ELSE NULL
              END AS max_price
            FROM signal.listing_fact
            WHERE standard_status = 'Active' AND property_type = :ptype AND {col} = :area
              AND list_price IS NOT NULL
        ) b
        GROUP BY band, band_order, min_price, max_price
        ORDER BY band_order
    """
    return await _rows(session, sql, {"ptype": property_type, "area": area_code})


# ── Graph 5 · SPEED TO SELL (median DOM, SF vs Condo) ─────────────────────────
async def speed_to_sell(session, area_level, area_code):
    col = _area_col(area_level)
    sql = f"""
        SELECT date_trunc('month', close_date)::date AS month, property_type,
               round(percentile_cont(0.5) WITHIN GROUP (ORDER BY COALESCE(dom_reported,(pending_date-list_date)))::numeric,1) AS median_dom,
               count(*) AS sample_size
        FROM   signal.listing_fact
        WHERE  standard_status = 'Closed' AND property_type IN ('SF','CONDO') AND {col} = :area
          AND  COALESCE(dom_reported,(pending_date-list_date)) IS NOT NULL
        GROUP  BY 1,2 ORDER BY 1,2
    """
    return await _rows(session, sql, {"area": area_code})

# ── Graph 5 drill-down · DOM BREAKDOWN (speed buckets) ─────────────────────────
#  Closed sales grouped into days-on-market buckets. Click a bucket -> listings
#  with dom_min/dom_max returns the homes in that speed range.
async def dom_breakdown(session, area_level, area_code, property_type, year, month):
    col = _area_col(area_level)
    sql = f"""
        SELECT bucket, bucket_order, dom_min, dom_max, count(*) AS homes
        FROM (
            SELECT
              CASE
                WHEN d <= 14 THEN 'Under 2 weeks'
                WHEN d <= 30 THEN '2-4 weeks'
                WHEN d <= 60 THEN '1-2 months'
                ELSE 'Over 2 months'
              END AS bucket,
              CASE
                WHEN d <= 14 THEN 1
                WHEN d <= 30 THEN 2
                WHEN d <= 60 THEN 3
                ELSE 4
              END AS bucket_order,
              CASE
                WHEN d <= 14 THEN 0
                WHEN d <= 30 THEN 15
                WHEN d <= 60 THEN 31
                ELSE 61
              END AS dom_min,
              CASE
                WHEN d <= 14 THEN 14
                WHEN d <= 30 THEN 30
                WHEN d <= 60 THEN 60
                ELSE NULL
              END AS dom_max
            FROM (
                SELECT COALESCE(dom_reported, (close_date - list_date))::int AS d
                FROM   signal.listing_fact
                WHERE  standard_status = 'Closed' AND property_type = :ptype AND {col} = :area
                  AND  COALESCE(dom_reported, (close_date - list_date)) IS NOT NULL
                  AND  (CAST(:year  AS int) IS NULL OR EXTRACT(YEAR  FROM close_date) = :year)
                  AND  (CAST(:month AS int) IS NULL OR EXTRACT(MONTH FROM close_date) = :month)
            ) s
        ) x
        GROUP BY bucket, bucket_order, dom_min, dom_max
        ORDER BY bucket_order
    """
    return await _rows(session, sql, {"ptype": property_type, "area": area_code,
                                      "year": year, "month": month})

# ── Shared drill-down · LISTINGS (status = active|pending|sold|new) ───────────
#  active / pending / sold  -> current state, from listing_fact.standard_status
#  new                      -> the 'new_listing' EVENT (matches the signals feed
#                              listed_for_sale -> new_listing), from market_event.
#  Date filter: sold -> close_date; new -> the new_listing event_date (in LATERAL);
#  active/pending are a current state, so no date filter applies to them.
async def listings(session, area_level, area_code, property_type, status_key, year, month,
                   price_min, price_max, dom_min, dom_max, only_public, limit):
    col = _area_col(area_level)
    sql = f"""
        SELECT f.listing_key_numeric,
               NULL::text                AS address,
               f.city, f.zip_code,
               f.list_price, f.sale_price,
               f.bedrooms_total          AS beds,
               f.bathrooms_total_integer AS baths,
               f.living_sqft             AS sqft,
               f.standard_status         AS status,
               COALESCE(f.dom_reported, (f.pending_date - f.list_date))::int AS dom,
               f.list_date, f.close_date,
               ev.event_date             AS new_listing_date
        FROM   signal.listing_fact f
        LEFT   JOIN LATERAL (
                   SELECT max(me.event_date) AS event_date
                   FROM   signal.market_event me
                   WHERE  me.listing_key_numeric = f.listing_key_numeric
                     AND  me.kind = 'new_listing'
                     AND  (CAST(:year  AS int) IS NULL OR EXTRACT(YEAR  FROM me.event_date) = :year)
                     AND  (CAST(:month AS int) IS NULL OR EXTRACT(MONTH FROM me.event_date) = :month)
               ) ev ON TRUE
        WHERE  f.{col} = :area AND f.property_type = :ptype
          AND  (
                (:status = 'active'  AND f.standard_status = 'Active')  OR
                (:status = 'pending' AND f.standard_status = 'Pending') OR
                (:status = 'sold'    AND f.standard_status = 'Closed')  OR
                (:status = 'new'     AND ev.event_date IS NOT NULL)
               )
          AND  (CAST(:year AS int) IS NULL
                OR (:status = 'sold' AND EXTRACT(YEAR FROM f.close_date) = :year)
                OR  :status IN ('active','pending','new'))
          AND  (CAST(:month AS int) IS NULL
                OR (:status = 'sold' AND EXTRACT(MONTH FROM f.close_date) = :month)
                OR  :status IN ('active','pending','new'))
          -- price band (Graph 4 drill-down): filter on list_price
          AND  (CAST(:price_min AS numeric) IS NULL OR f.list_price >= :price_min)
          AND  (CAST(:price_max AS numeric) IS NULL OR f.list_price <  :price_max)
          -- dom bucket (Graph 5 drill-down): filter on days on market
          AND  (CAST(:dom_min AS int) IS NULL
                OR COALESCE(f.dom_reported, (f.close_date - f.list_date)) >= :dom_min)
          AND  (CAST(:dom_max AS int) IS NULL
                OR COALESCE(f.dom_reported, (f.close_date - f.list_date)) <= :dom_max)
        ORDER  BY COALESCE(ev.event_date, f.close_date, f.list_date) DESC NULLS LAST
        LIMIT  :limit
    """
    return await _rows(session, sql, {"area": area_code, "ptype": property_type,
                                      "status": status_key, "year": year, "month": month,
                                      "price_min": price_min, "price_max": price_max,
                                      "dom_min": dom_min, "dom_max": dom_max,
                                      "limit": limit})


