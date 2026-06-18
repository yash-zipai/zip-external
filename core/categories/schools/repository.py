"""
ZipAI — Schools Data Repository (DAL).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_schools_k12(
    session: AsyncSession,
    zipcode: str,
) -> list[dict[str, Any]]:
    sql = text("""
        SELECT nces_id, school_name, school_category, school_type, level_type,
               low_grade, high_grade, enrollment, teachers_fte,
               rank_in_zip, latitude, longitude, address, phone
        FROM schools.schools_details
        WHERE zipcode = :zip
          AND school_category IN ('public_k12', 'private_k12')
        ORDER BY school_category, rank_in_zip;
    """)
    result = await session.execute(sql, {"zip": zipcode})
    return [dict(row._mapping) for row in result.fetchall()]


async def get_schools_higher_ed(
    session: AsyncSession,
    zipcode: str,
) -> list[dict[str, Any]]:
    sql = text("""
        SELECT nces_id, school_name, school_type, enrollment,
               admission_rate, completion_rate, tuition_in, tuition_out,
               school_url, rank_in_zip, latitude, longitude, address, phone
        FROM schools.schools_details
        WHERE zipcode = :zip
          AND school_category = 'college'
        ORDER BY rank_in_zip;
    """)
    result = await session.execute(sql, {"zip": zipcode})
    return [dict(row._mapping) for row in result.fetchall()]


async def get_education_breakdown(
    session: AsyncSession,
    zipcode: str,
) -> list[dict[str, Any]]:
    sql = text("""
        WITH state_ratio AS (
            SELECT school_category,
                   percentile_cont(0.5) WITHIN GROUP (
                       ORDER BY enrollment::numeric / NULLIF(teachers_fte, 0)
                   ) AS median_ratio
            FROM schools.schools_details
            WHERE teachers_fte > 0
            GROUP BY school_category
        )
        SELECT d.school_category,
               count(*)                                   AS school_count,
               sum(d.enrollment)                          AS total_students,
               round(avg(d.enrollment::numeric
                         / NULLIF(d.teachers_fte, 0)), 1) AS avg_students_per_teacher,
               round(greatest(0, least(100,
                     100 * sr.median_ratio
                         / NULLIF(avg(d.enrollment::numeric
                                      / NULLIF(d.teachers_fte, 0)), 0)
               )))                                        AS education_index
        FROM schools.schools_details d
        JOIN state_ratio sr USING (school_category)
        WHERE d.zipcode = :zip
        GROUP BY d.school_category, sr.median_ratio
        ORDER BY d.school_category;
    """)
    result = await session.execute(sql, {"zip": zipcode})
    return [dict(row._mapping) for row in result.fetchall()]


async def get_school_details(
    session: AsyncSession,
    nces_id: str,
) -> dict[str, Any] | None:
    sql = text("""
        SELECT nces_id, school_name, school_category, school_type, level_type,
               address, city, state, zipcode, phone, school_url,
               low_grade, high_grade, enrollment, teachers_fte,
               round(enrollment::numeric / NULLIF(teachers_fte, 0), 1)
                    AS students_per_teacher,
               admission_rate, completion_rate, tuition_in, tuition_out,
                rank_in_zip, latitude, longitude, data_year
        FROM schools.schools_details
        WHERE nces_id = :nces_id;
    """)
    result = await session.execute(sql, {"nces_id": nces_id})
    row = result.fetchone()
    if row:
        return dict(row._mapping)
    return None


async def get_map_pins(
    session: AsyncSession,
    bbox: tuple[float, float, float, float] | None = None,
    limit: int = 2000,
) -> list[dict[str, Any]]:
    conditions = ["latitude IS NOT NULL", "longitude IS NOT NULL"]
    params: dict[str, Any] = {"limit": limit}

    if bbox:
        west, south, east, north = bbox
        conditions.append("latitude BETWEEN :south AND :north")
        conditions.append("longitude BETWEEN :west AND :east")
        params.update(west=west, south=south, east=east, north=north)

    where_clause = "WHERE " + " AND ".join(conditions)

    sql = text(f"""
        SELECT nces_id, school_name, school_category, latitude, longitude
        FROM schools.schools_details
        {where_clause}
        LIMIT :limit;
    """)
    result = await session.execute(sql, params)
    return [dict(row._mapping) for row in result.fetchall()]
