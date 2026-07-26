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
    conversation_repo: object = None
    trace_repo: object = None
    eval_repo: object = None
    vector_index_factory: Callable[[str], object] | None = None
    lexical_index: object = None
    query_pipeline: object = None


def create_app(deps: AppDeps) -> FastAPI:
    from llm_bench.llm.ollama import OllamaClient, OllamaEmbeddingClient

    from pageindex_test.api.chat_router import router as chat_router
    from pageindex_test.api.documents_router import router as documents_router
    from pageindex_test.api.eval_router import router as eval_router
    from pageindex_test.api.locations_router import router as locations_router
    from pageindex_test.db.repos import (
        ChunkRepo,
        ConversationRepo,
        DocumentRepo,
        EvalRepo,
        JobRepo,
        SettingsRepo,
        TraceRepo,
    )
    from pageindex_test.locations import LocationService
    from pageindex_test.pipeline.query import QueryPipeline
    from pageindex_test.retrieval.lexical import Bm25Index
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
    if deps.conversation_repo is None:
        deps.conversation_repo = ConversationRepo(deps.engine)
    if deps.trace_repo is None:
        deps.trace_repo = TraceRepo(deps.engine)
    if deps.eval_repo is None:
        deps.eval_repo = EvalRepo(deps.engine)
    if deps.vector_index_factory is None:
        deps.vector_index_factory = lambda location_id: QdrantIndex(
            deps.settings.qdrant_url, location_id
        )
    if deps.lexical_index is None:
        deps.lexical_index = Bm25Index()
    if deps.query_pipeline is None:
        from pageindex_test.locations import library_dir
        from pageindex_test.retrieval.trees import TreeStage

        settings = deps.settings
        llm = OllamaClient(settings.ollama_base_url, timeout_s=settings.request_timeout_s)

        def _location(location_id: str):
            for loc in deps.location_service.list():
                if loc.location_id == location_id:
                    return loc
            raise KeyError(f"Unknown location {location_id}")

        tree_stage = TreeStage(
            llm=llm,
            tree_cache_dir_resolver=lambda loc_id: library_dir(_location(loc_id)) / "trees",
            extracted_path_resolver=lambda loc_id, doc_id: (
                library_dir(_location(loc_id)) / "docs" / doc_id / "extracted.md"
            ),
            doc_title_resolver=lambda doc_id: (
                (deps.document_repo.get(doc_id) or {}).get("title") or "Document"
            ),
            max_docs=settings.tree_stage_docs,
            num_ctx=settings.tree_num_ctx,
        )
        deps.query_pipeline = QueryPipeline(
            engine=deps.engine,
            chunks=deps.chunk_repo,
            lexical=deps.lexical_index,
            embedder=OllamaEmbeddingClient(
                settings.ollama_base_url, model=settings.embedding_model
            ),
            vector_index_factory=deps.vector_index_factory,
            llm=llm,
            hybrid_top_n=settings.hybrid_top_n,
            tree_stage=tree_stage,
        )

    app = FastAPI(title="pageindex-test", version=__version__)
    app.state.deps = deps
    from pageindex_test.api.logs_router import router as logs_router

    app.include_router(locations_router)
    app.include_router(documents_router)
    app.include_router(chat_router)
    app.include_router(eval_router)
    app.include_router(logs_router)

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
    from pageindex_test.obs.jsonlog import configure_logging, prune_old_logs

    settings = settings or Settings()
    engine = make_engine(settings.database_url)
    init_schema(engine)
    configure_logging(engine)
    pruned = prune_old_logs(engine, settings.log_retention_days)
    logger.info(
        "schema initialized",
        extra={"data": {"db": settings.database_url.split("@")[-1], "logs_pruned": pruned}},
    )
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
