"""
ZipAI — Seller-Agent dashboard — Service Layer.

Maps repository rows to typed Pydantic models. Coercion helpers tolerate
Decimal / timedelta / str / None so no DB type can 500 the response.
"""
from __future__ import annotations

import datetime as _dt
from decimal import Decimal as _Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import (
    cached,
    agent_profile_cache,
    agent_listings_cache,
    agent_invites_summary_cache,
    agent_invites_cache,
    agent_people_cache,
    agent_invited_by_cache,
)
from . import repository as repo
from .schemas import (
    AgentProfile,
    AgentListingRow, AgentListingsResponse,
    InvitesSummary, InvitesSummaryResponse,
    InviteRow, InvitesResponse,
    PersonRow, PeopleResponse,
    InvitedByResponse,
)


def _i(v):
    if v is None:
        return 0
    if isinstance(v, _dt.timedelta):
        return int(v.days)
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _f(v):
    if v is None:
        return None
    if isinstance(v, _Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _s(v):
    return str(v) if v is not None else None


class AgentService:

    # 1 · Profile ──────────────────────────────────────────────────────────────
    @staticmethod
    @cached(agent_profile_cache)
    async def profile(session: AsyncSession, agent_key) -> AgentProfile:
        rows = await repo.agent_profile(session, agent_key)
        if not rows:
            return AgentProfile(agent_key=_s(agent_key))
        r = rows[0]
        return AgentProfile(agent_key=_s(r["agent_key"]), agent_name=r.get("agent_name"),
                            agent_email=r.get("agent_email"), agent_phone=r.get("agent_phone"),
                            office_key=_s(r.get("office_key")), office_name=r.get("office_name"))

    # 2 · Listings ─────────────────────────────────────────────────────────────
    @staticmethod
    @cached(agent_listings_cache)
    async def listings(session: AsyncSession, agent_key, status_key, limit) -> AgentListingsResponse:
        rows = await repo.agent_listings(session, agent_key, status_key, limit)
        out = [AgentListingRow(listing_key_numeric=_s(r["listing_key_numeric"]), address=r.get("address"),
                               city=r.get("city"), zip_code=_s(r.get("zip_code")),
                               list_price=_f(r["list_price"]), sale_price=_f(r["sale_price"]),
                               status=r.get("status"), property_type=r.get("property_type"),
                               beds=_f(r["beds"]), baths=_f(r["baths"]), sqft=_f(r["sqft"])) for r in rows]
        return AgentListingsResponse(agent_key=_s(agent_key), status=status_key, count=len(out), rows=out)

    # 3 · Invites summary (bar chart) ──────────────────────────────────────────
    @staticmethod
    @cached(agent_invites_summary_cache)
    async def invites_summary(session: AsyncSession, invited_by_id) -> InvitesSummaryResponse:
        rows = await repo.invites_summary(session, invited_by_id)
        r = rows[0] if rows else {}
        s = InvitesSummary(total=_i(r.get("total")), pending=_i(r.get("pending")),
                           sent=_i(r.get("sent")), accepted=_i(r.get("accepted")),
                           clients=_i(r.get("clients")), partners=_i(r.get("partners")))
        return InvitesSummaryResponse(invited_by_id=invited_by_id, summary=s)

    # 3 · Invites list (drill-down) ────────────────────────────────────────────
    @staticmethod
    @cached(agent_invites_cache)
    async def invites(session: AsyncSession, invited_by_id, role, status_key, limit) -> InvitesResponse:
        rows = await repo.invites(session, invited_by_id, role, status_key, limit)
        out = [InviteRow(invite_id=_i(r["invite_id"]), first_name=r.get("first_name"),
                         last_name=r.get("last_name"), email=r.get("email"),
                         phone_number=r.get("phone_number"), role=r.get("role"),
                         status=r.get("status"), invitation_kind=r.get("invitation_kind"),
                         accepted_at=r.get("accepted_at"),
                         user_id=(_i(r["user_id"]) if r["user_id"] is not None else None)) for r in rows]
        return InvitesResponse(invited_by_id=invited_by_id, role=role, status=status_key,
                               count=len(out), rows=out)

    # 4 & 5 · Clients / Partners ───────────────────────────────────────────────
    @staticmethod
    @cached(agent_people_cache)
    async def people_by_role(session: AsyncSession, invited_by_id, role, status_key, limit) -> PeopleResponse:
        rows = await repo.people_by_role(session, invited_by_id, role, status_key, limit)
        out = [PersonRow(user_id=(_i(r["user_id"]) if r["user_id"] is not None else None),
                         first_name=r.get("first_name"), last_name=r.get("last_name"),
                         email=r.get("email"), phone_number=r.get("phone_number"),
                         status=r.get("status"),
                         joined_at=r.get("joined_at")) for r in rows]
        return PeopleResponse(invited_by_id=invited_by_id, role=role, status=status_key, count=len(out), rows=out)

    # 6 · Invited-by ───────────────────────────────────────────────────────────
    @staticmethod
    @cached(agent_invited_by_cache)
    async def invited_by(session: AsyncSession, user_id) -> InvitedByResponse:
        rows = await repo.invited_by(session, user_id)
        if not rows:
            return InvitedByResponse(user_id=user_id)
        r = rows[0]
        return InvitedByResponse(user_id=user_id,
                                 invited_by_id=(_i(r["invited_by_id"]) if r["invited_by_id"] is not None else None),
                                 role=r.get("role"), invitation_kind=r.get("invitation_kind"),
                                 accepted_at=r.get("accepted_at"))