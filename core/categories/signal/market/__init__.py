"""
ZipAI — Market (MLS) signal module.

Market-analysis API built on the ``signal`` schema (signal.listing_fact).
Exposes ``router`` for inclusion in the FastAPI app.
"""

from .routes import router as market_router

__all__ = ["market_router"]