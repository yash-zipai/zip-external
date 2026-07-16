"""
ZipAI — Lifestyle Data Repository (DAL).

Executes raw SQL queries against the ``lifestyle`` schema.
All queries use parameterised binds — never string interpolation.

The SQL mirrors the queries provided by the lifestyle data team, updated so
that ratings/review counts are read from the stored ``lifestyle_place`` columns
(``rating`` / ``reviews_count``) rather than aggregated from the review table,
with pagination added to the list endpoints.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# from logging import get_logger

# logger = get_logger(__name__)


async def get_top_places(
    session: AsyncSession,
    zipcode: str,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """
    Query 1 — Top lifestyle places in a zipcode.

    Optionally filtered by a single category. ``avg_rating`` / ``review_count``
    come from the stored ``lifestyle_place`` columns; ``thumbnail_url`` is the
    first (lowest) image URL for the place.

    Returns:
        (rows, total_count)  where rows is a list of dicts.
    """
    # ``category`` is always sent as a bound parameter, so this is injection-safe.
    if category:
        category_clause = "AND lp.category = :category"
        params: dict[str, Any] = {
            "zip": zipcode,
            "category": category,
            "limit": limit,
            "offset": offset,
        }
    else:
        category_clause = ""
        params = {"zip": zipcode, "limit": limit, "offset": offset}

    count_sql = text(f"""
        SELECT COUNT(DISTINCT lp.place_id)
        FROM lifestyle.lifestyle_place lp
        WHERE lp.zipcode = :zip
          {category_clause}
    """)

    data_sql = text(f"""
        SELECT
            lp.place_id,
            lp.place_name,
            lp.category,
            lp.address                        AS address,
            lp.phone                         AS phone,
            lp.website                        AS website,
            lp.google_maps                    AS google_maps,
            array_to_string(lp.hours, ', ')  AS hours,
            lp.rank                            AS rank,
            lp.rating                         AS avg_rating,
            lp.reviews_count                   AS review_count,
            lp.latitude,
            lp.longitude,
            MIN(li.image_url)  AS thumbnail_url
        FROM lifestyle.lifestyle_place lp
        LEFT JOIN lifestyle.lifestyle_image li  ON li.place_id = lp.place_id
        WHERE lp.zipcode = :zip
          {category_clause}
        GROUP BY
            lp.place_id, lp.place_name, lp.category,
            lp.address, lp.phone, lp.website, lp.google_maps, lp.hours,
            lp.rank, lp.rating, lp.reviews_count,
            lp.latitude, lp.longitude
        ORDER BY lp.category, lp.rank ASC
        LIMIT :limit OFFSET :offset
    """)

    count_result = await session.execute(count_sql, params)
    total = count_result.scalar() or 0

    result = await session.execute(data_sql, params)
    rows = [dict(row._mapping) for row in result.fetchall()]

    # logger.debug("repo_get_top_places", zipcode=zipcode, category=category, total=total)
    return rows, total


async def get_breakdown(
    session: AsyncSession,
    zipcode: str,
) -> list[dict[str, Any]]:
    """
    Query 2 — Lifestyle breakdown by category for a zipcode.

    Returns one row per category with the average stored rating, the number
    of places, and the total review count, ordered by average rating desc.

    Column aliases (``category`` / ``total_places`` / ``city``) are kept to match
    what ``LifestyleService.get_breakdown`` consumes. ``total_reviews`` is
    COALESCEd to 0 so a category with no reviews returns 0 rather than NULL.
    """
    sql = text("""
        SELECT
            zipcode,
            city,
            category,
            ROUND(AVG(rating)::numeric, 2)        AS avg_rating,
            COUNT(place_id)                       AS total_places,
            SUM(reviews_count)      AS total_reviews
        FROM lifestyle.lifestyle_place
        WHERE zipcode = :zip
        GROUP BY zipcode, city, category
        ORDER BY avg_rating DESC
    """)

    result = await session.execute(sql, {"zip": zipcode})
    rows = [dict(row._mapping) for row in result.fetchall()]

    # logger.debug("repo_get_breakdown", zipcode=zipcode, categories=len(rows))
    return rows


async def get_index_scores(
    session: AsyncSession,
    zipcode: str,
) -> dict[str, Any] | None:
    """
    Query 3 — Lifestyle index scores (ZIP aggregate) for a zipcode.

    Returns a single aggregate row for the ZIP, or None if the ZIP has no
    lifestyle places. ``lifestyle_index_score`` (0–100) is a derived metric:
        70% weight on average rating (normalised against 5.0)
      + 30% weight on place density (capped at 50 places).
    Adjust the weighting/formula here if the product spec changes.
    """
    sql = text("""
        SELECT
            lp.zipcode,
            MAX(lp.city)                          AS city,
            COUNT(*)                              AS total_places,
            ROUND(AVG(lp.rating)::numeric, 2)     AS overall_avg_rating,
            SUM(lp.reviews_count)    AS total_reviews,
            CASE  WHEN AVG(lp.rating) IS NULL THEN NULL
           ELSE LEAST(
                 ROUND(
                     ((AVG(lp.rating) / 5.0) * 70)
                     + (LEAST(COUNT(*), 50) / 50.0 * 30)
                 , 0),
                 100
             )
         END      AS lifestyle_index_score
        FROM lifestyle.lifestyle_place lp
        WHERE lp.zipcode = :zip
        GROUP BY lp.zipcode
    """)

    result = await session.execute(sql, {"zip": zipcode})
    row = result.fetchone()
    if row is None:
        return None

    # logger.debug("repo_get_index_scores", zipcode=zipcode)
    return dict(row._mapping)


async def get_map_pins(
    session: AsyncSession,
    zipcode: str | None = None,
    layers: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """
    Query 4 — Lifestyle place map pins.

    Returns minimal place locations for map display, optionally filtered by
    zipcode, layer (category) and/or a map bounding box. Only places with BOTH
    latitude and longitude are returned — a pin without coordinates can't be
    placed on a map. ``avg_rating`` (stored) and ``thumbnail_url`` (first image)
    are included for pin previews.
    """
    # A pin must have coordinates, so these conditions are always applied.
    conditions: list[str] = ["lp.latitude IS NOT NULL", "lp.longitude IS NOT NULL"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    if zipcode:
        conditions.append("lp.zipcode = :zip")
        params["zip"] = zipcode

    if layers:
        # layers can be comma-separated, e.g. "entertainment,fitness".
        # Each value is bound as its own parameter (injection-safe).
        layer_list = [l.strip() for l in layers.split(",") if l.strip()]
        if layer_list:
            placeholders = ", ".join(f":layer_{i}" for i in range(len(layer_list)))
            conditions.append(f"lp.category IN ({placeholders})")
            for i, layer in enumerate(layer_list):
                params[f"layer_{i}"] = layer

    if bbox:
        # bbox = (west, south, east, north) → longitude/latitude ranges.
        # Wrapped so the OR-free AND chain can't be broken by precedence.
        west, south, east, north = bbox
        conditions.append("lp.longitude BETWEEN :west AND :east")
        conditions.append("lp.latitude  BETWEEN :south AND :north")
        params.update(west=west, east=east, south=south, north=north)

    where_clause = "WHERE " + " AND ".join(conditions)

    count_sql = text(f"""
        SELECT COUNT(DISTINCT lp.place_id)
        FROM lifestyle.lifestyle_place lp
        {where_clause}
    """)

    data_sql = text(f"""
        SELECT
            lp.place_id,
            lp.place_name,
            lp.category,
            lp.latitude,
            lp.longitude,
            lp.rating    AS avg_rating,
            MIN(li.image_url)  AS thumbnail_url
        FROM lifestyle.lifestyle_place lp
        LEFT JOIN lifestyle.lifestyle_image li  ON li.place_id = lp.place_id
        {where_clause}
        GROUP BY
            lp.place_id, lp.place_name, lp.category,
            lp.latitude, lp.longitude, lp.rating, lp.reviews_count
        ORDER BY lp.rating DESC NULLS LAST, lp.reviews_count DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """)

    count_result = await session.execute(count_sql, params)
    total = count_result.scalar() or 0

    result = await session.execute(data_sql, params)
    rows = [dict(row._mapping) for row in result.fetchall()]

    # logger.debug("repo_get_map_pins", zipcode=zipcode, layers=layers, total=total)
    return rows, total
