"""
ZipAI — Multi-Schema Session Manager

ONE shared async engine + session factory for the whole app. All schemas
live on the same database, so they share a single connection pool; the
active schema is selected per-request via ``SET search_path``.
"""

from __future__ import annotations

import threading
from collections.abc import AsyncGenerator
from typing import Callable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import get_settings

# Schemas the app is allowed to switch to. Guards the SET search_path below
# against injection, since the schema name is interpolated into raw SQL.
_ALLOWED_SCHEMAS = frozenset({
    "analytics", "cost_of_living", "crime", "employer",
    "healthcare", "lifestyle", "rag", "schools",
})


class SchemaSessionManager:
    """Singleton holding ONE async engine + factory shared by all schemas."""

    def __init__(self) -> None:
        self._engine: AsyncEngine | None = None
        self._factory: async_sessionmaker[AsyncSession] | None = None
        self._lock = threading.RLock()
        self._settings = get_settings()

    # ── Engine / Factory ──────────────────────────────────────────────────

    def get_engine(self) -> AsyncEngine:
        """Return (or lazily create) the single shared async engine."""
        if self._engine is None:
            with self._lock:
                if self._engine is None:                 # double-checked locking
                    self._engine = create_async_engine(
                        self._settings.database_url,
                        echo=self._settings.db_echo,
                        pool_size=10,
                        max_overflow=5,
                        pool_pre_ping=True,
                        pool_recycle=3600,
                        pool_timeout=30,
                        connect_args={
                            "server_settings": {
                                "application_name": "zipai-external",
                            }
                        },
                    )
        return self._engine

    def get_factory(self) -> async_sessionmaker[AsyncSession]:
        """Return (or lazily create) the single shared session factory."""
        if self._factory is None:
            with self._lock:
                if self._factory is None:
                    self._factory = async_sessionmaker(
                        bind=self.get_engine(),
                        class_=AsyncSession,
                        expire_on_commit=False,
                        autoflush=False,
                        autocommit=False,
                    )
        return self._factory

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def dispose_all(self) -> None:
        """Dispose the engine.  Call during application shutdown."""
        if self._engine is not None:
            await self._engine.dispose()
        self._engine = None
        self._factory = None


# ── Module-level singleton ────────────────────────────────────────────────────
schema_manager = SchemaSessionManager()


def get_schema_session(schema: str) -> Callable[[], AsyncGenerator[AsyncSession, None]]:
    """
    FastAPI dependency factory.

    Yields a session whose ``search_path`` is scoped to *schema* for the life
    of the request. The session is rolled back on error and always closed.
    """
    if schema not in _ALLOWED_SCHEMAS:
        raise ValueError(f"Unknown schema: {schema!r}")

    async def _session_dependency() -> AsyncGenerator[AsyncSession, None]:
        factory = schema_manager.get_factory()
        async with factory() as session:
            try:
                await session.execute(
                    text(f"SET search_path TO {schema}, public")
                )
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    return _session_dependency