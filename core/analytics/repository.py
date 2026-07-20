"""
ZipAI — Analytics Data Repository (DAL).
Reads aggregate click counts from analytics.page_clicks.
(Writes go through Vector, not through here — see service.forward_to_vector.)
All queries use parameterised binds — never string interpolation.
"""
from __future__ import annotations
from typing import Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_click_counts(session: AsyncSession, metric_key: str) -> dict[str, Any]:
    """Total clicks, distinct people, and distinct people this month for one metric_key."""
    result = await session.execute(text("""
        SELECT
            COUNT(*)                                              AS total_clicks,
            COUNT(DISTINCT COALESCE(user_id, session_id))         AS unique_people,
            COUNT(DISTINCT COALESCE(user_id, session_id))
                FILTER (WHERE created_at >= date_trunc('month', now())) AS this_month_people
        FROM analytics.page_clicks
        WHERE metric_key = :metric_key
    """), {"metric_key": metric_key})
    row = result.fetchone()
    return dict(row._mapping) if row else {}


async def insert_click_direct(session: AsyncSession, metric_key: str,
                              user_id: str | None, session_id: str | None,
                              url: str | None) -> None:
    """OPTIONAL fallback: write a click straight to Postgres WITHOUT Vector.
    Use only if you are NOT running Vector. The Vector path is preferred for
    batching/durability. Kept here so the module works either way."""
    await session.execute(text("""
        INSERT INTO analytics.page_clicks (metric_key, user_id, session_id, url, created_at)
        VALUES (:metric_key, :user_id, :session_id, :url, now())
    """), {"metric_key": metric_key, "user_id": user_id,
           "session_id": session_id, "url": url})
    await session.commit()
