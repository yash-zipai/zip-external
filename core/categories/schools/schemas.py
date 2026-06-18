"""
ZipAI — Schools Pydantic response schemas.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Schools K-12 ─────────────────────────────────────────────────────────────


class SchoolK12Item(BaseModel):
    nces_id: str | None = None
    school_name: str | None = None
    school_category: str | None = None
    school_type: str | None = None
    level_type: str | None = None
    low_grade: str | None = None
    high_grade: str | None = None
    enrollment: int | None = None
    teachers_fte: float | None = None
    rank_in_zip: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    phone: str | None = None


class SchoolK12Response(BaseModel):
    zipcode: str
    schools: list[SchoolK12Item] = Field(default_factory=list)


# ── Colleges and Universities ────────────────────────────────────────────────


class SchoolHigherEdItem(BaseModel):
    nces_id: str | None = None
    school_name: str | None = None
    school_type: str | None = None
    enrollment: int | None = None
    admission_rate: float | None = None
    completion_rate: float | None = None
    tuition_in: float | None = None
    tuition_out: float | None = None
    school_url: str | None = None
    rank_in_zip: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    phone: str | None = None


class SchoolHigherEdResponse(BaseModel):
    zipcode: str
    colleges: list[SchoolHigherEdItem] = Field(default_factory=list)


# ── Education Breakdown ──────────────────────────────────────────────────────


class EducationBreakdownItem(BaseModel):
    school_category: str | None = None
    school_count: int | None = None
    total_students: int | None = None
    avg_students_per_teacher: float | None = None
    education_index: float | None = None


class EducationBreakdownResponse(BaseModel):
    zipcode: str
    items: list[EducationBreakdownItem] = Field(default_factory=list)


# ── School Details ───────────────────────────────────────────────────────────


class SchoolDetailResponse(BaseModel):
    nces_id: str | None = None
    school_name: str | None = None
    school_category: str | None = None
    school_type: str | None = None
    level_type: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zipcode: str | None = None
    phone: str | None = None
    school_url: str | None = None
    low_grade: str | None = None
    high_grade: str | None = None
    enrollment: int | None = None
    teachers_fte: float | None = None
    students_per_teacher: float | None = None
    admission_rate: float | None = None
    completion_rate: float | None = None
    tuition_in: float | None = None
    tuition_out: float | None = None
    rank_in_zip: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    data_year: str | None = None


# ── Map Pins ─────────────────────────────────────────────────────────────────


class SchoolMapPinItem(BaseModel):
    nces_id: str | None = None
    school_name: str | None = None
    school_category: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class SchoolMapPinsResponse(BaseModel):
    pins: list[SchoolMapPinItem] = Field(default_factory=list)
