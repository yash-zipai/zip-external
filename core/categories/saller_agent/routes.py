"""
Seller-Agent dashboard — API routes.

    from core.categories.saller_agent.routes import router as agent_router
    app.include_router(agent_router, prefix="/v1")

NOTE on identity:
  - Profile & listings scope by the MLS agent key (listing_member_key_numeric).
  - Invites/clients/partners/invited-by scope by the app user id (zipdata_customuser.id).
  For now both are passed as query params. Once auth is wired, replace the
  `agent_key` / `user_id` query params with a dependency that resolves them from
  the logged-in user (see resolve_agent_key / resolve_user_id TODO below).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.schema_manager import get_schema_session
from .schemas import (
    AgentProfile,
    AgentListingsResponse,
    InvitesSummaryResponse, InvitesResponse,
    PeopleResponse, InvitedByResponse,
)
from .service import AgentService

router = APIRouter(tags=["Seller Agent"])
_db = get_schema_session("public")     # agent tables live in the Django public schema

ALLOWED_LISTING_STATUS = {"all", "active", "pending", "sold"}
ALLOWED_ROLES = {"client", "partner"}
ALLOWED_INVITE_STATUS = {"pending", "sent", "accepted"}

# ── TODO (auth): replace these query params with real resolvers ───────────────
# def resolve_agent_key(user = Depends(current_user)) -> str: ...
# def resolve_user_id(user = Depends(current_user)) -> int: ...
# Until then, the caller passes agent_key / user_id explicitly.


# ═══════════════════════════ 1 · AGENT PROFILE ═══════════════════════════════
@router.get("/agent/me", response_model=AgentProfile, summary="Agent profile")
async def agent_me(
    agent_key: str = Query(..., description="MLS listing_member_key_numeric of the logged-in agent."),
    db: AsyncSession = Depends(_db),
) -> AgentProfile:
    return await AgentService.profile(db, agent_key)


# ═══════════════════════════ 2 · AGENT LISTINGS ══════════════════════════════
@router.get("/agent/listings/", response_model=AgentListingsResponse, summary="Agent listings")
async def agent_listings(
    agent_key: str = Query(..., description="MLS agent key."),
    status_: str = Query("all", alias="status", description="all | active | pending | sold"),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(_db),
) -> AgentListingsResponse:
    s = status_.lower()
    if s not in ALLOWED_LISTING_STATUS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"status must be one of {sorted(ALLOWED_LISTING_STATUS)}.")
    return await AgentService.listings(db, agent_key, s, limit)


# ═══════════════════ 3 · INVITES — summary (bar chart) ═══════════════════════
@router.get("/agent/invites/summary", response_model=InvitesSummaryResponse,
            summary="Invites summary (counts for the bar chart)")
async def invites_summary(
    invited_by_id: int = Query(..., description="Logged-in agent's zipdata_customuser id (the invite sender)."),
    db: AsyncSession = Depends(_db),
) -> InvitesSummaryResponse:
    return await AgentService.invites_summary(db, invited_by_id)


# ═══════════════════ 3 · INVITES — list (drill-down) ═════════════════════════
@router.get("/agent/invites/", response_model=InvitesResponse,
            summary="Invited users (drill-down; filter by role/status)")
async def invites(
    invited_by_id: int = Query(..., description="Logged-in agent's user id (the invite sender)."),
    role: str | None = Query(None, description="client | partner (omit for all)."),
    status_: str | None = Query(None, alias="status", description="pending | sent | accepted (omit for all)."),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(_db),
) -> InvitesResponse:
    if role is not None and role.lower() not in ALLOWED_ROLES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"role must be one of {sorted(ALLOWED_ROLES)}.")
    if status_ is not None and status_.lower() not in ALLOWED_INVITE_STATUS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"status must be one of {sorted(ALLOWED_INVITE_STATUS)}.")
    return await AgentService.invites(db, invited_by_id,
                                      role.lower() if role else None,
                                      status_.lower() if status_ else None, limit)


# ═══════════════════════════ 4 · AGENT CLIENTS ═══════════════════════════════
@router.get("/agent/clients/", response_model=PeopleResponse, summary="Agent clients (accepted)")
async def agent_clients(
    invited_by_id: int = Query(..., description="Logged-in agent's user id (the invite sender)."),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(_db),
) -> PeopleResponse:
    return await AgentService.people_by_role(db, invited_by_id, "client", limit)


# ═══════════════════════════ 5 · AGENT PARTNERS ══════════════════════════════
@router.get("/agent/partners/", response_model=PeopleResponse, summary="Agent partners (accepted)")
async def agent_partners(
    invited_by_id: int = Query(..., description="Logged-in agent's user id (the invite sender)."),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(_db),
) -> PeopleResponse:
    return await AgentService.people_by_role(db, invited_by_id, "partner", limit)


# ═══════════════════════════ 6 · INVITED-BY ══════════════════════════════════
@router.get("/agent/invited-by", response_model=InvitedByResponse, summary="Who invited this agent")
async def invited_by(
    user_id: int = Query(..., description="Logged-in agent's user id."),
    db: AsyncSession = Depends(_db),
) -> InvitedByResponse:
    return await AgentService.invited_by(db, user_id)