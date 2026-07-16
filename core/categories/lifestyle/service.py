"""
ZipAI — Lifestyle Service Layer.

Orchestrates repository calls, applies caching, and maps raw dicts
to typed Pydantic response models. All business logic for lifestyle
endpoints lives here.
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

# from logging import get_logger
from core.categories.lifestyle.schemas import (
    IndexScoresResponse,
    LifestyleBreakdownItem,
    LifestyleBreakdownResponse,
    MapPin,
    MapPinsResponse,
    PlaceDetail,
    TopPlacesResponse,
)
from core.pagination import PaginationMeta
from core.cache import (
    cached,
    lifestyle_breakdown_cache,
    lifestyle_index_scores_cache,
    lifestyle_map_pins_cache,
    lifestyle_top_places_cache,
)
from core.categories.lifestyle.repository import (
    get_breakdown as repo_get_breakdown,
    get_index_scores as repo_get_index_scores,
    get_map_pins as repo_get_map_pins,
    get_top_places as repo_get_top_places,
)

# logger = get_logger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _to_float(value: Any) -> float | None:
    """Safely convert a Decimal/numeric DB value to a Python float."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int:
    """Safely convert a numeric DB value to an int, defaulting to 0."""
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
        
def _to_int_or_none(value: Any) -> int | None:
    """Numeric DB value -> int, keeping None as None (for 'no data' scores)."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

class LifestyleService:
    """Business logic for lifestyle API endpoints."""

    @staticmethod
    @cached(lifestyle_top_places_cache)
    async def get_top_places(
        session: AsyncSession,
        zipcode: str,
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> TopPlacesResponse:
        """Retrieve top-rated lifestyle places for a zipcode."""
        t0 = time.monotonic()

        rows, total = await repo_get_top_places(
            session, zipcode, category=category, limit=limit, offset=offset
        )

        places = [
            PlaceDetail(
                place_id=row["place_id"],
                place_name=row.get("place_name"),
                category=row.get("category"),
                address=row.get("address"),
                phone=row.get("phone"),
                website=row.get("website"),
                google_maps=row.get("google_maps"),
                hours=row.get("hours"),
                rank=row.get("rank"),
                avg_rating=_to_float(row.get("avg_rating")),
                review_count=_to_int(row.get("review_count")),
                latitude=_to_float(row.get("latitude")),
                longitude=_to_float(row.get("longitude")),
                thumbnail_url=row.get("thumbnail_url"),
            )
            for row in rows
        ]

        duration_ms = int((time.monotonic() - t0) * 1000)
        # logger.info("svc_get_top_places", zipcode=zipcode, category=category,
        #             places_returned=len(places), total=total, duration_ms=duration_ms)

        return TopPlacesResponse(
            zipcode=zipcode,
            category_filter=category,
            places=places,
            pagination=PaginationMeta.build(
                limit=limit, offset=offset, total=total, count=len(places)
            ),
        )

    @staticmethod
    @cached(lifestyle_breakdown_cache)
    async def get_breakdown(
        session: AsyncSession,
        zipcode: str,
    ) -> LifestyleBreakdownResponse:
        """Retrieve the per-category lifestyle breakdown for a zipcode."""
        t0 = time.monotonic()

        rows = await repo_get_breakdown(session, zipcode)

        items = [
            LifestyleBreakdownItem(
                category=row.get("category"),
                avg_rating=_to_float(row.get("avg_rating")),
                total_places=_to_int(row.get("total_places")),
                total_reviews=_to_int(row.get("total_reviews")),
            )
            for row in rows
        ]

        # zipcode/city are constant across rows; surface city from the first row.
        city = rows[0].get("city") if rows else None

        duration_ms = int((time.monotonic() - t0) * 1000)
        # logger.info("svc_get_breakdown", zipcode=zipcode,
        #             categories_returned=len(items), duration_ms=duration_ms)

        return LifestyleBreakdownResponse(zipcode=zipcode, city=city, items=items)

    @staticmethod
    @cached(lifestyle_index_scores_cache)
    async def get_index_scores(
        session: AsyncSession,
        zipcode: str,
    ) -> IndexScoresResponse:
        """Retrieve the ZIP-level lifestyle aggregate and index score."""
        t0 = time.monotonic()

        row = await repo_get_index_scores(session, zipcode)

        if row is None:
            # No lifestyle places for this ZIP — return a zeroed aggregate
            # rather than a 404, consistent with the list endpoints.
            return IndexScoresResponse(
                zipcode=zipcode,
                city=None,
                total_places=0,
                overall_avg_rating=None,
                total_reviews=0,
                lifestyle_index_score=None,
            )

        duration_ms = int((time.monotonic() - t0) * 1000)
        # logger.info("svc_get_index_scores", zipcode=zipcode, duration_ms=duration_ms)

        return IndexScoresResponse(
            zipcode=zipcode,
            city=row.get("city"),
            total_places=_to_int_or_none(row.get("total_places")),
            overall_avg_rating=_to_float(row.get("overall_avg_rating")),
            total_reviews=_to_int_or_none(row.get("total_reviews")),
            lifestyle_index_score=_to_int_or_none(row.get("lifestyle_index_score")),
        )

    @staticmethod
    @cached(lifestyle_map_pins_cache)
    async def get_map_pins(
        session: AsyncSession,
        zipcode: str | None = None,
        layers: str | None = None,
        bbox: tuple[float, float, float, float] | None = None,
        zoom: int | None = None,   # reserved for future clustering; unused for now
        limit: int = 200,
        offset: int = 0,
    ) -> MapPinsResponse:
        """Retrieve minimal lifestyle place pins for map display."""
        t0 = time.monotonic()

        rows, total = await repo_get_map_pins(
            session,
            zipcode=zipcode,
            layers=layers,
            bbox=bbox,
            limit=limit,
            offset=offset,
        )

        pins: list[MapPin] = []
        for row in rows:
            lat = _to_float(row.get("latitude"))
            lng = _to_float(row.get("longitude"))
            if lat is None or lng is None:
                continue  # never emit a pin without coordinates
            pins.append(
                MapPin(
                    place_id=row.get("place_id"),
                    name=row.get("place_name"),
                    category=row.get("category"),
                    latitude=lat,
                    longitude=lng,
                    avg_rating=_to_float(row.get("avg_rating")),
                    thumbnail_url=row.get("thumbnail_url"),
                )
            )

        duration_ms = int((time.monotonic() - t0) * 1000)
        # logger.info("svc_get_map_pins", zipcode=zipcode, layers=layers, zoom=zoom,
        #             pins_returned=len(pins), total=total, duration_ms=duration_ms)

        return MapPinsResponse(pins=pins)
