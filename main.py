"""
ZipAI External Data API — application entry point.

Builds the FastAPI app, wires up domain routers under ``/v1`` and manages
the per-schema database engine lifecycle.

Run locally::

    python main.py --reload
    # or
    uvicorn main:app --reload
"""

from __future__ import annotations

import argparse
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from core.config import get_settings
from core.schema_manager import schema_manager
from core.categories.healthcare.routes import router as healthcare_router
from core.categories.crime.routes import router as crime_router

from core.categories.lifestyle.routes import router as lifestyle_router

from core.categories.schools.routes import router as schools_router
from core.categories.cost_of_living.routes import router as cost_of_living_router
from core.categories.employer.routes import router as jobs_router

from core.categories.audit.routes import router as audit_router



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — dispose every per-schema engine on shutdown."""
    yield
    await schema_manager.dispose_all()


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="ZipAI External Data API",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health", tags=["Meta"], summary="Liveness probe")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.service_name, "env": settings.app_env}

    # Domain routers — final paths become /v1/healthcare/...
    app.include_router(healthcare_router, prefix="/v1")

    # crime
    app.include_router(crime_router, prefix="/v1")
  
    #lifestyle
    app.include_router(lifestyle_router, prefix="/v1")

    # schools
    app.include_router(schools_router,prefix="/v1")

    # cost of living
    app.include_router(cost_of_living_router,prefix="/v1")

    #employer
    app.include_router(jobs_router, prefix="/v1")

    #audit
    app.include_router(audit_router, prefix="/v1")

    #Vector
    app.include_router(analytics_router, prefix="/v1")


    return app


app = create_app()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the ZipAI External Data API")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    # Pass the import string (not the app object) so --reload can re-import on change.
    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
