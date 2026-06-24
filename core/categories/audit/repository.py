"""
ZipAI — Audit Data Access Layer (DAL).

Single responsibility: insert a user prompt into ai.AiConversationLogs
via the DB function. Follows the same pattern as the crime/healthcare
repository — parameterised SQL only, no string interpolation.

Save as: core/categories/audit/repository.py
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def insert_conversation_log(
    session: AsyncSession,
    prompt_text: str,
    user_id: int | None = None,
    session_id: str | None = None,
    event_id: str | None = None,
    notes: str | None = None,
    type: str | None = None,
) -> int:
    """
    Call ai.usp_AiConversationLog and return the new row Id.

    This is the only DB operation in this module — the audit table
    is append-only from the API side (no updates, no deletes).

    NOTE on commit/close:
      - We commit here so the row is persisted before the response
        is returned (Option B — commit in the repository).
      - We do NOT close the session manually. The get_schema_session
        dependency opens it inside an `async with` block, so FastAPI
        closes it automatically when the request ends.
      - If you later move the commit into get_schema_session (Option A),
        delete the `await session.commit()` line below so you don't
        commit twice.
    """
    # CHANGED: function name now matches the one you created in the DB
    # (ai.usp_AiConversationLog), instead of audit.fn_InsertAiConversationLog.
    sql = text("""
        SELECT ai.usp_AiConversationLog(
            :prompt_text,
            :user_id,
            :session_id,
            :event_id,
            :notes,
            :type
        ) AS new_id
    """)

    result = await session.execute(sql, {
        "prompt_text": prompt_text,
        "user_id":     user_id,
        "session_id":  session_id,
        "event_id":    event_id,
        "notes":       notes,
        "type":        type,
    })

    # Commit so the row is persisted immediately.
    await session.commit()

    row = result.fetchone()
    return int(row.new_id)