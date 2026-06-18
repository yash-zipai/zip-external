"""
ZipAI — Healthcare Service Layer.

Orchestrates repository calls, applies caching, and maps raw dicts
to typed Pydantic response models.  All business logic for healthcare
endpoints lives here.
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

# from logging import get_logger
from core.categories.healthcare.schemas import (
    BreakdownBucket,
    BreakdownResponse,
    HealthcareIndexEntry,
    HealthcareIndexResponse,
    MapPin,
    MapPinsResponse,
    ProviderDetail,
    TopPlacesResponse,
)
from core.pagination import PaginationMeta
from core.cache import (
    breakdown_cache,
    cached,
    index_scores_cache,
    map_pins_cache,
    top_places_cache,
)
from core.categories.healthcare.repository import (
    get_breakdown as repo_get_breakdown,
    get_index_scores as repo_get_index_scores,
    get_map_pins as repo_get_map_pins,
    get_top_places as repo_get_top_places,
)

# logger = get_logger(__name__)


class HealthcareService:
    """Business logic for healthcare API endpoints."""

    @staticmethod
    @cached(top_places_cache)
    async def get_top_places(
        session: AsyncSession,
        zipcode: str,
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> TopPlacesResponse:
        """
        Retrieve top-rated healthcare providers for a zipcode.

        Optionally filtered by a single category.
        """
        t0 = time.monotonic()

        rows, total = await repo_get_top_places(
            session, zipcode, category=category, limit=limit, offset=offset
        )

        providers = [
            ProviderDetail(
                provider_id=row["provider_id"],
                provider_name=row.get("provider_name"),
                category=row.get("category"),
                address=row.get("address"),
                phone=row.get("phone"),
                website=row.get("website"),
                google_maps=row.get("google_maps"),
                rank=row.get("rank"),
                avg_rating=_to_float(row.get("avg_rating")),
                review_count=row.get("review_count", 0),
                thumbnail_url=row.get("thumbnail_url"),
            )
            for row in rows
        ]

        duration_ms = int((time.monotonic() - t0) * 1000)
        # logger.info(
        #     "svc_get_top_places",
        #     zipcode=zipcode,
        #     category=category,
        #     providers_returned=len(providers),
        #     total=total,
        #     duration_ms=duration_ms,
        # )

        return TopPlacesResponse(
            zipcode=zipcode,
            category_filter=category,
            providers=providers,
            pagination=PaginationMeta.build(
                limit=limit, offset=offset, total=total, count=len(providers)
            ),
        )

    @staticmethod
    @cached(breakdown_cache)
    async def get_breakdown(
        session: AsyncSession,
        zipcode: str,
    ) -> BreakdownResponse:
        """Retrieve healthcare breakdown buckets for a zipcode."""
        t0 = time.monotonic()

        rows = await repo_get_breakdown(session, zipcode)

        buckets = [
            BreakdownBucket(
                bucket=row["bucket"],
                provider_count=row.get("provider_count", 0),
                avg_rating=_to_float(row.get("avg_rating")),
                total_reviews=row.get("total_reviews", 0),
                score=_to_float(row.get("score")),
            )
            for row in rows
        ]

        duration_ms = int((time.monotonic() - t0) * 1000)
        # logger.info(
        #     "svc_get_breakdown",
        #     zipcode=zipcode,
        #     buckets_returned=len(buckets),
        #     duration_ms=duration_ms,
        # )

        return BreakdownResponse(zipcode=zipcode, buckets=buckets)

    @staticmethod
    @cached(index_scores_cache)
    async def get_index_scores(
        session: AsyncSession,
        zipcode: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> HealthcareIndexResponse:
        """
        Retrieve healthcare index scores.

        If *zipcode* is provided, returns the score for that single zip.
        Otherwise returns all zipcodes sorted by score descending.
        """
        t0 = time.monotonic()

        rows, total = await repo_get_index_scores(
            session, zipcode=zipcode, limit=limit, offset=offset
        )

        entries = [
            HealthcareIndexEntry(
                zipcode=row["zipcode"],
                city=row.get("city"),
                total_providers=row.get("total_providers", 0),
                overall_avg_rating=_to_float(row.get("overall_avg_rating")),
                total_reviews=row.get("total_reviews", 0),
                healthcare_index_score=_to_float(row.get("healthcare_index_score")),
            )
            for row in rows
        ]

        duration_ms = int((time.monotonic() - t0) * 1000)
        # logger.info(
        #     "svc_get_index_scores",
        #     zipcode=zipcode,
        #     entries_returned=len(entries),
        #     total=total,
        #     duration_ms=duration_ms,
        # )

        return HealthcareIndexResponse(
            zipcode_filter=zipcode,
            entries=entries,
            pagination=PaginationMeta.build(
                limit=limit, offset=offset, total=total, count=len(entries)
            ),
        )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _to_float(value: Any) -> float | None:
    """Safely convert a Decimal/numeric DB value to a Python float."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class MapPinsService:
    """Business logic for healthcare map pins endpoint."""

    @staticmethod
    @cached(map_pins_cache)
    async def get_map_pins(
        session: AsyncSession,
        zipcode: str | None = None,
        layers: str | None = None,
        bbox: tuple[float, float, float, float] | None = None,
        zoom: int | None = None,   # reserved for future clustering; unused for now
        limit: int = 200,
        offset: int = 0,
    ) -> MapPinsResponse:
        """
        Retrieve minimal healthcare provider pins for map display.

        Optionally filtered by zipcode, category layers and/or a map
        bounding box. Pins without coordinates are dropped.
        """
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
                    name=row.get("provider_name"),
                    latitude=lat,
                    longitude=lng,
                    avg_rating=_to_float(row.get("avg_rating")),
                    thumbnail_url=None,  # no image column in the table yet
                )
            )

        duration_ms = int((time.monotonic() - t0) * 1000)
        # logger.info(
        #     "svc_get_map_pins",
        #     zipcode=zipcode,
        #     layers=layers,
        #     zoom=zoom,
        #     pins_returned=len(pins),
        #     total=total,
        #     duration_ms=duration_ms,
        # )

        return MapPinsResponse(pins=pins)