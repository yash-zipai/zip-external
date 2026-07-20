"""
ZipAI — Analytics Service Layer.
Forwards click events to Vector (write path) and reads aggregate counts
from Postgres (read path).
"""
from __future__ import annotations
import os
from typing import Any
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from core.categories.analytics.schemas import ClickStatsResponse
from core.categories.analytics.repository import get_click_counts

# Vector's HTTP source. On this EC2 (systemd), Vector runs on the same host,
# so localhost. (If you ever move to docker-compose, use http://vector:8080.)
VECTOR_URL = os.getenv("VECTOR_URL", "http://localhost:8080")


def _to_int(value: Any) -> int:
    return int(value) if value is not None else 0


class AnalyticsService:
    """Business logic for the analytics endpoints."""

    @staticmethod
    async def forward_to_vector(payload: dict) -> None:
        """Send one event to Vector. NEVER raises — telemetry must not break UX.
        Runs in a FastAPI BackgroundTask so the user's click returns instantly."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                await client.post(VECTOR_URL, json=payload)
        except Exception:
            pass  # Vector down/slow: drop silently. Retry/disk-buffer live in Vector.

    @staticmethod
    async def get_stats(session: AsyncSession, metric_key: str) -> ClickStatsResponse:
        row = await get_click_counts(session, metric_key)
        return ClickStatsResponse(
            metric_key=metric_key,
            total_clicks=_to_int(row.get("total_clicks")),
            unique_people=_to_int(row.get("unique_people")),
            this_month_people=_to_int(row.get("this_month_people")),
        )
