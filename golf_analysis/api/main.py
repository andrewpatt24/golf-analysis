from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from golf_analysis.api.access import AccessTokenMiddleware
from golf_analysis.api.routers import health, meta, on_course, performance, plans, range, reference, rounds, settings, strategy


def create_app() -> FastAPI:
    app = FastAPI(title="Golf Analysis API", version="1.0.0")
    app.add_middleware(AccessTokenMiddleware)

    origins_raw = os.environ.get(
        "GOLF_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    origins = [o.strip() for o in origins_raw.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for r in (
        health.router,
        meta.router,
        rounds.router,
        range.router,
        performance.router,
        strategy.router,
        reference.router,
        settings.router,
        on_course.router,
        plans.router,
    ):
        app.include_router(r, prefix="/api/v1")

    static_dir = os.environ.get("GOLF_DASHBOARD_DIST")
    if static_dir:
        path = Path(static_dir).expanduser().resolve()
        if path.is_dir():
            app.mount("/", StaticFiles(directory=str(path), html=True), name="dashboard")

    return app


app = create_app()
