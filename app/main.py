"""FastAPI application factory and ASGI entrypoint.

``create_app`` wires the routers, the ``Allow``-header middleware, and the
Prometheus instrumentator; ``app`` is the module-level ASGI callable uvicorn
and the test client import.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app import __version__
from app.api import responses as api_responses
from app.api.middleware import AllowHeaderMiddleware
from app.api.routes import auth, health, photos
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="SnapTrack API",
        version=__version__,
        summary="Photo tracking with async thumbnail processing and moderation workflows.",
        description=(
            "SnapTrack lets a user upload photos, tracks per-photo metadata, and "
            "derives thumbnails on a background worker. Reads of hot photo metadata "
            "are served from a Redis cache-aside layer."
        ),
    )

    app.add_middleware(AllowHeaderMiddleware)

    app.include_router(health.router)
    app.include_router(auth.router, responses={**api_responses.COMMON})
    app.include_router(photos.router, responses={**api_responses.COMMON})

    # Phase 1 hook: /metrics with request-count + latency histograms.
    Instrumentator(
        should_group_status_codes=False,
        should_instrument_requests_inprogress=True,
        inprogress_labels=True,
    ).instrument(app).expose(app, include_in_schema=False)

    @app.get("/", tags=["health"], include_in_schema=False)
    def root() -> dict:
        return {"service": "snaptrack-api", "version": __version__, "env": settings.environment}

    return app


app = create_app()
