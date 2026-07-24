"""
ZipAI — Analytics Service Layer.

Handles analytics business logic.

Endpoints:
    POST /internal/vector/events
    GET  /v1/analytics/house/{house_id}/views
    GET  /v1/analytics/usage

Save as:
core/analytics/service.py
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.categories.analytics.repository import (
    insert_event as repo_insert_event,
    get_house_views as repo_get_house_views,
    get_zipai_usage as repo_get_zipai_usage,
)

from core.categories.analytics.schemas import (
    AnalyticsEventRequest,
    HouseViewResponse,
    ZipAIUsageItem,
    ZipAIUsageResponse,
)


class AnalyticsService:

    # ======================================================================
    # Insert Analytics Event (Called by Vector)
    # ======================================================================

    @staticmethod
    async def insert_event(
        session: AsyncSession,
        event: AnalyticsEventRequest,
    ) -> None:
        """
        Stores analytics events received from Vector.
        """

        await repo_insert_event(
            session=session,
            event=event.model_dump(),
        )

    # ======================================================================
    # House View Analytics
    # ======================================================================

    @staticmethod
    async def get_house_views(
        session: AsyncSession,
        house_id: str,
    ) -> HouseViewResponse | None:
        """
        Returns total views and unique visitors for a house.
        """

        row = await repo_get_house_views(
            session=session,
            house_id=house_id,
        )

        if not row:
            return None

        return HouseViewResponse(
            house_id=row.get("house_id"),
            total_views=int(row.get("total_views", 0)),
            unique_visitors=int(row.get("unique_visitors", 0)),
        )

    # ======================================================================
    # ZIPAI Usage Analytics
    # ======================================================================

    @staticmethod
    async def get_zipai_usage(
        session: AsyncSession,
    ) -> ZipAIUsageResponse:
        """
        Returns overall ZIPAI usage statistics.
        """

        rows = await repo_get_zipai_usage(session)

        usage = [
            ZipAIUsageItem(
                page_name=row.get("page_name"),
                event_type=row.get("event_type"),
                total_events=int(row.get("total_events", 0)),
                unique_users=int(row.get("unique_users", 0)),
            )
            for row in rows
        ]

        return ZipAIUsageResponse(
            usage=usage
        )