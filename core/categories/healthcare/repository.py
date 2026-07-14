"""
ZipAI — Healthcare Data Repository (DAL).

Executes raw SQL queries against the ``healthcare`` schema.
All queries use parameterised binds — never string interpolation.
The SQL is kept close to the original queries provided by the
healthcare data team, with pagination added.

NULL-safety: aggregate columns are wrapped in COALESCE(..., 0) so that
providers/zipcodes with no matching reviews return 0 instead of NULL,
which the frontend was dropping.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# from logging import get_logger
# logger = get_logger(__name__)

# ── Valid categories (whitelist) ──────────────────────────────────────────────
VALID_CATEGORIES = frozenset(
    {"hospitals", "urgent_care", "pediatrics", "dentists", "clinics", "pharmacies", "mental_health"}
)


async def get_top_places(
    session: AsyncSession,
    zipcode: str,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """
    Query 1 — Top healthcare providers in a zipcode.

    Returns:
        (rows, total_count)  where rows is a list of dicts.
    """
    # Build category filter
    if category and category in VALID_CATEGORIES:
        category_clause = "AND p.category = :category"
        params: dict[str, Any] = {"zip": zipcode, "category": category, "limit": limit, "offset": offset}
    else:
        category_clause = """AND p.category IN (
            'hospitals', 'urgent_care', 'pediatrics',
            'dentists', 'clinics', 'pharmacies'
        )"""
        params = {"zip": zipcode, "limit": limit, "offset": offset}

    # Count query (for pagination metadata)
    count_sql = text(f"""
        SELECT COUNT(DISTINCT p.provider_id)
        FROM healthcare.healthcare_provider p
        WHERE p.zipcode = :zip
          {category_clause}
    """)

    # Main query — matches the provided SQL with pagination
    data_sql = text(f"""
        SELECT
            p.provider_id,
            p.provider_name,
            p.category,
            p.address,
            p.phone,
            p.website,
            p.google_maps,
            p.rank,
            COALESCE(ROUND(AVG(r.review_rating), 2), 0)   AS avg_rating,
            COUNT(r.review_id)                            AS review_count,
            p.latitude,
            p.longitude,
            COALESCE(MIN(i.image_url), '')                AS thumbnail_url
        FROM healthcare.healthcare_provider p
        LEFT JOIN healthcare.healthcare_reviews r  ON r.provider_id = p.provider_id
        LEFT JOIN healthcare.healthcare_images  i  ON i.provider_id = p.provider_id
        WHERE p.zipcode = :zip
          {category_clause}
        GROUP BY
            p.provider_id, p.provider_name, p.category,
            p.address, p.phone, p.website, p.google_maps, p.rank,
            p.latitude, p.longitude
        ORDER BY p.category, p.rank ASC
        LIMIT :limit OFFSET :offset
    """)

    count_result = await session.execute(count_sql, params)
    total = count_result.scalar() or 0

    result = await session.execute(data_sql, params)
    rows = [dict(row._mapping) for row in result.fetchall()]

    # logger.debug(
    #     "repo_get_top_places",
    #     zipcode=zipcode,
    #     category=category,
    #     total=total,
    #     returned=len(rows),
    # )
    return rows, total


async def get_breakdown(
    session: AsyncSession,
    zipcode: str,
) -> list[dict[str, Any]]:
    """
    Query 2 — Healthcare breakdown by bucket for a zipcode.

    Buckets:
      hospitals + urgent_care → hospital_urgent
      pediatrics              → pediatrics
      dentists                → dental
      clinics + pharmacies    → primary_care
    """
    sql = text("""
        SELECT
            bucket,
            COUNT(DISTINCT p.provider_id)                               AS provider_count,
            COALESCE(ROUND(AVG(r.review_rating)::numeric, 2), 0)        AS avg_rating,
            COUNT(r.review_id)                                          AS total_reviews,
            COALESCE(
                ROUND(
                    (AVG(r.review_rating) * LN(NULLIF(COUNT(r.review_id), 0)))::numeric,
                    2
                ), 0
            )                                                           AS score
        FROM (
            SELECT
                provider_id,
                CASE category
                    WHEN 'hospitals'     THEN 'hospital_urgent'
                    WHEN 'urgent_care'   THEN 'hospital_urgent'
                    WHEN 'pediatrics'    THEN 'pediatrics'
                    WHEN 'dentists'      THEN 'dental'
                    WHEN 'clinics'       THEN 'primary_care'
                    WHEN 'pharmacies'    THEN 'primary_care'
                    WHEN 'mental_health' THEN 'mental_health'
                END AS bucket
            FROM healthcare.healthcare_provider
            WHERE zipcode = :zip
        ) p
        LEFT JOIN healthcare.healthcare_reviews r ON r.provider_id = p.provider_id
        WHERE bucket IS NOT NULL
        GROUP BY bucket
        ORDER BY score DESC
    """)

    result = await session.execute(sql, {"zip": zipcode})
    rows = [dict(row._mapping) for row in result.fetchall()]

    # logger.debug("repo_get_breakdown", zipcode=zipcode, buckets=len(rows))
    return rows


async def get_index_scores(
    session: AsyncSession,
    zipcode: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """
    Query 3 — Healthcare index score per zipcode.

    If *zipcode* is provided, filters to that single zip.
    Otherwise returns all zipcodes sorted by score descending.
    """
    where_clause = "WHERE p.zipcode = :zip" if zipcode else ""
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if zipcode:
        params["zip"] = zipcode

    count_sql = text(f"""
        SELECT COUNT(DISTINCT (p.zipcode, p.city))
        FROM healthcare.healthcare_provider p
        {where_clause}
    """)

    data_sql = text(f"""
        SELECT
            p.zipcode,
            p.city,
            COUNT(DISTINCT p.provider_id)                               AS total_providers,
            COALESCE(ROUND(AVG(r.review_rating)::numeric, 2), 0)        AS overall_avg_rating,
            COUNT(r.review_id)                                          AS total_reviews,
            LEAST(ROUND(
		     (AVG(r.review_rating) * LN(NULLIF(COUNT(r.review_id), 0)))::numeric,
		  2) ,100)  AS healthcare_index_score
        FROM healthcare.healthcare_provider p
        LEFT JOIN healthcare.healthcare_reviews r ON r.provider_id = p.provider_id
        {where_clause}
        GROUP BY p.zipcode, p.city
        ORDER BY healthcare_index_score DESC
        LIMIT :limit OFFSET :offset
    """)

    count_result = await session.execute(count_sql, params)
    total = count_result.scalar() or 0

    result = await session.execute(data_sql, params)
    rows = [dict(row._mapping) for row in result.fetchall()]

    # logger.debug(
    #     "repo_get_index_scores",
    #     zipcode=zipcode,
    #     total=total,
    #     returned=len(rows),
    # )
    return rows, total


async def get_map_pins(
    session: AsyncSession,
    zipcode: str | None = None,
    layers: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """
    Query — Healthcare provider map pins.

    Returns minimal provider locations for map display, optionally filtered
    by zipcode, layer (category) and/or a map bounding box.

    Only providers with BOTH latitude and longitude are returned — a pin
    without coordinates can't be placed on a map. ``rating`` is the stored
    per-provider average, surfaced as ``avg_rating``.
    """
    # A pin must have coordinates, so these conditions are always applied.
    conditions: list[str] = ["p.latitude IS NOT NULL", "p.longitude IS NOT NULL"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    if zipcode:
        conditions.append("p.zipcode = :zip")
        params["zip"] = zipcode

    if layers:
        # layers can be comma-separated, e.g. "hospitals,dentists"
        layer_list = [l.strip() for l in layers.split(",") if l.strip() in VALID_CATEGORIES]
        if layer_list:
            placeholders = ", ".join(f":layer_{i}" for i in range(len(layer_list)))
            conditions.append(f"p.category IN ({placeholders})")
            for i, layer in enumerate(layer_list):
                params[f"layer_{i}"] = layer

    if bbox:
        # bbox = (west, south, east, north) → longitude/latitude ranges
        west, south, east, north = bbox
        conditions.append("p.longitude BETWEEN :west AND :east")
        conditions.append("p.latitude  BETWEEN :south AND :north")
        params.update(west=west, east=east, south=south, north=north)

    where_clause = "WHERE " + " AND ".join(conditions)

    count_sql = text(f"""
        SELECT COUNT(DISTINCT p.provider_id)
        FROM healthcare.healthcare_provider p
        {where_clause}
    """)

    data_sql = text(f"""
        SELECT
            p.provider_id,
            p.provider_name,
            p.latitude,
            p.longitude,
            COALESCE(p.rating, 0)   AS avg_rating,
            p.google_maps
        FROM healthcare.healthcare_provider p
        {where_clause}
        ORDER BY p.rating DESC NULLS LAST, p.reviews_count DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """)

    count_result = await session.execute(count_sql, params)
    total = count_result.scalar() or 0

    result = await session.execute(data_sql, params)
    rows = [dict(row._mapping) for row in result.fetchall()]

    # logger.debug(
    #     "repo_get_map_pins",
    #     zipcode=zipcode,
    #     layers=layers,
    #     total=total,
    #     returned=len(rows),
    # )
    return rows, total
