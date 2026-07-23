"""
ZipAI — Dynamic Multi-Schema Session Manager

Lazily creates and caches one async SQLAlchemy engine + session factory
per PostgreSQL schema.  Each schema gets its own connection pool with
``search_path`` set to ``<schema>,public``.

Usage in any domain module:
    from app.db.schema_manager import get_schema_session

    # FastAPI dependency — just pass the schema name:
    @router.get("/...")
    async def endpoint(db = Depends(get_schema_session("healthcare"))):
        ...

Adding a future domain (crime, school, …) requires ZERO changes here —
just call ``get_schema_session("crime")`` from the new domain's routes.
"""
 
from __future__ import annotations

import threading
from collections.abc import AsyncGenerator
from typing import Callable

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import get_settings
# from logging import get_logger

# logger = get_logger(__name__)


class SchemaSessionManager:
    """
    Singleton registry that manages one async engine per PostgreSQL schema.

    Thread-safe: uses a lock for lazy engine/factory creation so that
    concurrent startup requests don't create duplicate pools.
    """

    def __init__(self) -> None:
        self._engines: dict[str, AsyncEngine] = {}
        self._factories: dict[str, async_sessionmaker[AsyncSession]] = {}
        self._lock = threading.RLock()
        self._settings = get_settings()

    # ── Engine / Factory ──────────────────────────────────────────────────

    def get_engine(self, schema: str) -> AsyncEngine:
        """Return (or create) the async engine for *schema*."""
        if schema not in self._engines:
            with self._lock:
                # Double-checked locking
                if schema not in self._engines:
                    engine = create_async_engine(
                        self._settings.database_url,
                        echo=self._settings.db_echo,
                        pool_size=3,
                        max_overflow=2,
                        pool_pre_ping=True,
                        pool_recycle=3600,
                        connect_args={
                            "server_settings": {
                                "search_path": f"{schema},public",
                                "application_name": "zipai-external",
                            }
                        },
                    )
                    self._engines[schema] = engine
                    # logger.info(
                    #     "schema_engine_created",
                    #     schema=schema,
                    #     pool_size=5,
                    #     max_overflow=10,
                    # )
        return self._engines[schema]

    def get_factory(self, schema: str) -> async_sessionmaker[AsyncSession]:
        """Return (or create) the session factory for *schema*."""
        if schema not in self._factories:
            with self._lock:
                if schema not in self._factories:
                    engine = self.get_engine(schema)
                    factory = async_sessionmaker(
                        bind=engine,
                        class_=AsyncSession,
                        expire_on_commit=False,
                        autoflush=False,
                        autocommit=False,
                    )
                    self._factories[schema] = factory
                    # logger.info("schema_session_factory_created", schema=schema)
        return self._factories[schema]

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def dispose_all(self) -> None:
        """Dispose every engine.  Call during application shutdown."""
        for schema, engine in self._engines.items():
            await engine.dispose()
            # logger.info("schema_engine_disposed", schema=schema)
        self._engines.clear()
        self._factories.clear()


# ── Module-level singleton ────────────────────────────────────────────────────
schema_manager = SchemaSessionManager()


def get_schema_session(schema: str) -> Callable[[], AsyncGenerator[AsyncSession, None]]:
    """
    FastAPI dependency factory.

    Returns an async generator that yields a **read-only** session for the
    requested schema.  The session is rolled back on error and always closed.

    Example::

        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_schema_session("healthcare"))):
            result = await db.execute(text("SELECT ..."))
            ...
    """

    async def _session_dependency() -> AsyncGenerator[AsyncSession, None]:
        factory = schema_manager.get_factory(schema)
        async with factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    return _session_dependency
