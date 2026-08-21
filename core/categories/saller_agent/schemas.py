"""
ZipAI — Seller-Agent dashboard — response schemas.

Covers 6 dashboard features:
  1 profile · 2 listings · 3 invites (+summary drill-down) · 4 clients
  5 partners · 6 invited-by
"""
from __future__ import annotations

from datetime import date, datetime
from pydantic import BaseModel, Field


# ── 1 · Agent profile ─────────────────────────────────────────────────────────
class AgentProfile(BaseModel):
    agent_key: str | None = None
    agent_name: str | None = None
    agent_email: str | None = None
    agent_phone: str | None = None
    office_key: str | None = None
    office_name: str | None = None


# ── 2 · Agent listings ────────────────────────────────────────────────────────
class AgentListingRow(BaseModel):
    listing_key_numeric: str
    address: str | None = None
    city: str | None = None
    zip_code: str | None = None
    list_price: float | None = None
    sale_price: float | None = None
    status: str | None = None
    property_type: str | None = None
    beds: float | None = None
    baths: float | None = None
    sqft: float | None = None


class AgentListingsResponse(BaseModel):
    agent_key: str
    status: str
    count: int = 0
    rows: list[AgentListingRow] = Field(default_factory=list)


# ── 3 · Invites — summary (bar chart) + list (drill-down) ─────────────────────
class InvitesSummary(BaseModel):
    total: int = 0
    pending: int = 0
    sent: int = 0
    accepted: int = 0
    clients: int = 0
    partners: int = 0


class InvitesSummaryResponse(BaseModel):
    sender_id: int
    summary: InvitesSummary


class InviteRow(BaseModel):
    invite_id: int
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone_number: str | None = None
    role: str | None = None
    status: str | None = None
    invitation_kind: str | None = None
    accepted_at: datetime | None = None
    user_id: int | None = None


class InvitesResponse(BaseModel):
    sender_id: int
    role: str | None = None
    status: str | None = None
    count: int = 0
    rows: list[InviteRow] = Field(default_factory=list)


# ── 4 & 5 · Clients / Partners (accepted invites) ─────────────────────────────
class PersonRow(BaseModel):
    user_id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone_number: str | None = None
    joined_at: datetime | None = None


class PeopleResponse(BaseModel):
    sender_id: int
    role: str
    count: int = 0
    rows: list[PersonRow] = Field(default_factory=list)


# ── 6 · Invited-by ────────────────────────────────────────────────────────────
class InvitedByResponse(BaseModel):
    user_id: int
    invited_by_id: int | None = None
    role: str | None = None
    invitation_kind: str | None = None
    accepted_at: datetime | None = None