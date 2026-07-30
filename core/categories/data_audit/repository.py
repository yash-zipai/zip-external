"""
Data Audit — Repository (raw SQL over the real `zipdata` category schemas).

All table names are FULLY QUALIFIED (schema.table), so these queries do not
depend on the session's search_path — one schema session can serve every
endpoint.

Category -> main table used here (swap to a *_v1 / *_v2 table only if that is
your live one):
    cost_of_living  -> cost_of_living.col_snapshot   (zipcode, inserted_at, snapshot_date)
    crime           -> crime.crime_history           (zipcode, year, current_flag='Y')
                       crime.stg_crime_raw.load_ts    (crime's ingest timestamp)
    employer        -> employer.zip_snapshots        (zipcode, created_at, zip_snapshot_year)
    healthcare      -> healthcare.healthcare_provider (zipcode, created_at)
    lifestyle       -> lifestyle.lifestyle_place      (zipcode, created_at, updated_at)
    schools         -> schools.schools_details        (zipcode, loaded_at, data_year)

Table names cannot be bind parameters, so the per-category coverage subqueries
live in a fixed whitelist below (constant SQL, no user input). Only VALUES
(:days, :limit, :category) are ever bound.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# The six category coverage subqueries — each returns DISTINCT zipcodes we hold
# data for in that category. Constant strings, safe to interpolate.
# zipcode is CAST to text everywhere so the UNION across tables (whose zipcode
# columns may be int / varchar / text) and the join against
# analytics.user_events.zipcode (TEXT) never hit a type mismatch.
COVERAGE_SUBQUERIES: dict[str, str] = {
    "cost_of_living": "SELECT DISTINCT zipcode::text AS zipcode FROM cost_of_living.col_snapshot",
    "crime":          "SELECT DISTINCT zipcode::text AS zipcode FROM crime.crime_history WHERE current_flag = 'Y'",
    "employer":       "SELECT DISTINCT zipcode::text AS zipcode FROM employer.zip_snapshots",
    "healthcare":     "SELECT DISTINCT zipcode::text AS zipcode FROM healthcare.healthcare_provider",
    "lifestyle":      "SELECT DISTINCT zipcode::text AS zipcode FROM lifestyle.lifestyle_place",
    "schools":        "SELECT DISTINCT zipcode::text AS zipcode FROM schools.schools_details",
}

# (category, zipcode) pairs we hold — used to make coverage-gaps category-aware
# so a zip that has healthcare data but no crime data is flagged ONLY as a
# crime gap, not as "uncovered" overall.
COVERAGE_PAIRS_UNION = " UNION ALL ".join(
    f"SELECT '{cat}' AS category, zipcode FROM ({sub}) c_{i}"
    for i, (cat, sub) in enumerate(COVERAGE_SUBQUERIES.items())
)


async def _rows(session: AsyncSession, sql: str, params: dict | None = None) -> list[dict]:
    res = await session.execute(text(sql), params or {})
    return [dict(r._mapping) for r in res.fetchall()]


async def _one(session: AsyncSession, sql: str, params: dict | None = None) -> dict:
    res = await session.execute(text(sql), params or {})
    row = res.fetchone()
    return dict(row._mapping) if row else {}


# ── 1) Ingestion activity — new rows per day, per category ────────────────────
async def ingestion_activity(session: AsyncSession, days: int) -> list[dict]:
    return await _rows(session, """
        SELECT day, category, SUM(cnt) AS ingested
        FROM (
            SELECT to_char(date_trunc('day', inserted_at), 'YYYY-MM-DD') AS day,
                   'cost_of_living' AS category, COUNT(*) AS cnt
            FROM cost_of_living.col_snapshot
            WHERE inserted_at >= now() - (:days * interval '1 day') GROUP BY 1
          UNION ALL
            SELECT to_char(date_trunc('day', load_ts), 'YYYY-MM-DD'), 'crime', COUNT(*)
            FROM crime.stg_crime_raw
            WHERE load_ts >= now() - (:days * interval '1 day') GROUP BY 1
          UNION ALL
            SELECT to_char(date_trunc('day', created_at), 'YYYY-MM-DD'), 'employer', COUNT(*)
            FROM employer.zip_snapshots
            WHERE created_at >= now() - (:days * interval '1 day') GROUP BY 1
          UNION ALL
            SELECT to_char(date_trunc('day', created_at), 'YYYY-MM-DD'), 'healthcare', COUNT(*)
            FROM healthcare.healthcare_provider
            WHERE created_at >= now() - (:days * interval '1 day') GROUP BY 1
          UNION ALL
            SELECT to_char(date_trunc('day', created_at), 'YYYY-MM-DD'), 'lifestyle', COUNT(*)
            FROM lifestyle.lifestyle_place
            WHERE created_at >= now() - (:days * interval '1 day') GROUP BY 1
          UNION ALL
            SELECT to_char(date_trunc('day', loaded_at), 'YYYY-MM-DD'), 'schools', COUNT(*)
            FROM schools.schools_details
            WHERE loaded_at >= now() - (:days * interval '1 day') GROUP BY 1
        ) t
        GROUP BY day, category
        ORDER BY day, category
    """, {"days": days})


# ── 2) Freshness — last ingested + latest data period + stale flag ────────────
async def freshness(session: AsyncSession, stale_days: int) -> list[dict]:
    return await _rows(session, """
        SELECT 'cost_of_living' AS dataset,
               to_char(MAX(inserted_at), 'YYYY-MM-DD HH24:MI') AS last_ingested,
               MAX(snapshot_date)::text AS latest_period,
               (MAX(inserted_at) < now() - (:days * interval '1 day')) AS is_stale
        FROM cost_of_living.col_snapshot
        UNION ALL
        SELECT 'crime',
               to_char((SELECT MAX(load_ts) FROM crime.stg_crime_raw), 'YYYY-MM-DD HH24:MI'),
               (SELECT MAX(year)::text FROM crime.crime_history WHERE current_flag = 'Y'),
               ((SELECT MAX(load_ts) FROM crime.stg_crime_raw) < now() - (:days * interval '1 day'))
        UNION ALL
        SELECT 'employer',
               to_char(MAX(created_at), 'YYYY-MM-DD HH24:MI'),
               MAX(zip_snapshot_year)::text,
               (MAX(created_at) < now() - (:days * interval '1 day'))
        FROM employer.zip_snapshots
        UNION ALL
        SELECT 'healthcare',
               to_char(MAX(created_at), 'YYYY-MM-DD HH24:MI'),
               NULL,
               (MAX(created_at) < now() - (:days * interval '1 day'))
        FROM healthcare.healthcare_provider
        UNION ALL
        SELECT 'lifestyle',
               to_char(MAX(created_at), 'YYYY-MM-DD HH24:MI'),
               MAX(updated_at)::date::text,
               (MAX(created_at) < now() - (:days * interval '1 day'))
        FROM lifestyle.lifestyle_place
        UNION ALL
        SELECT 'schools',
               to_char(MAX(loaded_at), 'YYYY-MM-DD HH24:MI'),
               MAX(data_year)::text,
               (MAX(loaded_at) < now() - (:days * interval '1 day'))
        FROM schools.schools_details
        ORDER BY dataset
    """, {"days": stale_days})


# ── 3) Record counts — rows per category (current data) ───────────────────────
async def record_counts(session: AsyncSession) -> list[dict]:
    return await _rows(session, """
        SELECT 'cost_of_living' AS category, COUNT(*) AS rows FROM cost_of_living.col_snapshot
        UNION ALL SELECT 'crime',      COUNT(*) FROM crime.crime_history WHERE current_flag = 'Y'
        UNION ALL SELECT 'employer',   COUNT(*) FROM employer.zip_snapshots
        UNION ALL SELECT 'healthcare', COUNT(*) FROM healthcare.healthcare_provider
        UNION ALL SELECT 'lifestyle',  COUNT(*) FROM lifestyle.lifestyle_place
        UNION ALL SELECT 'schools',    COUNT(*) FROM schools.schools_details
        ORDER BY rows DESC
    """)


# ── 4) Coverage — distinct zipcodes with data per category ────────────────────
async def coverage(session: AsyncSession) -> list[dict]:
    return await _rows(session, """
        SELECT 'cost_of_living' AS category, COUNT(DISTINCT zipcode) AS zipcodes_covered
        FROM cost_of_living.col_snapshot
        UNION ALL SELECT 'crime',      COUNT(DISTINCT zipcode) FROM crime.crime_history WHERE current_flag = 'Y'
        UNION ALL SELECT 'employer',   COUNT(DISTINCT zipcode) FROM employer.zip_snapshots
        UNION ALL SELECT 'healthcare', COUNT(DISTINCT zipcode) FROM healthcare.healthcare_provider
        UNION ALL SELECT 'lifestyle',  COUNT(DISTINCT zipcode) FROM lifestyle.lifestyle_place
        UNION ALL SELECT 'schools',    COUNT(DISTINCT zipcode) FROM schools.schools_details
        ORDER BY zipcodes_covered DESC
    """)


# ── 5) Coverage gaps (category-aware) ─────────────────────────────────────────
# For each zip a user SEARCHED in a given category, is that (category, zip) pair
# missing from our data? A zip with healthcare but no crime shows up ONLY as a
# crime gap. Optional `category` narrows to one category.
async def coverage_gaps(
    session: AsyncSession,
    days: int,
    limit: int,
    category: str | None = None,
) -> list[dict]:
    sql = f"""
        WITH coverage AS (
            SELECT DISTINCT category, zipcode
            FROM ( {COVERAGE_PAIRS_UNION} ) all_cov
        )
        SELECT ue.category,
               ue.zipcode::text                                    AS zipcode,
               COUNT(*)                                             AS searches,
               COUNT(DISTINCT COALESCE(ue.user_id, ue.session_id)) AS users
        FROM analytics.user_events ue
        LEFT JOIN coverage cov
               ON cov.category = ue.category
              AND cov.zipcode  = ue.zipcode::text
        WHERE ue.zipcode IS NOT NULL AND ue.zipcode::text <> ''
          AND ue.category IS NOT NULL
          AND ue.category IN ('cost_of_living','crime','employer','healthcare','lifestyle','schools')
          AND cov.zipcode IS NULL
          AND ue.created_at >= now() - (:days * interval '1 day')
          -- CAST is required: a bare ":category IS NULL" sends an untyped NULL and
          -- asyncpg/Postgres raises "could not determine data type of parameter".
          AND (CAST(:category AS text) IS NULL OR ue.category = CAST(:category AS text))
        GROUP BY ue.category, ue.zipcode
        ORDER BY searches DESC
        LIMIT :limit
    """
    return await _rows(session, sql, {"days": days, "limit": limit, "category": category})


# ── 6) Data quality — one completeness row PER category ───────────────────────
# Instead of two near-identical healthcare blocks, every category gets exactly
# one row: how many rows are missing the key field we check for it.
#   crime      -> rate      (domain field)
#   healthcare -> rating    (domain field)
#   others     -> zipcode   (the field a zip product can't work without)
# zipcode is cast to text so the "empty" check is type-safe on any column type.
def _zip_missing(schema_table: str, extra_where: str = "") -> str:
    where = f"WHERE {extra_where}" if extra_where else ""
    return f"""
        SELECT '{schema_table.split('.')[0]}' AS category, 'zipcode' AS field_checked,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE zipcode IS NULL OR btrim(zipcode::text) = '') AS missing,
               COALESCE(ROUND(100.0 * COUNT(*) FILTER (WHERE zipcode IS NULL OR btrim(zipcode::text) = '')
                              / NULLIF(COUNT(*), 0), 1), 0) AS missing_pct
        FROM {schema_table} {where}
    """


async def completeness(session: AsyncSession) -> list[dict]:
    return await _rows(session, f"""
        SELECT 'crime' AS category, 'rate' AS field_checked,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE rate IS NULL) AS missing,
               COALESCE(ROUND(100.0 * COUNT(*) FILTER (WHERE rate IS NULL)
                              / NULLIF(COUNT(*), 0), 1), 0) AS missing_pct
        FROM crime.crime_history WHERE current_flag = 'Y'
        UNION ALL
        SELECT 'healthcare', 'rating',
               COUNT(*),
               COUNT(*) FILTER (WHERE rating IS NULL),
               COALESCE(ROUND(100.0 * COUNT(*) FILTER (WHERE rating IS NULL)
                              / NULLIF(COUNT(*), 0), 1), 0)
        FROM healthcare.healthcare_provider
        UNION ALL {_zip_missing('cost_of_living.col_snapshot')}
        UNION ALL {_zip_missing('employer.zip_snapshots')}
        UNION ALL {_zip_missing('lifestyle.lifestyle_place')}
        UNION ALL {_zip_missing('schools.schools_details')}
        ORDER BY missing_pct DESC
    """)