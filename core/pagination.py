"""
ZipAI — Reusable Pagination Utilities.

Centralises limit/offset pagination so every domain (healthcare, and any
future crime/school/… schema) shares one implementation instead of redefining
``PaginationMeta`` and the ``limit``/``offset`` Query params per module.

Three pieces fit together:

  1. ``pagination_params(...)`` — a FastAPI dependency factory that yields a
     validated :class:`PaginationParams` (limit + offset) with per-endpoint
     defaults and ceilings.
  2. ``PaginationMeta`` — the Pydantic model returned in list responses. It is
     a drop-in superset of the inline meta used by the healthcare schemas
     (``limit``/``offset``/``total``) plus computed navigation helpers.
  3. ``paginate`` / ``PaginationMeta.build`` — turn a repository's
     ``(rows, total)`` tuple into a meta object (and optionally a full page).

Repositories already return ``(rows, total)``; this module turns that pair
into the response contract without each service hand-rolling the maths.

Example (route layer)::

    from core.pagination import PaginationParams, pagination_params

    @router.get("/items")
    async def list_items(
        page: PaginationParams = Depends(pagination_params(default_limit=50, max_limit=200)),
        db: AsyncSession = Depends(get_schema_session("healthcare")),
    ):
        rows, total = await repo_list_items(db, limit=page.limit, offset=page.offset)
        return ItemsResponse(items=rows, pagination=page.meta(total))
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, Sequence, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field

T = TypeVar("T")

# ── Defaults ────────────────────────────────────────────────────────────────────
# Conservative ceilings keep a single request from scanning unbounded result
# sets. Individual endpoints override these via ``pagination_params(...)``.
DEFAULT_LIMIT = 50
DEFAULT_MAX_LIMIT = 200
DEFAULT_OFFSET = 0


# ── Pagination metadata ─────────────────────────────────────────────────────────


class PaginationMeta(BaseModel):
    """
    Pagination metadata returned with list endpoints.

    A superset of the minimal ``{limit, offset, total}`` contract: the extra
    fields are derived once on the server so clients don't have to recompute
    page numbers and "is there more?" themselves.
    """

    limit: int = Field(..., description="Maximum items per page.")
    offset: int = Field(..., description="Number of items skipped.")
    total: int = Field(..., description="Total items matching the query.")
    count: int = Field(..., description="Number of items actually returned in this page.")
    page: int = Field(..., description="Current 1-based page number.")
    pages: int = Field(..., description="Total number of pages available.")
    has_more: bool = Field(..., description="True if more items exist after this page.")
    has_previous: bool = Field(..., description="True if a previous page exists.")

    @classmethod
    def build(cls, *, limit: int, offset: int, total: int, count: int | None = None) -> "PaginationMeta":
        """
        Compute pagination metadata from the raw window and total.

        Args:
            limit: Page size requested.
            offset: Number of items skipped.
            total: Total items matching the query (the count query result).
            count: Items actually returned. Defaults to the window size capped
                by ``total`` when not supplied (i.e. assumes a full page).
        """
        # Guard against limit=0 to keep page arithmetic safe.
        safe_limit = max(limit, 1)

        if count is None:
            count = max(0, min(safe_limit, total - offset))

        pages = (total + safe_limit - 1) // safe_limit if total > 0 else 0
        page = (offset // safe_limit) + 1

        return cls(
            limit=limit,
            offset=offset,
            total=total,
            count=count,
            page=page,
            pages=pages,
            has_more=offset + count < total,
            has_previous=offset > 0,
        )


# ── Generic page envelope ─────────────────────────────────────────────────────────


class Page(BaseModel, Generic[T]):
    """
    Generic paginated envelope: a list of items plus pagination metadata.

    Domains that don't need a bespoke response model (with extra top-level
    fields like ``zipcode_filter``) can return ``Page[ProviderDetail]`` directly.
    """

    items: list[T] = Field(default_factory=list, description="Items on this page.")
    pagination: PaginationMeta = Field(..., description="Pagination metadata.")

    @classmethod
    def of(cls, items: Sequence[T], *, limit: int, offset: int, total: int) -> "Page[T]":
        """Build a page from items and the raw window/total."""
        items = list(items)
        meta = PaginationMeta.build(limit=limit, offset=offset, total=total, count=len(items))
        return cls(items=items, pagination=meta)


# ── Request parameters (FastAPI dependency) ───────────────────────────────────────


@dataclass(frozen=True)
class PaginationParams:
    """
    Validated ``limit``/``offset`` pair for a single request.

    Use the convenience methods to bridge into the response contract:
        ``page.meta(total)``         → :class:`PaginationMeta`
        ``page.paginate(rows, total)`` → :class:`Page`
    """

    limit: int
    offset: int

    def meta(self, total: int, count: int | None = None) -> PaginationMeta:
        """Build :class:`PaginationMeta` for this window against *total*."""
        return PaginationMeta.build(limit=self.limit, offset=self.offset, total=total, count=count)

    def paginate(self, rows: Sequence[T], total: int) -> Page[T]:
        """Wrap repository ``(rows, total)`` output into a :class:`Page`."""
        return Page.of(rows, limit=self.limit, offset=self.offset, total=total)


def pagination_params(
    *,
    default_limit: int = DEFAULT_LIMIT,
    max_limit: int = DEFAULT_MAX_LIMIT,
    default_offset: int = DEFAULT_OFFSET,
) -> Callable[..., PaginationParams]:
    """
    FastAPI dependency factory for ``limit``/``offset`` query parameters.

    Each endpoint can set its own page size and ceiling — e.g. map pins allow
    larger pages than provider listings::

        Depends(pagination_params(default_limit=200, max_limit=500))

    Args:
        default_limit: Page size when the client omits ``limit``.
        max_limit: Hard ceiling enforced by FastAPI validation (HTTP 422).
        default_offset: Starting offset when the client omits ``offset``.

    Returns:
        A dependency callable that resolves to a :class:`PaginationParams`.
    """

    def _dependency(
        limit: int = Query(
            default=default_limit,
            ge=1,
            le=max_limit,
            description=f"Max items per page (1–{max_limit}).",
        ),
        offset: int = Query(
            default=default_offset,
            ge=0,
            description="Number of items to skip.",
        ),
    ) -> PaginationParams:
        return PaginationParams(limit=limit, offset=offset)

    return _dependency


# ── Plain helpers ──────────────────────────────────────────────────────────────


def paginate(rows: Sequence[T], total: int, *, limit: int, offset: int) -> Page[T]:
    """
    Functional equivalent of :meth:`PaginationParams.paginate`.

    Handy when limit/offset are already loose variables rather than a
    :class:`PaginationParams` instance.
    """
    return Page.of(rows, limit=limit, offset=offset, total=total)


def clamp_limit(limit: int, *, max_limit: int = DEFAULT_MAX_LIMIT) -> int:
    """Clamp an arbitrary limit into the ``[1, max_limit]`` range."""
    return max(1, min(limit, max_limit))
