"""
ZipAI — Market (MLS) Data Repository (DAL).

Executes raw SQL against the ``signal`` schema (signal.listing_fact) and, for
price reductions, public.zipdata_idxlistingpriceevent. All values are passed as
bound parameters — never string-interpolated. The only interpolated token is the
area *column name*, which is resolved from a fixed whitelist (injection-safe).

These are the 10 market-analysis charts + the local summary table, ported from
market_chart_queries.sql.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# area_level -> physical column on signal.listing_fact (whitelist: safe to inline)
_AREA_COLUMNS = {"county": "county", "city": "city", "zip": "zip_code"}


def _area_col(area_level: str) -> str:
    try:
        return _AREA_COLUMNS[area_level]
    except KeyError:
        raise ValueError(f"Unsupported area_level '{area_level}'. Use county | city | zip.")


async def _rows(session: AsyncSession, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    result = await session.execute(text(sql), params)
    return [dict(r._mapping) for r in result.fetchall()]


# ── 1. Median sale price over time ────────────────────────────────────────────


async def median_sale_price(session, area_level, area_code, property_type):
    col = _area_col(area_level)
    sql = f"""
        SELECT date_trunc('month', close_date)::date AS month,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY sale_price) AS median_sale_price,
               count(*) AS closed_sales
        FROM   signal.listing_fact
        WHERE  standard_status = 'Closed'
          AND  property_type = :ptype
          AND  {col} = :area
        GROUP  BY 1 ORDER BY 1
    """
    return await _rows(session, sql, {"ptype": property_type, "area": area_code})


# ── 2. Median price YoY % (SF vs Condo) ───────────────────────────────────────


async def median_price_yoy(session, area_level, area_code):
    col = _area_col(area_level)
    sql = f"""
        WITH m AS (
            SELECT date_trunc('month', close_date)::date AS month, property_type,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY sale_price) AS med
            FROM   signal.listing_fact
            WHERE  standard_status = 'Closed'
              AND  property_type IN ('SF','CONDO')
              AND  {col} = :area
            GROUP  BY 1, 2
        )
        SELECT month, property_type,
               round(((med / NULLIF(lag(med,12) OVER (PARTITION BY property_type ORDER BY month),0) - 1) * 100)::numeric, 1) AS yoy_pct
        FROM   m ORDER BY property_type, month
    """
    return await _rows(session, sql, {"area": area_code})


# ── 3. Price per sq ft by month ───────────────────────────────────────────────


async def ppsf_by_month(session, area_level, area_code, property_type):
    col = _area_col(area_level)
    sql = f"""
        SELECT date_trunc('month', close_date)::date AS month,
               round(percentile_cont(0.5) WITHIN GROUP (ORDER BY sale_price / NULLIF(living_sqft,0))::numeric, 0) AS median_ppsf
        FROM   signal.listing_fact
        WHERE  standard_status = 'Closed'
          AND  property_type = :ptype
          AND  {col} = :area
          AND  living_sqft > 0
        GROUP  BY 1 ORDER BY 1
    """
    return await _rows(session, sql, {"ptype": property_type, "area": area_code})


# ── 4. Median price per sq ft by city (ranked) ────────────────────────────────


async def ppsf_by_city(session, area_level, area_code, property_type, trailing_12m: bool):
    col = _area_col(area_level)
    window_clause = (
        "close_date >= now() - interval '12 months'"
        if trailing_12m else
        "close_date >= date_trunc('month', now())"
    )
    sql = f"""
        SELECT city,
               round(percentile_cont(0.5) WITHIN GROUP (ORDER BY sale_price / NULLIF(living_sqft,0))::numeric, 0) AS median_ppsf,
               round(percentile_cont(0.5) WITHIN GROUP (ORDER BY living_sqft)::numeric, 0) AS median_sqft,
               count(*) AS closed
        FROM   signal.listing_fact
        WHERE  standard_status = 'Closed'
          AND  property_type = :ptype
          AND  {col} = :area
          AND  living_sqft > 0
          AND  {window_clause}
        GROUP  BY city ORDER BY median_ppsf DESC
    """
    return await _rows(session, sql, {"ptype": property_type, "area": area_code})


# ── 5. Closed sales per month ─────────────────────────────────────────────────


async def closed_sales(session, area_level, area_code, property_type):
    col = _area_col(area_level)
    sql = f"""
        SELECT date_trunc('month', close_date)::date AS month, count(*) AS closed_sales
        FROM   signal.listing_fact
        WHERE  standard_status = 'Closed'
          AND  property_type = :ptype
          AND  {col} = :area
        GROUP  BY 1 ORDER BY 1
    """
    return await _rows(session, sql, {"ptype": property_type, "area": area_code})


# ── 6. New listings per month (SF vs Condo) ───────────────────────────────────


async def new_listings(session, area_level, area_code):
    col = _area_col(area_level)
    sql = f"""
        SELECT date_trunc('month', list_date)::date AS month, property_type, count(*) AS new_listings
        FROM   signal.listing_fact
        WHERE  list_date IS NOT NULL
          AND  property_type IN ('SF','CONDO')
          AND  {col} = :area
        GROUP  BY 1, 2 ORDER BY 1, 2
    """
    return await _rows(session, sql, {"area": area_code})


# ── 7. Active & in-contract inventory (point-in-time) ─────────────────────────


async def inventory(session, area_level, area_code, property_type):
    col = _area_col(area_level)
    sql = f"""
        WITH months AS (
            SELECT generate_series(date '2020-01-01', date_trunc('month', now()), interval '1 month')::date AS m
        )
        SELECT mo.m AS month,
               count(*) FILTER (
                   WHERE f.list_date <= (mo.m + interval '1 month - 1 day')
                     AND COALESCE(f.pending_date, f.close_date, date '2999-01-01') > (mo.m + interval '1 month - 1 day')
               ) AS active_listings,
               count(*) FILTER (
                   WHERE f.pending_date <= (mo.m + interval '1 month - 1 day')
                     AND COALESCE(f.close_date, date '2999-01-01') > (mo.m + interval '1 month - 1 day')
               ) AS in_contract
        FROM   months mo
        JOIN   signal.listing_fact f ON f.{col} = :area AND f.property_type = :ptype
        GROUP  BY mo.m ORDER BY mo.m
    """
    return await _rows(session, sql, {"ptype": property_type, "area": area_code})


# ── 8. Days on market (SF vs Condo) ───────────────────────────────────────────


async def days_on_market(session, area_level, area_code):
    col = _area_col(area_level)
    sql = f"""
        SELECT date_trunc('month', close_date)::date AS month, property_type,
               round(percentile_cont(0.5) WITHIN GROUP (ORDER BY COALESCE(dom_reported, (pending_date - list_date)))::numeric, 1) AS median_dom
        FROM   signal.listing_fact
        WHERE  standard_status = 'Closed'
          AND  property_type IN ('SF','CONDO')
          AND  {col} = :area
          AND  COALESCE(dom_reported, (pending_date - list_date)) IS NOT NULL
        GROUP  BY 1, 2 ORDER BY 1, 2
    """
    return await _rows(session, sql, {"area": area_code})


# ── 9a. Sale-to-list ratio ────────────────────────────────────────────────────


async def sale_to_list(session, area_level, area_code, property_type):
    col = _area_col(area_level)
    sql = f"""
        SELECT date_trunc('month', close_date)::date AS month,
               round((avg(sale_price / NULLIF(list_price,0)) * 100)::numeric, 1) AS sale_to_list_pct
        FROM   signal.listing_fact
        WHERE  standard_status = 'Closed'
          AND  property_type = :ptype
          AND  {col} = :area
        GROUP  BY 1 ORDER BY 1
    """
    return await _rows(session, sql, {"ptype": property_type, "area": area_code})


# ── 9b. Price reductions per month (event table, joined for area) ─────────────


async def price_reductions(session, area_level, area_code):
    col = _area_col(area_level)
    sql = f"""
        SELECT date_trunc('month', pe.event_date)::date AS month, count(*) AS price_reductions
        FROM   public.zipdata_idxlistingpriceevent pe
        JOIN   signal.listing_fact f ON f.listing_key_numeric = pe.listing_key_numeric
        WHERE  pe.event_type = 'price_change'
          AND  pe.price < pe.prior_price
          AND  f.{col} = :area
        GROUP  BY 1 ORDER BY 1
    """
    return await _rows(session, sql, {"area": area_code})


# ── 10. Sales/listings by price segment, by city ──────────────────────────────


async def segments_by_city(session, area_level, area_code, property_type, status: str):
    """status: 'closed' | 'active' | 'new'."""
    col = _area_col(area_level)
    if status == "active":
        status_clause = "standard_status = 'Active'"
        price_col = "list_price"
        date_clause = ""
    elif status == "new":
        status_clause = "list_date >= date_trunc('month', now())"
        price_col = "list_price"
        date_clause = ""
    else:  # closed
        status_clause = "standard_status = 'Closed'"
        price_col = "sale_price"
        date_clause = "AND close_date >= date_trunc('month', now())"

    sql = f"""
        SELECT city,
               CASE width_bucket({price_col}, ARRAY[1000000,1500000,2000000,3000000,4000000,5000000])
                    WHEN 0 THEN '< $1M'  WHEN 1 THEN '$1M-$1.5M' WHEN 2 THEN '$1.5M-$2M'
                    WHEN 3 THEN '$2M-$3M' WHEN 4 THEN '$3M-$4M'   WHEN 5 THEN '$4M-$5M'
                    ELSE '$5M+' END AS price_segment,
               count(*) AS count
        FROM   signal.listing_fact
        WHERE  {status_clause}
          AND  property_type = :ptype
          AND  {col} = :area
          {date_clause}
        GROUP  BY city, price_segment ORDER BY city, price_segment
    """
    return await _rows(session, sql, {"ptype": property_type, "area": area_code})


# ── + Local summary table ─────────────────────────────────────────────────────


async def summary(session, area_level, area_code, property_type):
    col = _area_col(area_level)
    sql = f"""
        WITH sold12 AS (
            SELECT city, sale_price, list_price, close_date,
                   COALESCE(dom_reported, (pending_date - list_date)) AS dom
            FROM   signal.listing_fact
            WHERE  standard_status='Closed' AND property_type=:ptype AND {col}=:area
              AND  close_date >= date_trunc('month', now()) - interval '12 months'
        ),
        active_now AS (
            SELECT city, count(*) AS active_cnt
            FROM   signal.listing_fact
            WHERE  standard_status='Active' AND property_type=:ptype AND {col}=:area
            GROUP  BY city
        ),
        appr AS (
            SELECT city,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY sale_price)
                     FILTER (WHERE date_trunc('month',close_date)=date_trunc('month',now())) AS med_now,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY sale_price)
                     FILTER (WHERE date_trunc('month',close_date)=date_trunc('month',now()-interval '12 months')) AS med_prev
            FROM sold12 GROUP BY city
        )
        SELECT s.city,
               round(avg(s.sale_price / NULLIF(s.list_price,0))::numeric * 100) AS sale_to_list_pct,
               round((count(*) FILTER (WHERE date_trunc('month',s.close_date)=date_trunc('month',now())))::numeric
                     / NULLIF(a.active_cnt,0) * 100) AS absorption_pct,
               round(avg((s.sale_price > s.list_price)::int)::numeric * 100) AS overbid_pct,
               round(percentile_cont(0.5) WITHIN GROUP (ORDER BY s.dom))::numeric AS dom,
               round(((ap.med_now / NULLIF(ap.med_prev,0) - 1) * 100)::numeric, 1) AS appreciation_12mo_pct
        FROM   sold12 s
        LEFT   JOIN active_now a USING (city)
        LEFT   JOIN appr       ap USING (city)
        GROUP  BY s.city, a.active_cnt, ap.med_now, ap.med_prev
        ORDER  BY s.city
    """
    return await _rows(session, sql, {"ptype": property_type, "area": area_code})