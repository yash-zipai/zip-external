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
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.categories.analytics.repository import (
    insert_event as repo_insert_event,
    get_house_views as repo_get_house_views,
    get_zipai_usage as repo_get_zipai_usage,
)
from core.categories.analytics import repository as repo
from core.categories.analytics.schemas import (
    AnalyticsEventRequest,
    HouseViewResponse,
    ZipAIUsageItem,
    ZipAIUsageResponse,
    InsightsOverviewResponse,
    UserActivity,
    ZipcodeStat,
    IndexUsage,
    ResourceStat,
    PageStat,
    DayCount,
    ContentEngagement,
    TrendingZipcode,
    TrendingZipcodesResponse,
    HeatmapCell,
    ActivityHeatmapResponse,
    FunnelStep,
    UserJourneyFunnelResponse,
    SessionQualityResponse,
    SearchToViewConversionResponse,
)
logger = logging.getLogger("analytics.insights")

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

        # ======================================================================
    # Admin Insights Overview (user behaviour + engagement)
    # Each metric is failure-isolated: on error we log, roll back, continue.
    # ======================================================================

    @staticmethod
    async def get_insights_overview(
        session: AsyncSession,
    ) -> InsightsOverviewResponse:

        W = 30

        async def safe(factory, default=None):
            try:
                return await factory()
            except Exception as err:  # noqa: BLE001
                logger.warning("insights metric failed: %s", err)
                try:
                    await session.rollback()
                except Exception:  # noqa: BLE001
                    pass
                return default

        # ---- User activity ----
        total = int(await safe(lambda: repo.ins_total_users(session), 0) or 0)
        active = int(await safe(lambda: repo.ins_active_users(session, W), 0) or 0)
        new = int(await safe(lambda: repo.ins_new_users(session, W), 0) or 0)
        dau = int(await safe(lambda: repo.ins_active_users(session, 1), 0) or 0)
        wau = int(await safe(lambda: repo.ins_active_users(session, 7), 0) or 0)
        mau = int(await safe(lambda: repo.ins_active_users(session, 30), 0) or 0)

        users = UserActivity(
            total_users=total,
            active_users=active,
            inactive_users=max(total - active, 0),
            new_users=new,
            returning_users=max(active - new, 0),
            dau=dau, wau=wau, mau=mau,
            active_window_days=W,
        )

        # ---- Top zipcodes ----
        zip_rows = await safe(lambda: repo.ins_top_zipcodes(session, 10), []) or []
        top_zipcodes = [
            ZipcodeStat(zipcode=str(r["zipcode"]), users=int(r["users"]), searches=int(r["searches"]))
            for r in zip_rows
        ]

        # ---- Index usage ----
        idx = await safe(lambda: repo.ins_index_usage(session), (0, {}))
        index_total, index_by = idx if idx else (0, {})
        index_usage = IndexUsage(total_users=int(index_total or 0), by_category=index_by or {})

        # ---- Content engagement ----
        t_events = int(await safe(lambda: repo.ins_total_events(session), 0) or 0)
        t_sessions = int(await safe(lambda: repo.ins_total_sessions(session), 0) or 0)
        house_rows = await safe(lambda: repo.ins_top_houses(session, 10), []) or []
        page_rows = await safe(lambda: repo.ins_top_pages(session, 10), []) or []
        day_rows = await safe(lambda: repo.ins_events_per_day(session, 30), []) or []

        content = ContentEngagement(
            total_events=t_events,
            total_sessions=t_sessions,
            top_houses=[ResourceStat(resource_id=str(r["resource_id"]), views=int(r["views"])) for r in house_rows],
            top_pages=[PageStat(page_name=r["page_name"], events=int(r["events"])) for r in page_rows],
            events_per_day=[DayCount(day=r["day"], events=int(r["events"])) for r in day_rows],
        )

        return InsightsOverviewResponse(
            users=users,
            top_zipcodes=top_zipcodes,
            index_usage=index_usage,
            content=content,
        )

    # ======================================================================
    # Trending Zipcodes — demand trend (current window vs previous window)
    # ======================================================================

    @staticmethod
    async def get_trending_zipcodes(
        session: AsyncSession,
        days: int = 7,
        limit: int = 10,
    ) -> TrendingZipcodesResponse:
        """
        Ranked list of the most-searched zipcodes right now, each with its
        week-over-week (or `days`-over-`days`) demand trend.
        """
        rows = await repo.ins_trending_zipcodes(session, days=days, limit=limit)

        items = [
            TrendingZipcode(
                zipcode=str(r["zipcode"]),
                current_searches=int(r["current_searches"] or 0),
                previous_searches=int(r["previous_searches"] or 0),
                users=int(r["users"] or 0),
                change_pct=(float(r["change_pct"]) if r["change_pct"] is not None else None),
                trend=str(r["trend"]),
            )
            for r in rows
        ]

        return TrendingZipcodesResponse(period_days=days, items=items)

        # ======================================================================
    # API 5 — Peak usage hours (activity heatmap: day-of-week x hour)
    # ======================================================================

    @staticmethod
    async def get_activity_heatmap(
        session: AsyncSession,
        days: int = 30,
    ) -> ActivityHeatmapResponse:
        day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        rows = await repo.ins_activity_heatmap(session, days=days)
        cells = [
            HeatmapCell(
                dow=int(r["dow"]),
                day_name=day_names[int(r["dow"])],
                hour=int(r["hour"]),
                events=int(r["events"]),
            )
            for r in rows
        ]
        busiest = max(cells, key=lambda c: c.events) if cells else None
        return ActivityHeatmapResponse(days=days, cells=cells, busiest=busiest)

    # ======================================================================
    # API 6 — User journey funnel (searched -> viewed house -> viewed index)
    # ======================================================================

    @staticmethod
    async def get_user_journey_funnel(
        session: AsyncSession,
        days: int = 30,
    ) -> UserJourneyFunnelResponse:
        d = await repo.ins_user_journey_funnel(session, days=days)
        searched = int(d.get("searched", 0) or 0)
        viewed_house = int(d.get("viewed_house", 0) or 0)
        viewed_index = int(d.get("viewed_index", 0) or 0)

        def pct_of_top(n: int) -> float:
            return round(100.0 * n / searched, 1) if searched else 0.0

        steps = [
            FunnelStep(
                step="searched_zipcode", label="Searched a zipcode",
                users=searched, pct_of_top=pct_of_top(searched), drop_from_prev_pct=0.0,
            ),
            FunnelStep(
                step="viewed_house", label="Viewed a house",
                users=viewed_house, pct_of_top=pct_of_top(viewed_house),
                drop_from_prev_pct=(round(100.0 * (searched - viewed_house) / searched, 1) if searched else 0.0),
            ),
            FunnelStep(
                step="viewed_index", label="Viewed an index",
                users=viewed_index, pct_of_top=pct_of_top(viewed_index),
                drop_from_prev_pct=(round(100.0 * (viewed_house - viewed_index) / viewed_house, 1) if viewed_house else 0.0),
            ),
        ]
        return UserJourneyFunnelResponse(days=days, steps=steps)

    # ======================================================================
    # API 7 — Session quality (depth of a visit)
    # ======================================================================

    @staticmethod
    async def get_session_quality(
        session: AsyncSession,
        days: int = 30,
    ) -> SessionQualityResponse:
        d = await repo.ins_session_quality(session, days=days)
        secs = float(d.get("avg_session_seconds", 0) or 0)
        return SessionQualityResponse(
            days=days,
            total_sessions=int(d.get("total_sessions", 0) or 0),
            avg_events_per_session=float(d.get("avg_events_per_session", 0) or 0),
            avg_session_seconds=secs,
            avg_session_minutes=round(secs / 60.0, 1),
            bounce_rate_pct=float(d.get("bounce_rate_pct", 0) or 0),
        )

    # ======================================================================
    # API 8 — Search-to-view conversion
    # ======================================================================

    @staticmethod
    async def get_search_to_view_conversion(
        session: AsyncSession,
        days: int = 30,
    ) -> SearchToViewConversionResponse:
        d = await repo.ins_search_to_view_conversion(session, days=days)
        searchers = int(d.get("searchers", 0) or 0)
        converters = int(d.get("converters", 0) or 0)
        rate = round(100.0 * converters / searchers, 1) if searchers else 0.0
        return SearchToViewConversionResponse(
            days=days, searchers=searchers, converters=converters, conversion_rate_pct=rate,
        )



