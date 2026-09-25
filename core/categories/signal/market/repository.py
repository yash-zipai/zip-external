"""
ZipAI — Market (MLS) Data Repository (DAL) — SLIM build.

Raw SQL for the 5 dashboard graphs + two drill-down feeds. Values are bound
parameters; the only interpolated token is the area column name, resolved from
a fixed whitelist (injection-safe). Queries match the frontend SQL 1:1
(city/ptype are parameterized).
"""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_AREA_COLUMNS = {"county": "county", "city": "city", "zip": "zip_code"}


def _area_col(area_level: str) -> str:
    try:
        return _AREA_COLUMNS[area_level]
    except KeyError:
        raise ValueError(f"Unsupported area_level '{area_level}'. Use county | city | zip.")


def _window_start(months: int) -> date:
    """First day of the month (months - 1) before the current one.

    months=1 -> start of this month; months=24 -> this month plus the 23 before it.
    Computed here (not with now() in SQL) so it binds as a plain date the planner
    can use as an index range bound.
    """
    today = date.today()
    y, m = divmod(today.year * 12 + (today.month - 1) - (months - 1), 12)
    return date(y, m + 1, 1)


async def _rows(session: AsyncSession, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    result = await session.execute(text(sql), params)
    return [dict(r._mapping) for r in result.fetchall()]


# ── Graph 1 + Graph 2 + Graph 3 · CLOSED SALES PER MONTH (shared) ─────────────
#  One scan of the area's closed sales feeds five charts: home-price-trend
#  (median_sale_price, sample_size), homes-sold (sample_size), value-per-sqft
#  (median_ppsf, ppsf_sample_size — only sales with living_sqft > 0; months with
#  none are dropped by the service, as the old per-chart WHERE did), buyer-leverage
#  (median_sale_to_list, stl_sample_size) and price-reductions (sold_after_cut,
#  median_cut_pct, cut_sample_size).
#  A "cut" is a final list price below the original one. Cuts deeper than 50% are
#  left out of the cut figures: they are data-entry errors, not negotiations.
async def closed_monthly(session, area_level, area_code, property_type, months):
    col = _area_col(area_level)
    sql = f"""
        SELECT date_trunc('month', close_date)::date AS month,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY sale_price) AS median_sale_price,
               count(*) AS sample_size,
               round((percentile_cont(0.5) WITHIN GROUP (ORDER BY sale_price/NULLIF(living_sqft,0))
                      FILTER (WHERE living_sqft > 0))::numeric,0) AS median_ppsf,
               count(*) FILTER (WHERE living_sqft > 0) AS ppsf_sample_size,
               round((percentile_cont(0.5) WITHIN GROUP (ORDER BY sale_price/list_price)
                      FILTER (WHERE sale_price > 0 AND list_price > 0))::numeric,4) AS median_sale_to_list,
               count(*) FILTER (WHERE sale_price > 0 AND list_price > 0) AS stl_sample_size,
               count(*) FILTER (WHERE list_price < original_list_price
                                  AND list_price >= 0.5*original_list_price) AS sold_after_cut,
               round((100*percentile_cont(0.5) WITHIN GROUP (ORDER BY 1 - list_price/original_list_price)
                      FILTER (WHERE list_price < original_list_price
                                AND list_price >= 0.5*original_list_price))::numeric,1) AS median_cut_pct,
               count(*) FILTER (WHERE original_list_price > 0 AND list_price > 0
                                  AND list_price >= 0.5*original_list_price) AS cut_sample_size
        FROM   signal.listing_fact
        WHERE  standard_status = 'Closed' AND property_type = :ptype AND {col} = :area
          AND  close_date >= :start
        GROUP  BY 1 ORDER BY 1
    """
    return await _rows(session, sql, {"ptype": property_type, "area": area_code,
                                      "start": _window_start(months)})


# ── Graph 2 · PRICE DROP PRESSURE (Negotiating room) ──────────────────────────
async def price_drop_pressure(session, area_level, area_code, property_type, months):
    col = _area_col(area_level)
    sql = f"""
        SELECT month,
               count(*) FILTER (WHERE kind='price_drop')  AS price_drops,
               count(*) FILTER (WHERE kind='new_listing') AS new_listings,
               round(100.0*count(*) FILTER (WHERE kind='price_drop')/NULLIF(count(*) FILTER (WHERE kind='new_listing'),0),1) AS drops_per_100_new
        FROM   signal.market_event
        WHERE  {col} = :area AND property_type = :ptype AND month >= :start
        GROUP  BY month ORDER BY month
    """
    return await _rows(session, sql, {"area": area_code, "ptype": property_type,
                                      "start": _window_start(months)})


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
        ORDER  BY me.event_date DESC, cut_amount DESC, me.src_event_id  -- PK tie-break: stable order
    """
    return await _rows(session, sql, {"area": area_code, "ptype": property_type,
                                      "year": year, "month": month})


# ── Graph 3 · FRESH SUPPLY (new listings, SF vs Condo) ────────────────────────
async def fresh_supply(session, area_level, area_code, months):
    col = _area_col(area_level)
    sql = f"""
        SELECT date_trunc('month', list_date)::date AS month, property_type, count(*) AS new_listings
        FROM   signal.listing_fact
        WHERE  list_date >= :start AND property_type IN ('SF','CONDO') AND {col} = :area
        GROUP  BY 1,2 ORDER BY 1,2
    """
    return await _rows(session, sql, {"area": area_code, "start": _window_start(months)})


# ── Graph 4 · AVAILABLE INVENTORY (active & in-contract) ──────────────────────
#  A listing is "active" at a month-end if list_date <= month_end < COALESCE(pending_date,
#  close_date), and "in contract" if pending_date <= month_end < close_date. Rather than
#  test every listing against every month (months x listings), each listing emits a +1 in
#  the month its interval opens and a -1 in the month it closes; a running sum over months
#  then gives the count at each month-end. The close month is clamped to >= the open month
#  so bad data (pending before list) nets to zero, exactly as the interval test would.
async def available_inventory(session, area_level, area_code, property_type, months):
    col = _area_col(area_level)
    sql = f"""
        WITH f AS (
            SELECT date_trunc('month', list_date)::date                           AS list_m,
                   date_trunc('month', COALESCE(pending_date, close_date))::date  AS off_m,
                   date_trunc('month', pending_date)::date                        AS pend_m,
                   date_trunc('month', close_date)::date                          AS close_m
            FROM   signal.listing_fact
            WHERE  {col} = :area AND property_type = :ptype
        ),
        deltas AS (
            SELECT list_m AS m, 1 AS active, 0 AS in_contract FROM f WHERE list_m IS NOT NULL
            UNION ALL
            SELECT GREATEST(off_m, list_m), -1, 0 FROM f WHERE list_m IS NOT NULL AND off_m IS NOT NULL
            UNION ALL
            SELECT pend_m, 0, 1 FROM f WHERE pend_m IS NOT NULL
            UNION ALL
            SELECT GREATEST(close_m, pend_m), 0, -1 FROM f WHERE pend_m IS NOT NULL AND close_m IS NOT NULL
            UNION ALL
            SELECT generate_series(GREATEST(date '2020-01-01', :start), date_trunc('month', now()), interval '1 month')::date, 0, 0
        ),
        running AS (
            SELECT m,
                   sum(sum(active))      OVER (ORDER BY m) AS active_listings,
                   sum(sum(in_contract)) OVER (ORDER BY m) AS in_contract
            FROM   deltas
            GROUP  BY m
        )
        SELECT m AS month, active_listings::bigint AS active_listings, in_contract::bigint AS in_contract
        FROM   running
        WHERE  m BETWEEN GREATEST(date '2020-01-01', :start) AND date_trunc('month', now())
          AND  EXISTS (SELECT 1 FROM f)
        ORDER  BY m
    """
    return await _rows(session, sql, {"area": area_code, "ptype": property_type,
                                      "start": _window_start(months)})

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
async def speed_to_sell(session, area_level, area_code, months):
    col = _area_col(area_level)
    sql = f"""
        SELECT date_trunc('month', close_date)::date AS month, property_type,
               round(percentile_cont(0.5) WITHIN GROUP (ORDER BY COALESCE(dom_reported,(pending_date-list_date)))::numeric,1) AS median_dom,
               count(*) AS sample_size
        FROM   signal.listing_fact
        WHERE  standard_status = 'Closed' AND property_type IN ('SF','CONDO') AND {col} = :area
          AND  COALESCE(dom_reported,(pending_date-list_date)) IS NOT NULL
          AND  close_date >= :start
        GROUP  BY 1,2 ORDER BY 1,2
    """
    return await _rows(session, sql, {"area": area_code, "start": _window_start(months)})

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
        ORDER  BY COALESCE(ev.event_date, f.close_date, f.list_date) DESC NULLS LAST,
               f.listing_key_numeric  -- PK tie-break: same rows, same order, every call
        LIMIT  :limit
    """
    return await _rows(session, sql, {"area": area_code, "ptype": property_type,
                                      "status": status_key, "year": year, "month": month,
                                      "price_min": price_min, "price_max": price_max,
                                      "dom_min": dom_min, "dom_max": dom_max,
                                      "limit": limit})


