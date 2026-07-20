import os
import httpx

from .repository import get_click_counts

VECTOR_URL = os.environ.get("VECTOR_URL", "http://localhost:8080")


class AnalyticsService:
    @staticmethod
    async def forward_to_vector(payload: dict):
        # Fire-and-forget. Never let analytics break a user request.
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                await client.post(VECTOR_URL, json=payload)
        except Exception:
            pass

    @staticmethod
    async def get_stats(session, metric_key: str):
        return await get_click_counts(session, metric_key)