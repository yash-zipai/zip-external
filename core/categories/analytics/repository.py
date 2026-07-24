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