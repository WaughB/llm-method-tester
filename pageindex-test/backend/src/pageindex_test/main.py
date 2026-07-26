"""FastAPI application factory with injected dependencies."""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine

from pageindex_test import __version__
from pageindex_test.config import Settings

logger = logging.getLogger("pageindex_test.api")


@dataclass
class AppDeps:
    settings: Settings
    engine: Engine
    health_probes: dict[str, Callable[[], dict]] = field(default_factory=dict)
    frontend_dist: Path | None = None


def create_app(deps: AppDeps) -> FastAPI:
    app = FastAPI(title="pageindex-test", version=__version__)
    app.state.deps = deps

    @app.get("/api/meta")
    def meta() -> dict:
        checks = {name: probe() for name, probe in deps.health_probes.items()}
        return {
            "version": __version__,
            "default_model": deps.settings.default_model,
            "checks": checks,
            "ok": all(c.get("ok") for c in checks.values()) if checks else True,
        }

    logger.info("application configured")

    if deps.frontend_dist is not None and deps.frontend_dist.exists():
        app.mount("/", StaticFiles(directory=deps.frontend_dist, html=True), name="frontend")
    return app


def build_deps(settings: Settings | None = None) -> AppDeps:
    """Production composition root."""
    from pageindex_test.db.schema import init_schema, make_engine
    from pageindex_test.health import check_database, check_ollama_models, check_qdrant
    from pageindex_test.obs.jsonlog import configure_logging

    settings = settings or Settings()
    engine = make_engine(settings.database_url)
    init_schema(engine)
    configure_logging(engine)
    logger.info("schema initialized", extra={"data": {"db": settings.database_url.split("@")[-1]}})
    frontend_dist = settings.frontend_dist or Path("frontend") / "dist"
    return AppDeps(
        settings=settings,
        engine=engine,
        health_probes={
            "database": lambda: check_database(engine),
            "qdrant": lambda: check_qdrant(settings.qdrant_url),
            "ollama": lambda: check_ollama_models(
                settings.ollama_base_url,
                [settings.default_model, settings.embedding_model],
            ),
        },
        frontend_dist=frontend_dist if frontend_dist.exists() else None,
    )
