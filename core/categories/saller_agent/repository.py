"""
ZipAI — Seller-Agent dashboard — Data Repository (DAL).

Two source tables (both in the Django `public` schema):
  - public.zipdata_idxlisting        -> agent identity + listings
  - public.zipdata_temporaryaccount  -> invite graph (who invited whom)

All values are bound parameters. asyncpg-safe: params used only in IS NULL are
wrapped in CAST(... AS type); no ':param::type' casts anywhere.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def _rows(session: AsyncSession, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    result = await session.execute(text(sql), params)
    return [dict(r._mapping) for r in result.fetchall()]


# ── 1 · Agent profile ─────────────────────────────────────────────────────────
async def agent_profile(session, agent_key):
    sql = """
        SELECT DISTINCT
               listing_member_key_numeric  AS agent_key,
               listing_member_name         AS agent_name,
               listing_member_email        AS agent_email,
               listing_member_phone        AS agent_phone,
               listing_office_key_numeric  AS office_key,
               listing_office_name         AS office_name
        FROM   public.zipdata_idxlisting
        WHERE  listing_member_key_numeric = :agent_key
        LIMIT  1
    """
    return await _rows(session, sql, {"agent_key": agent_key})


# ── 2 · Agent listings (status = active | pending | sold | all) ───────────────
async def agent_listings(session, agent_key, status_key, limit):
    sql = """
        SELECT listing_key_numeric,
               source_payload->>'UnparsedAddress' AS address,
               city, postal_code AS zip_code,
               list_price,
               NULL::numeric AS sale_price,
               standard_status AS status,
               property_class  AS property_type,
               bedrooms_total  AS beds,
               bathrooms_total_integer AS baths,
               living_area     AS sqft
        FROM   public.zipdata_idxlisting
        WHERE  listing_member_key_numeric = :agent_key
          AND  (:status = 'all'
                OR (:status = 'active'  AND standard_status = 'Active')
                OR (:status = 'pending' AND standard_status = 'Pending')
                OR (:status = 'sold'    AND standard_status = 'Closed'))
        ORDER  BY list_price DESC NULLS LAST
        LIMIT  :limit
    """
    return await _rows(session, sql, {"agent_key": agent_key, "status": status_key, "limit": limit})


# ── 3 · Invites summary (bar-chart counts) ────────────────────────────────────
async def invites_summary(session, sender_id):
    sql = """
        SELECT count(*)                                   AS total,
               count(*) FILTER (WHERE status = 'pending')  AS pending,
               count(*) FILTER (WHERE status = 'sent')     AS sent,
               count(*) FILTER (WHERE status = 'accepted') AS accepted,
               count(*) FILTER (WHERE role   = 'client')   AS clients,
               count(*) FILTER (WHERE role   = 'partner')  AS partners
        FROM   public.zipdata_temporaryaccount
        WHERE  invited_by_id = :sender_id
    """
    return await _rows(session, sql, {"sender_id": sender_id})


# ── 3 · Invites list (drill-down; optional role/status filters) ───────────────
async def invites(session, sender_id, role, status_key, limit):
    sql = """
        SELECT id AS invite_id,
               first_name, last_name, email, phone_number,
               role, status, invitation_kind, accepted_at, user_id
        FROM   public.zipdata_temporaryaccount
        WHERE  invited_by_id = :sender_id
          AND  (CAST(:role   AS text) IS NULL OR role   = :role)
          AND  (CAST(:status AS text) IS NULL OR status = :status)
        ORDER  BY accepted_at DESC NULLS LAST, id DESC
        LIMIT  :limit
    """
    return await _rows(session, sql, {"sender_id": sender_id, "role": role,
                                      "status": status_key, "limit": limit})


# ── 4 & 5 · Clients / Partners (accepted, became real users) ──────────────────
async def people_by_role(session, sender_id, role, limit):
    sql = """
        SELECT user_id, first_name, last_name, email, phone_number,
               accepted_at AS joined_at
        FROM   public.zipdata_temporaryaccount
        WHERE  invited_by_id = :sender_id
          AND  role = :role
          AND  status = 'accepted'
          AND  user_id IS NOT NULL
        ORDER  BY accepted_at DESC NULLS LAST
        LIMIT  :limit
    """
    return await _rows(session, sql, {"sender_id": sender_id, "role": role, "limit": limit})


# ── 6 · Invited-by (who invited this user) ────────────────────────────────────
async def invited_by(session, user_id):
    sql = """
        SELECT invited_by_id, role, invitation_kind, accepted_at
        FROM   public.zipdata_temporaryaccount
        WHERE  user_id = :user_id
        ORDER  BY accepted_at DESC NULLS LAST
        LIMIT  1
    """
    return await _rows(session, sql, {"user_id": user_id})