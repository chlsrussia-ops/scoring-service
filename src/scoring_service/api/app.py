from __future__ import annotations

from fastapi import FastAPI

from scoring_service.api.routes import router
from scoring_service.config import Settings
from scoring_service.diagnostics import configure_logging


def create_app() -> FastAPI:
    settings = Settings()
    configure_logging(settings.log_level, json_logs=settings.log_json)

    app = FastAPI(
        title=settings.app_name,
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.state.settings = settings
    app.include_router(router)
    return app
