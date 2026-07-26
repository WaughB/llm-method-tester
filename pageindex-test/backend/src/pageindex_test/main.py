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
    settings_repo: object = None
    location_service: object = None
    document_repo: object = None
    chunk_repo: object = None
    job_repo: object = None
    vector_index_factory: Callable[[str], object] | None = None


def create_app(deps: AppDeps) -> FastAPI:
    from pageindex_test.api.documents_router import router as documents_router
    from pageindex_test.api.locations_router import router as locations_router
    from pageindex_test.db.repos import ChunkRepo, DocumentRepo, JobRepo, SettingsRepo
    from pageindex_test.locations import LocationService
    from pageindex_test.retrieval.vectors import QdrantIndex

    if deps.settings_repo is None:
        deps.settings_repo = SettingsRepo(deps.engine)
    if deps.location_service is None:
        deps.location_service = LocationService(deps.settings, deps.settings_repo)
    if deps.document_repo is None:
        deps.document_repo = DocumentRepo(deps.engine)
    if deps.chunk_repo is None:
        deps.chunk_repo = ChunkRepo(deps.engine)
    if deps.job_repo is None:
        deps.job_repo = JobRepo(deps.engine)
    if deps.vector_index_factory is None:
        deps.vector_index_factory = lambda location_id: QdrantIndex(
            deps.settings.qdrant_url, location_id
        )

    app = FastAPI(title="pageindex-test", version=__version__)
    app.state.deps = deps
    app.include_router(locations_router)
    app.include_router(documents_router)

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
