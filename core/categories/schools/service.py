"""
ZipAI — Schools Service Layer.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import (
    cached,
    schools_breakdown_cache,
    schools_details_cache,
    schools_higher_ed_cache,
    schools_k12_cache,
    schools_map_pins_cache,
)
from core.categories.schools.repository import (
    get_education_breakdown as repo_get_education_breakdown,
    get_map_pins as repo_get_map_pins,
    get_school_details as repo_get_school_details,
    get_schools_higher_ed as repo_get_schools_higher_ed,
    get_schools_k12 as repo_get_schools_k12,
)
from core.categories.schools.schemas import (
    EducationBreakdownItem,
    EducationBreakdownResponse,
    SchoolDetailResponse,
    SchoolHigherEdItem,
    SchoolHigherEdResponse,
    SchoolK12Item,
    SchoolK12Response,
    SchoolMapPinItem,
    SchoolMapPinsResponse,
)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class SchoolService:
    @staticmethod
    @cached(schools_k12_cache)
    async def get_schools_k12(
        session: AsyncSession,
        zipcode: str,
    ) -> SchoolK12Response:
        rows = await repo_get_schools_k12(session, zipcode)
        schools = [
            SchoolK12Item(
                nces_id=row.get("nces_id"),
                school_name=row.get("school_name"),
                school_category=row.get("school_category"),
                school_type=row.get("school_type"),
                level_type=row.get("level_type"),
                low_grade=row.get("low_grade"),
                high_grade=row.get("high_grade"),
                enrollment=_to_int(row.get("enrollment")),
                teachers_fte=_to_float(row.get("teachers_fte")),
                rank_in_zip=_to_int(row.get("rank_in_zip")),
                latitude=_to_float(row.get("latitude")),
                longitude=_to_float(row.get("longitude")),
                address=row.get("address"),
                phone=row.get("phone"),
                rating=_to_float(row.get("rating")),
                reviews_count=_to_int(row.get("reviews_count")),
            )
            for row in rows
        ]
        return SchoolK12Response(zipcode=zipcode, schools=schools)

    @staticmethod
    @cached(schools_higher_ed_cache)
    async def get_schools_higher_ed(
        session: AsyncSession,
        zipcode: str,
    ) -> SchoolHigherEdResponse:
        rows = await repo_get_schools_higher_ed(session, zipcode)
        colleges = [
            SchoolHigherEdItem(
                nces_id=row.get("nces_id"),
                school_name=row.get("school_name"),
                school_type=row.get("school_type"),
                enrollment=_to_int(row.get("enrollment")),
                admission_rate=_to_float(row.get("admission_rate")),
                completion_rate=_to_float(row.get("completion_rate")),
                tuition_in=_to_float(row.get("tuition_in")),
                tuition_out=_to_float(row.get("tuition_out")),
                school_url=row.get("school_url"),
                rank_in_zip=_to_int(row.get("rank_in_zip")),
                latitude=_to_float(row.get("latitude")),
                longitude=_to_float(row.get("longitude")),
                address=row.get("address"),
                phone=row.get("phone"),
                rating=_to_float(row.get("rating")),
                reviews_count=_to_int(row.get("reviews_count")),
            )
            for row in rows
        ]
        return SchoolHigherEdResponse(zipcode=zipcode, colleges=colleges)

    @staticmethod
    @cached(schools_breakdown_cache)
    async def get_education_breakdown(
        session: AsyncSession,
        zipcode: str,
    ) -> EducationBreakdownResponse:
        rows = await repo_get_education_breakdown(session, zipcode)
        items = [
            EducationBreakdownItem(
                school_category=row.get("school_category"),
                school_count=_to_int(row.get("school_count")),
                total_students=_to_int(row.get("total_students")),
                avg_students_per_teacher=_to_float(row.get("avg_students_per_teacher")),
                education_index=_to_float(row.get("education_index")),
                avg_rating=_to_float(row.get("avg_rating")),
                rated_school_count=_to_int(row.get("rated_school_count")),
            )
            for row in rows
        ]
        return EducationBreakdownResponse(zipcode=zipcode, items=items)

    @staticmethod
    @cached(schools_details_cache)
    async def get_school_details(
        session: AsyncSession,
        nces_id: str,
    ) -> SchoolDetailResponse | None:
        row = await repo_get_school_details(session, nces_id)
        if not row:
            return None
        return SchoolDetailResponse(
            nces_id=row.get("nces_id"),
            school_name=row.get("school_name"),
            school_category=row.get("school_category"),
            school_type=row.get("school_type"),
            level_type=row.get("level_type"),
            address=row.get("address"),
            city=row.get("city"),
            state=row.get("state"),
            zipcode=row.get("zipcode"),
            phone=row.get("phone"),
            school_url=row.get("school_url"),
            low_grade=row.get("low_grade"),
            high_grade=row.get("high_grade"),
            enrollment=_to_int(row.get("enrollment")),
            teachers_fte=_to_float(row.get("teachers_fte")),
            students_per_teacher=_to_float(row.get("students_per_teacher")),
            admission_rate=_to_float(row.get("admission_rate")),
            completion_rate=_to_float(row.get("completion_rate")),
            tuition_in=_to_float(row.get("tuition_in")),
            tuition_out=_to_float(row.get("tuition_out")),
            rank_in_zip=_to_int(row.get("rank_in_zip")),
            latitude=_to_float(row.get("latitude")),
            longitude=_to_float(row.get("longitude")),
            data_year=str(row.get("data_year")) if row.get("data_year") else None,
            rating=_to_float(row.get("rating")),
            reviews_count=_to_int(row.get("reviews_count")),
        )

    @staticmethod
    @cached(schools_map_pins_cache)
    async def get_map_pins(
        session: AsyncSession,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> SchoolMapPinsResponse:
        rows = await repo_get_map_pins(session, bbox=bbox)
        pins = [
            SchoolMapPinItem(
                nces_id=row.get("nces_id"),
                school_name=row.get("school_name"),
                school_category=row.get("school_category"),
                latitude=_to_float(row.get("latitude")),
                longitude=_to_float(row.get("longitude")),
                rating=_to_float(row.get("rating")),
                reviews_count=_to_int(row.get("reviews_count")),
            )
            for row in rows
        ]
        return SchoolMapPinsResponse(pins=pins)
