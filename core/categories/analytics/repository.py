"""
Analytics Repository

Save as:
core/analytics/repository.py
"""

from __future__ import annotations

from typing import Any
import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# ===========================================================
# Insert Event
# ===========================================================

async def insert_event(
    session: AsyncSession,
    event: dict[str, Any],
) -> None:

    sql = text("""
        INSERT INTO analytics.user_events
        (
            event_type,
            category,
            action,
            resource_id,
            zipcode,
            user_id,
            session_id,
            page_name,
            metadata
        )
        VALUES
        (
            :event_type,
            :category,
            :action,
            :resource_id,
            :zipcode,
            :user_id,
            :session_id,
            :page_name,
            CAST(:metadata AS JSONB)
        )
    """)

    await session.execute(
        sql,
        {
            "event_type": event.get("event_type"),
            "category": event.get("category"),
            "action": event.get("action"),
            "resource_id": event.get("resource_id"),
            "zipcode": event.get("zipcode"),
            "user_id": event.get("user_id"),
            "session_id": event.get("session_id"),
            "page_name": event.get("page_name"),
            "metadata": json.dumps(event.get("metadata", {}))
        },
    )

    await session.commit()


# ===========================================================
# API 1
# How many people viewed this house
# ===========================================================

async def get_house_views(
    session: AsyncSession,
    house_id: str,
) -> dict[str, Any] | None:

    sql = text("""
        SELECT

            resource_id AS house_id,

            COUNT(*) AS total_views,

            COUNT(DISTINCT session_id) AS unique_visitors

        FROM analytics.user_events

        WHERE
            event_type = 'house_view'
            AND resource_id = :house_id

        GROUP BY resource_id
    """)

    result = await session.execute(
        sql,
        {
            "house_id": house_id
        }
    )

    row = result.fetchone()

    return dict(row._mapping) if row else None


# ===========================================================
# API 2
# How people use ZIPAI
# ===========================================================

async def get_zipai_usage(
    session: AsyncSession,
) -> list[dict[str, Any]]:

    sql = text("""
        SELECT

            page_name,

            event_type,

            COUNT(*) AS total_events,

            COUNT(DISTINCT session_id) AS unique_users

        FROM analytics.user_events

        GROUP BY
            page_name,
            event_type

        ORDER BY total_events DESC
    """)

    result = await session.execute(sql)

    return [
        dict(row._mapping)
        for row in result.fetchall()
    ]


# ===========================================================
# API 3 — Admin Insights (read queries over analytics.user_events)
# "a user" = COALESCE(user_id, session_id)
# "active" = has an event within the window (uses DB clock now())
# ===========================================================

INDEX_CATEGORIES = ["lifestyle", "healthcare", "crime", "schools", "cost_of_living", "employer"]


async def _ins_scalar(session: AsyncSession, sql: str, params: dict | None = None):
    return (await session.execute(text(sql), params or {})).scalar()


async def _ins_rows(session: AsyncSession, sql: str, params: dict | None = None) -> list[dict]:
    res = await session.execute(text(sql), params or {})
    return [dict(r._mapping) for r in res.fetchall()]


async def ins_total_users(session: AsyncSession) -> int:
    return await _ins_scalar(
        session,
        "SELECT COUNT(DISTINCT COALESCE(user_id, session_id)) FROM analytics.user_events",
    ) or 0


async def ins_active_users(session: AsyncSession, days: int) -> int:
    return await _ins_scalar(session, """
        SELECT COUNT(DISTINCT COALESCE(user_id, session_id))
        FROM analytics.user_events
        WHERE created_at >= now() - (:days * interval '1 day')
    """, {"days": days}) or 0


async def ins_new_users(session: AsyncSession, days: int) -> int:
    return await _ins_scalar(session, """
        SELECT COUNT(*) FROM (
            SELECT COALESCE(user_id, session_id) AS person, MIN(created_at) AS first_seen
            FROM analytics.user_events
            GROUP BY COALESCE(user_id, session_id)
        ) t
        WHERE first_seen >= now() - (:days * interval '1 day')
    """, {"days": days}) or 0


async def ins_top_zipcodes(session: AsyncSession, limit: int = 10) -> list[dict]:
    return await _ins_rows(session, """
        SELECT zipcode,
               COUNT(DISTINCT COALESCE(user_id, session_id)) AS users,
               COUNT(*) AS searches
        FROM analytics.user_events
        WHERE zipcode IS NOT NULL AND zipcode <> ''
        GROUP BY zipcode ORDER BY searches DESC LIMIT :limit
    """, {"limit": limit})


async def ins_index_usage(session: AsyncSession):
    total = await _ins_scalar(session, """
        SELECT COUNT(DISTINCT COALESCE(user_id, session_id))
        FROM analytics.user_events WHERE category = ANY(:cats)
    """, {"cats": INDEX_CATEGORIES}) or 0
    rows = await _ins_rows(session, """
        SELECT category, COUNT(DISTINCT COALESCE(user_id, session_id)) AS users
        FROM analytics.user_events WHERE category = ANY(:cats) GROUP BY category
    """, {"cats": INDEX_CATEGORIES})
    return int(total), {r["category"]: int(r["users"]) for r in rows}


async def ins_total_events(session: AsyncSession) -> int:
    return await _ins_scalar(session, "SELECT COUNT(*) FROM analytics.user_events") or 0


async def ins_total_sessions(session: AsyncSession) -> int:
    return await _ins_scalar(
        session,
        "SELECT COUNT(DISTINCT session_id) FROM analytics.user_events WHERE session_id IS NOT NULL",
    ) or 0


async def ins_top_houses(session: AsyncSession, limit: int = 10) -> list[dict]:
    return await _ins_rows(session, """
        SELECT resource_id, COUNT(*) AS views
        FROM analytics.user_events
        WHERE event_type = 'house_view' AND resource_id IS NOT NULL
        GROUP BY resource_id ORDER BY views DESC LIMIT :limit
    """, {"limit": limit})


async def ins_top_pages(session: AsyncSession, limit: int = 10) -> list[dict]:
    return await _ins_rows(session, """
        SELECT page_name, COUNT(*) AS events
        FROM analytics.user_events
        WHERE page_name IS NOT NULL
        GROUP BY page_name ORDER BY events DESC LIMIT :limit
    """, {"limit": limit})


async def ins_events_per_day(session: AsyncSession, days: int = 30) -> list[dict]:
    return await _ins_rows(session, """
        SELECT to_char(date_trunc('day', created_at), 'YYYY-MM-DD') AS day, COUNT(*) AS events
        FROM analytics.user_events
        WHERE created_at >= now() - (:days * interval '1 day')
        GROUP BY 1 ORDER BY 1
    """, {"days": days})


async def ins_trending_zipcodes(session: AsyncSession, days: int = 7, limit: int = 10) -> list[dict]:
    """
    Compare searches per zipcode in the last `days` vs the `days` before that,
    ranked by current demand, with a week-over-week trend.
    """
    sql = text("""
        WITH cur AS (
            SELECT zipcode,
                   COUNT(*) AS current_searches,
                   COUNT(DISTINCT COALESCE(user_id, session_id)) AS users
            FROM analytics.user_events
            WHERE zipcode IS NOT NULL AND zipcode <> ''
              AND created_at >= now() - (:days * interval '1 day')
            GROUP BY zipcode
        ),
        prev AS (
            SELECT zipcode, COUNT(*) AS previous_searches
            FROM analytics.user_events
            WHERE zipcode IS NOT NULL AND zipcode <> ''
              AND created_at >= now() - (2 * :days * interval '1 day')
              AND created_at <  now() - (:days * interval '1 day')
            GROUP BY zipcode
        )
        SELECT c.zipcode,
               c.current_searches,
               COALESCE(p.previous_searches, 0) AS previous_searches,
               c.users,
               CASE WHEN COALESCE(p.previous_searches, 0) = 0 THEN NULL
                    ELSE ROUND(((c.current_searches - p.previous_searches)::numeric
                                 / p.previous_searches) * 100, 1) END AS change_pct,
               CASE WHEN COALESCE(p.previous_searches, 0) = 0 THEN 'new'
                    WHEN c.current_searches > p.previous_searches THEN 'up'
                    WHEN c.current_searches < p.previous_searches THEN 'down'
                    ELSE 'flat' END AS trend
        FROM cur c
        LEFT JOIN prev p ON p.zipcode = c.zipcode
        ORDER BY c.current_searches DESC
        LIMIT :limit
    """)
    res = await session.execute(sql, {"days": days, "limit": limit})
    return [dict(r._mapping) for r in res.fetchall()]
