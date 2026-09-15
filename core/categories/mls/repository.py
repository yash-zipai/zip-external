"""
MLS data quality — data access.

Every query reads from admin.dq_check_result. The checks have already done the
work — calling the MLS, working out which listings are affected — so nothing
here recalculates anything. That is what keeps the dashboard quick: it opens in
milliseconds rather than the several minutes a check run takes.

Table names are fully qualified, so these work whichever schema the session is
scoped to.
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


STATUS_SQL = text("""
    WITH latest AS (
        SELECT DISTINCT ON (check_name)
               check_name, value, passed, breakdown, run_at
        FROM admin.dq_check_result
        ORDER BY check_name, run_at DESC
    ),
    last_run AS (
        SELECT MAX(run_at) AS run_at FROM admin.dq_check_result
    )
    SELECT
        -- The data first: how old it is, and how far off the MLS.
        (SELECT value FROM latest WHERE check_name = 'data_age_days') AS data_age_days,
        (SELECT (breakdown->>'mls_has')::bigint
           FROM latest WHERE check_name = 'reconciliation_total')  AS mls_has,
        (SELECT (breakdown->>'we_have')::bigint
           FROM latest WHERE check_name = 'reconciliation_total')  AS we_have,
        (SELECT (breakdown->>'difference')::bigint
           FROM latest WHERE check_name = 'reconciliation_total')  AS gap,
        -- Then the checks.
        (SELECT COUNT(*) FROM latest WHERE NOT passed)             AS checks_failing,
        (SELECT COUNT(*) FROM latest)                              AS checks_run,
        -- And when this was all measured.
        r.run_at                                                   AS last_checked,
        ROUND(EXTRACT(EPOCH FROM (NOW() - r.run_at)) / 3600, 1)    AS hours_since_check,
        r.run_at > NOW() - INTERVAL '26 hours'                     AS ran_today
    FROM last_run r
""")


SOURCE_TARGET_SQL = text("""
    SELECT (breakdown->>'mls_has')::bigint     AS mls_has,
           (breakdown->>'we_have')::bigint     AS we_have,
           (breakdown->>'difference')::bigint  AS difference,
           run_at                              AS checked_at
    FROM admin.dq_check_result
    WHERE check_name = 'reconciliation_total'
    ORDER BY run_at DESC
    LIMIT 1
""")


STATUS_BREAKDOWN_SQL = text("""
    WITH latest AS (
        SELECT breakdown, run_at
        FROM admin.dq_check_result
        WHERE check_name = 'reconciliation_by_status'
        ORDER BY run_at DESC
        LIMIT 1
    )
    SELECT s.key                       AS status,
           (s.value->>'mls')::bigint   AS mls_has,
           (s.value->>'we')::bigint    AS we_have,
           (s.value->>'diff')::bigint  AS difference,
           s.value->>'error'           AS error,
           l.run_at                    AS checked_at
    FROM latest l, jsonb_each(l.breakdown) AS s(key, value)
    ORDER BY (s.value->>'mls')::bigint DESC NULLS LAST
""")


CHECKS_SQL = text("""
    WITH latest AS (
        SELECT DISTINCT ON (check_name)
               check_name, label, severity_level, fix_window,
               value, threshold, passed, run_at,
               COALESCE(jsonb_array_length(affected_keys), 0) AS listings_recorded
        FROM admin.dq_check_result
        ORDER BY check_name, run_at DESC
    ),
    week_ago AS (
        SELECT DISTINCT ON (check_name) check_name, value
        FROM admin.dq_check_result
        WHERE run_at < NOW() - INTERVAL '7 days'
        ORDER BY check_name, run_at DESC
    ),
    -- A check result is a photograph, not a live reading: once listings are
    -- repaired the stored count stays put until the next run. Counting the
    -- repair queue alongside it keeps the page honest between runs.
    repairs AS (
        SELECT found_by,
               COUNT(*) FILTER (
                   WHERE result IN ('updated', 'created', 'filed')) AS repaired,
               COUNT(*) FILTER (WHERE attempted_at IS NULL)         AS outstanding
        FROM admin.dq_action_queue
        GROUP BY found_by
    )
    SELECT
        l.check_name, l.label, l.severity_level, l.fix_window,
        l.value, l.threshold, l.passed, l.listings_recorded, l.run_at,
        COALESCE(rp.repaired, 0)    AS repaired,
        COALESCE(rp.outstanding, 0) AS outstanding,
        w.value AS value_a_week_ago,
        -- Direction decides whether anyone acts today. A number is a fact;
        -- a rising number is a decision.
        CASE
            WHEN w.value IS NULL   THEN 'no history yet'
            WHEN l.value > w.value THEN 'rising'
            WHEN l.value < w.value THEN 'falling'
            ELSE 'flat'
        END AS direction
    FROM latest l
    LEFT JOIN week_ago w USING (check_name)
    LEFT JOIN repairs rp ON rp.found_by = l.check_name
    ORDER BY l.passed, l.severity_level, l.value DESC
""")


# Checks record their detail two ways: some carry whole listings in the
# breakdown, the rest only keys. This covers both, so a caller does not have to
# know which kind of check it asked about.
LISTINGS_SQL = text("""
    WITH latest AS (
        SELECT breakdown, affected_keys
        FROM admin.dq_check_result
        WHERE check_name = :check_name
        ORDER BY run_at DESC LIMIT 1
    ),
    inline AS (
        SELECT jsonb_array_elements(l.breakdown->'listings') AS item
        FROM latest l
        WHERE l.breakdown ? 'listings'

        UNION ALL

        -- live_status_mismatch nests its listings under each status
        SELECT jsonb_array_elements(s.value->'listings')
        FROM latest l, jsonb_each(l.breakdown) AS s(key, value)
        WHERE jsonb_typeof(l.breakdown) = 'object'
          AND jsonb_typeof(s.value) = 'object'
          AND s.value ? 'listings'
    )
    SELECT item->>'listing_key'     AS listing_key,
           item->>'listing_id'      AS listing_id,
           item->>'address'         AS address,
           item->>'zip'             AS zip,
           item->>'our_status'      AS our_status,
           item->>'mls_status'      AS mls_status,
           item->>'our_price'       AS our_price,
           item->>'mls_close_price' AS mls_close_price,
           item->>'mls_close_date'  AS mls_close_date
    FROM inline

    UNION ALL

    SELECT l.listing_key_numeric, l.listing_id, l.unparsed_address,
           l.postal_code, l.standard_status, NULL,
           l.list_price::text, NULL, l.close_date::text
    FROM latest k
    JOIN zipdata_idxlisting l
      ON l.listing_key_numeric = ANY (
             SELECT jsonb_array_elements_text(k.affected_keys))
    WHERE NOT EXISTS (SELECT 1 FROM inline)

    LIMIT :limit OFFSET :offset
""")


LABEL_SQL = text("""
    SELECT label FROM admin.dq_check_result
    WHERE check_name = :check_name
    ORDER BY run_at DESC LIMIT 1
""")


class DQRepository:
    """Reads the stored results of the data quality checks."""

    @staticmethod
    async def fetch_status(session: AsyncSession) -> dict[str, Any] | None:
        result = await session.execute(STATUS_SQL)
        row = result.mappings().first()
        return dict(row) if row else None

    @staticmethod
    async def fetch_source_target(session: AsyncSession) -> dict[str, Any] | None:
        result = await session.execute(SOURCE_TARGET_SQL)
        row = result.mappings().first()
        return dict(row) if row else None

    @staticmethod
    async def fetch_status_breakdown(session: AsyncSession) -> list[dict[str, Any]]:
        result = await session.execute(STATUS_BREAKDOWN_SQL)
        return [dict(row) for row in result.mappings().all()]

    @staticmethod
    async def fetch_checks(session: AsyncSession) -> list[dict[str, Any]]:
        result = await session.execute(CHECKS_SQL)
        return [dict(row) for row in result.mappings().all()]

    @staticmethod
    async def fetch_listings(
        session: AsyncSession,
        check_name: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            LISTINGS_SQL,
            {"check_name": check_name, "limit": limit, "offset": offset},
        )
        return [dict(row) for row in result.mappings().all()]

    @staticmethod
    async def fetch_label(session: AsyncSession, check_name: str) -> str | None:
        result = await session.execute(LABEL_SQL, {"check_name": check_name})
        row = result.first()
        return row[0] if row else None