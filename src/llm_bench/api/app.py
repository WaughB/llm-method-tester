"""FastAPI application factory with injected dependencies."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from llm_bench.api.executor import ExecutorBusyError, RunExecutor, RunRequestSpec
from llm_bench.corpus.qa import QADataset
from llm_bench.runner import BenchmarkRunner
from llm_bench.storage.repository import ResultsRepository


@dataclass
class ApiDeps:
    repo: ResultsRepository
    runner: BenchmarkRunner
    dataset: QADataset
    models: list[str]
    health_check: Callable[[], dict]
    frontend_dist: Path | None = None


class RunRequest(BaseModel):
    models: list[str] | None = None
    strategies: list[str] | None = None
    question_ids: list[str] | None = None


def create_app(deps: ApiDeps) -> FastAPI:
    app = FastAPI(title="llm-method-tester", version="0.1.0")
    executor = RunExecutor()

    @app.get("/api/health")
    def health() -> dict:
        return deps.health_check()

    @app.get("/api/meta")
    def meta() -> dict:
        return {
            "models": deps.models,
            "strategies": deps.runner.available_strategies,
            "question_count": len(deps.dataset),
        }

    @app.get("/api/questions")
    def questions() -> list[dict]:
        return [q.model_dump() for q in deps.dataset]

    @app.post("/api/runs", status_code=202)
    def start_run(request: RunRequest) -> dict:
        known = set(deps.runner.available_strategies)
        if request.strategies and not set(request.strategies) <= known:
            unknown = sorted(set(request.strategies) - known)
            raise HTTPException(status_code=400, detail=f"Unknown strategies: {unknown}")
        spec = RunRequestSpec(
            models=request.models or deps.models,
            strategy_names=request.strategies,
            question_ids=request.question_ids,
        )
        try:
            run_id = executor.start(deps.runner, deps.repo, deps.dataset, spec)
        except ExecutorBusyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"run_id": run_id}

    @app.get("/api/runs")
    def list_runs() -> list[dict]:
        return [r.model_dump() for r in deps.repo.list_runs()]

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: int) -> dict:
        run = _run_or_404(run_id)
        payload = run.model_dump()
        payload["progress"] = executor.progress_for(run_id)
        return payload

    @app.get("/api/runs/{run_id}/results")
    def run_results(run_id: int) -> list[dict]:
        _run_or_404(run_id)
        return [r.model_dump() for r in deps.repo.results_for_run(run_id)]

    @app.get("/api/runs/{run_id}/summary")
    def run_summary(run_id: int, category: str | None = None) -> list[dict]:
        _run_or_404(run_id)
        return [row.model_dump() for row in deps.repo.summary_for_run(run_id, category=category)]

    def _run_or_404(run_id: int):
        try:
            return deps.repo.get_run(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"No run {run_id}") from exc

    if deps.frontend_dist is not None and deps.frontend_dist.exists():
        app.mount("/", StaticFiles(directory=deps.frontend_dist, html=True), name="frontend")

    return app
