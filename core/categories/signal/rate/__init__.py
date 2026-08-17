"""
ZipAI — Rate (mortgage) signal module.

Rate page API built on signal.mortgage_rate (Freddie Mac PMMS via FRED).
Exposes ``router`` for inclusion in the FastAPI app.
"""

from .routes import router as rate_router

__all__ = ["rate_router"]